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
