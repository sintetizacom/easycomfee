import json

import iniciar_comfy as ic


def _cfg(tmp_path, monkeypatch, **dados):
    monkeypatch.setattr(ic, "RAIZ", tmp_path)
    (tmp_path / "config.json").write_text(json.dumps(dados), encoding="utf-8")
    return dados


def test_porta_do_bat(tmp_path):
    bat = tmp_path / "run_nvidia_gpu.bat"
    bat.write_text(".\\python_embeded\\python.exe -s ComfyUI\\main.py --windows-standalone-build --port 8190\npause")
    assert ic.porta_do_bat(bat) == 8190
    bat.write_text(".\\python_embeded\\python.exe -s ComfyUI\\main.py --windows-standalone-build\npause")
    assert ic.porta_do_bat(bat) == 8188


def test_comfy_aberto_em_outra_porta_e_gravado(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch, comfy_url="http://127.0.0.1:8188", comfy_iniciar=False)
    monkeypatch.setattr(ic, "responde", lambda url: url.endswith(":8000"))
    abriu = []
    monkeypatch.setattr(ic.subprocess, "Popen", lambda *a, **k: abriu.append(a))
    ic.comfy_da_pessoa(cfg)
    assert json.loads((tmp_path / "config.json").read_text())["comfy_url"] == "http://127.0.0.1:8000"
    assert not abriu  # ja estava aberto: nao abre outro


def test_portatil_fechado_e_aberto_pelo_bat_dele(tmp_path, monkeypatch):
    raiz = tmp_path / "ComfyUI_windows_portable"
    (raiz / "ComfyUI").mkdir(parents=True)
    (raiz / "run_nvidia_gpu.bat").write_text("python main.py --port 8195")
    cfg = _cfg(tmp_path, monkeypatch, comfy_url="http://127.0.0.1:8188", comfy_iniciar=False,
               comfy_dir=(raiz / "ComfyUI").as_posix())
    monkeypatch.setattr(ic, "responde", lambda url: False)
    abriu = []
    monkeypatch.setattr(ic.subprocess, "Popen", lambda *a, **k: abriu.append(k.get("cwd")))
    ic.comfy_da_pessoa(cfg)
    assert json.loads((tmp_path / "config.json").read_text())["comfy_url"] == "http://127.0.0.1:8195"
    assert abriu == [raiz]


def test_segundo_motor_proprio_nao_e_tocado(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path, monkeypatch, comfy_url="http://127.0.0.1:8188",
               comfy_url_flux3="http://127.0.0.1:8189", comfy_iniciar=False)
    ic.gravar_url(cfg, "http://127.0.0.1:8000")
    salvo = json.loads((tmp_path / "config.json").read_text())
    assert (salvo["comfy_url"], salvo["comfy_url_flux3"]) == ("http://127.0.0.1:8000", "http://127.0.0.1:8189")
