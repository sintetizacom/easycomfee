import app


def test_copia_para_a_pasta_de_resultados(tmp_path, monkeypatch):
    saida = tmp_path / "comfy_out"; (saida / "editor").mkdir(parents=True)
    (saida / "editor" / "a.png").write_bytes(b"x")
    monkeypatch.setattr(app, "SAIDA_DO_MOTOR", saida)
    monkeypatch.setattr(app.pasta_resultados, "atual", lambda: tmp_path / "output")
    app.copiar_para_easycomfee([{"nome": "a.png", "subpasta": "editor"}, {"nome": "../x", "subpasta": "editor"}])
    assert (tmp_path / "output" / "editor" / "a.png").read_bytes() == b"x"


def test_nao_copia_quando_o_comfyui_ja_grava_ali(tmp_path, monkeypatch):
    saida = tmp_path / "output"; (saida / "editor").mkdir(parents=True)
    (saida / "editor" / "a.png").write_bytes(b"x")
    monkeypatch.setattr(app, "SAIDA_DO_MOTOR", saida)
    monkeypatch.setattr(app.pasta_resultados, "atual", lambda: saida)
    app.copiar_para_easycomfee([{"nome": "a.png", "subpasta": "editor"}])
    assert list(saida.rglob("*")) == [saida / "editor", saida / "editor" / "a.png"]
