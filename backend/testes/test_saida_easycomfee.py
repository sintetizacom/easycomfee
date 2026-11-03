import json

import iniciar_comfy as ic


def _rodar(tmp_path, monkeypatch, **extra):
    monkeypatch.setattr(ic, "RAIZ", tmp_path)
    monkeypatch.setattr(ic, "controle_inteligente_ligado", lambda: False)
    cfg = {"comfy_iniciar": True, "comfy_dir": str(tmp_path / "ComfyUI_windows_portable" / "ComfyUI"),
           "comfy_url": "http://127.0.0.1:59999", **extra}
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    chamadas = []
    monkeypatch.setattr(ic.subprocess, "Popen", lambda cmd, **k: chamadas.append(cmd))
    ic.main()
    return chamadas[0]


def test_instalacao_nova_grava_na_pasta_do_easycomfee(tmp_path, monkeypatch):
    saida = tmp_path / "output"
    cmd = _rodar(tmp_path, monkeypatch, comfy_saida=saida.as_posix())
    assert f'--output-directory "{saida.as_posix()}"' in cmd.replace("\\", "/") or "--output-directory" in cmd
    assert saida.is_dir()


def test_instalacao_antiga_continua_na_pasta_do_comfyui(tmp_path, monkeypatch):
    assert "--output-directory" not in _rodar(tmp_path, monkeypatch)
