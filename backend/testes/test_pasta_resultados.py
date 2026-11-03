import json

import pasta_resultados as pr


def test_padrao_e_escolhida(tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "ARQUIVO", tmp_path / "config.json")
    (tmp_path / "config.json").write_text(json.dumps({"comfy_url": "x"}), encoding="utf-8")
    assert not pr.escolhida() and pr.atual().name == "output"
    destino = tmp_path / "Meus resultados"
    pr.salvar(str(destino))
    assert pr.escolhida() and pr.atual() == destino and destino.is_dir()
    assert json.loads((tmp_path / "config.json").read_text())["comfy_url"] == "x"  # o resto fica


def test_recusa_caminho_relativo(tmp_path, monkeypatch):
    monkeypatch.setattr(pr, "ARQUIVO", tmp_path / "config.json")
    try:
        pr.salvar("relativo/pasta")
        assert False
    except ValueError:
        pass
