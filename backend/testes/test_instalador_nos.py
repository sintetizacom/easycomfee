import asyncio
import io
import zipfile

import pytest

import instalador_nos
import pacotes


def _zip(arquivos: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, dados in arquivos.items():
            z.writestr(nome, dados)
    return buf.getvalue()


def teste_zip_do_github_perde_a_pasta_de_topo(tmp_path):
    instalador_nos._extrair(_zip({"repo-abc123/__init__.py": b"x", "repo-abc123/sub/a.py": b"y"}), tmp_path)
    assert (tmp_path / "__init__.py").read_bytes() == b"x"
    assert (tmp_path / "sub/a.py").exists()


def teste_zip_do_registro_fica_como_esta(tmp_path):
    instalador_nos._extrair(_zip({"__init__.py": b"x", "nodes/a.py": b"y"}), tmp_path)
    assert (tmp_path / "__init__.py").exists() and (tmp_path / "nodes/a.py").exists()


def teste_zip_que_escapa_da_pasta_e_recusado(tmp_path):
    destino = tmp_path / "no"
    destino.mkdir()
    with pytest.raises(RuntimeError):
        instalador_nos._extrair(_zip({"__init__.py": b"x", "../fora.py": b"y"}), destino)
    assert not (tmp_path / "fora.py").exists()


def teste_zip_que_usa_prefixo_parecido_e_recusado(tmp_path):
    destino = tmp_path / "no"
    destino.mkdir()
    with pytest.raises(RuntimeError):
        instalador_nos._extrair(_zip({"__init__.py": b"x", "../no-outro/fora.py": b"y"}), destino)
    assert not (tmp_path / "no-outro" / "fora.py").exists()


def teste_situacao_consulta_o_motor_do_no(tmp_path, monkeypatch):
    principal = tmp_path / "principal"
    segundo = tmp_path / "segundo"
    (segundo / "custom_nodes" / "Plenio-Music-Production-System").mkdir(parents=True)
    monkeypatch.setattr(instalador_nos.config, "COMFY_CODIGO_DIR", principal)
    monkeypatch.setattr(instalador_nos.config, "COMFY_DIR_FLUX3", segundo)
    # O segundo motor so existe com endereco proprio (no config.json desta maquina ha;
    # numa instalacao nova, nao): o teste monta esse cenario em vez de depender dele.
    monkeypatch.setattr(instalador_nos.config, "COMFY_URL", "http://127.0.0.1:8188")
    monkeypatch.setattr(instalador_nos.config, "COMFY_URL_FLUX3", "http://127.0.0.1:8189")
    estado = {n["nome"]: n for n in instalador_nos.situacao()}
    assert estado["Plenio Music Production"]["instalado"] is True


def teste_todo_no_tem_origem_fixa_e_pacote_que_existe():
    ids = {p["id"] for p in pacotes.carregar()} | {"base"}
    for n in instalador_nos.carregar():
        assert set(n["pacotes"]) <= ids, n["pasta"]
        if n["fonte"] == "registro":
            assert n["id"] and n["versao"]
        elif n["fonte"] == "github":
            assert len(n["commit"]) == 40  # commit inteiro, nao branch
        else:
            assert (instalador_nos.config.RAIZ / n["origem"] / "__init__.py").exists()


# Log real do pip (PC de teste, 29/10/2026): o LayerStyle troca o OpenCV e o cv2.pyd
# estava carregado no ComfyUI ligado.
LOG_EM_USO = ("Instalando os pacotes coletados: opencv-contrib-python, loguru\r\n"
              "ERRO: Não foi possível instalar os pacotes devido a um erro do sistema operacional: "
              "[WinError 5] Acesso negado: 'C:\\x\\site-packages\\cv2\\cv2.pyd'\r\n"
              "Considere usar a opção `--user` ou verifique as permissões.\r\n\r\n"
              "[aviso] Uma nova versão do pip está disponível: 26.2.1 -> 26.2.2\r\n")


def teste_motivo_do_pip_e_a_linha_de_erro():
    e = instalador_nos.PipFalhou("comfyui_layerstyle", LOG_EM_USO)
    assert e.em_uso
    assert "WinError 5" in str(e) and "cv2.pyd" in str(e)
    assert instalador_nos.motivo_pip("Collecting x\nfoo failed\n[notice] new pip") == "foo failed"
    assert not instalador_nos.PipFalhou("x", "ERROR: No matching distribution found for y").em_uso


@pytest.fixture
def cenario(tmp_path, monkeypatch):
    """Um no de "projeto" e um ComfyUI de mentira: registra quando desliga e liga."""
    (tmp_path / "origem").mkdir()
    (tmp_path / "origem" / "__init__.py").write_text("")
    (tmp_path / "comfy" / "custom_nodes").mkdir(parents=True)
    monkeypatch.setattr(instalador_nos.config, "RAIZ", tmp_path)
    monkeypatch.setattr(instalador_nos.config, "COMFY_CODIGO_DIR", tmp_path / "comfy")
    monkeypatch.setattr(instalador_nos.config, "COMFY_URL_FLUX3", instalador_nos.config.COMFY_URL)
    chamadas = []
    monkeypatch.setattr(instalador_nos.motores, "pode_religar", lambda: True)
    monkeypatch.setattr(instalador_nos.motores, "desligar", lambda: chamadas.append("desligar"))
    monkeypatch.setattr(instalador_nos.motores, "ligar", lambda: chamadas.append("ligar") or True)
    monkeypatch.setattr(instalador_nos.comfy, "esquecer_info", lambda: None)
    tentativas = []

    async def dependencias(pasta, no):
        tentativas.append("desligado" if "desligar" in chamadas else "ligado")
        if "desligar" not in chamadas:
            raise instalador_nos.PipFalhou(pasta.name, LOG_EM_USO)
    monkeypatch.setattr(instalador_nos, "_dependencias", dependencias)
    no = {"pasta": "no_teste", "nome": "Teste", "fonte": "projeto", "origem": "origem", "pacotes": ["base"]}
    yield no, chamadas, tentativas, tmp_path / "comfy" / "custom_nodes" / "no_teste"
    instalador_nos.motores._pausa.clear()
    instalador_nos._ocupado = lambda: False


def teste_arquivo_em_uso_desliga_o_comfy_tenta_de_novo_e_religa(cenario):
    no, chamadas, tentativas, final = cenario
    asyncio.run(instalador_nos._instalar([no]))
    assert tentativas == ["ligado", "desligado"]
    assert chamadas == ["desligar", "ligar"]
    assert final.is_dir()
    e = instalador_nos.ESTADO
    assert e["erros"] == [] and e["feitos"] == ["Teste"] and e["religado"] and not e["reiniciar"]
    assert not instalador_nos.motores._pausa.is_set()  # o vigia volta a funcionar


def teste_com_geracao_em_andamento_nao_desliga(cenario):
    no, chamadas, tentativas, final = cenario
    instalador_nos._ocupado = lambda: True
    asyncio.run(instalador_nos._instalar([no]))
    assert chamadas == [] and not final.exists()
    assert "close ComfyUI" in instalador_nos.ESTADO["erros"][0]
    assert "WinError 5" in instalador_nos.ESTADO["erros"][0]


def teste_comfy_de_outra_pessoa_nunca_e_desligado(cenario, monkeypatch):
    no, chamadas, tentativas, final = cenario
    monkeypatch.setattr(instalador_nos.motores, "pode_religar", lambda: False)
    asyncio.run(instalador_nos._instalar([no]))
    assert chamadas == [] and not final.exists()
    assert "close ComfyUI" in instalador_nos.ESTADO["erros"][0]


def teste_no_novo_sem_erro_tambem_religa(cenario, monkeypatch):
    no, chamadas, tentativas, final = cenario

    async def sem_erro(pasta, no):
        pass
    monkeypatch.setattr(instalador_nos, "_dependencias", sem_erro)
    asyncio.run(instalador_nos._instalar([no]))
    assert chamadas == ["desligar", "ligar"] and final.is_dir()
    assert instalador_nos.ESTADO["religado"]
