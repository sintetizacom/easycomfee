"""Botao Remove: so sai o que nenhum outro pacote instalado usa."""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import pacotes  # noqa: E402
import remocao  # noqa: E402


def _arq(nome):
    return {"arquivo": nome, "pasta": "vae", "subpasta": "", "rotulo": nome, "tamanho": 1}


def _cenario(tmp_path, monkeypatch, catalogo, no_disco):
    monkeypatch.setattr(config, "MODELOS_DIR", tmp_path)
    monkeypatch.setattr(pacotes, "carregar", lambda: catalogo)
    (tmp_path / "vae").mkdir()
    for n in no_disco:
        (tmp_path / "vae" / n).write_bytes(b"x")


def test_arquivo_dividido_com_pacote_instalado_fica(tmp_path, monkeypatch):
    cat = [{"id": "a", "nome": "A", "arquivos": [_arq("so_a.st"), _arq("comum.st")]},
           {"id": "b", "nome": "B", "arquivos": [_arq("so_b.st"), _arq("comum.st")]}]
    _cenario(tmp_path, monkeypatch, cat, ["so_a.st", "comum.st", "so_b.st"])
    p = remocao.plano("a")
    assert [i["arquivo"] for i in p["sai"]] == ["so_a.st"]
    assert p["fica"][0]["usado_por"] == ["B"]


def test_pacote_nunca_baixado_nao_segura_o_arquivo(tmp_path, monkeypatch):
    # B nunca foi baixado: so "tem" o comum por tabela. A remocao de A leva os dois.
    cat = [{"id": "a", "nome": "A", "arquivos": [_arq("so_a.st"), _arq("comum.st")]},
           {"id": "b", "nome": "B", "arquivos": [_arq("so_b.st"), _arq("comum.st")]}]
    _cenario(tmp_path, monkeypatch, cat, ["so_a.st", "comum.st"])
    assert sorted(i["arquivo"] for i in remocao.plano("a")["sai"]) == ["comum.st", "so_a.st"]


def test_remover_manda_so_os_do_plano(tmp_path, monkeypatch):
    cat = [{"id": "a", "nome": "A", "arquivos": [_arq("so_a.st"), _arq("comum.st")]},
           {"id": "b", "nome": "B", "arquivos": [_arq("so_b.st"), _arq("comum.st")]}]
    _cenario(tmp_path, monkeypatch, cat, ["so_a.st", "comum.st", "so_b.st"])
    levados = []
    monkeypatch.setattr(remocao, "_para_lixeira", lambda c: levados.append(c.name))
    remocao.remover("a")
    assert levados == ["so_a.st"]
