import json

import pytest

import detectar_comfy as dc


@pytest.fixture
def app(tmp_path, monkeypatch):
    """%APPDATA% de mentira, com a pasta do Comfy Desktop."""
    monkeypatch.setenv("APPDATA", str(tmp_path))
    pasta = tmp_path / "Comfy Desktop"
    pasta.mkdir()
    return pasta


NUVEM = {"id": "inst-1", "name": "Comfy Cloud", "sourceId": "cloud", "status": "installed",
         "remoteUrl": "https://cloud.comfy.org/"}


def _instalacao(tmp_path, porta=None):
    """Como numa instalacao real: <installPath>\\ComfyUI com main.py, comfy e models."""
    raiz = tmp_path / "Installs" / "ComfyUI"
    (raiz / "ComfyUI" / "comfy").mkdir(parents=True)
    (raiz / "ComfyUI" / "models").mkdir()
    (raiz / "ComfyUI" / "main.py").write_text("")
    if porta:
        procs = tmp_path / "Comfy Desktop" / "comfy-procs"
        procs.mkdir()
        (procs / "inst-2.json").write_text(json.dumps({"port": porta}))
    return {"id": "inst-2", "name": "ComfyUI", "sourceId": "standalone", "status": "installed",
            "installPath": str(raiz)}


def test_so_nuvem(app):
    (app / "installations.json").write_text(json.dumps([NUVEM]))
    assert dc._comfy_desktop() == []
    assert dc.so_comfy_cloud()


def test_instalacao_local_com_pastas_compartilhadas(app, tmp_path):
    inst = _instalacao(tmp_path, porta=8190)
    (app / "installations.json").write_text(json.dumps([inst, NUVEM]))
    (app / "settings.json").write_text(json.dumps({
        "modelsDirs": ["D:\\Shared\\models"], "inputDir": "D:\\Shared\\input", "outputDir": "D:\\Shared\\output"}))
    a, = dc._comfy_desktop()
    assert a["pasta"].name == "ComfyUI" and a["pasta"].parent.name == "ComfyUI"
    assert a["url"] == "http://127.0.0.1:8190"
    assert set(a["pastas"]) == {"modelos_dir", "comfy_entrada", "comfy_saida"}
    assert not dc.so_comfy_cloud()


def test_porta_padrao_sem_comfy_procs(app, tmp_path):
    (app / "installations.json").write_text(json.dumps([_instalacao(tmp_path)]))
    assert dc._comfy_desktop()[0]["url"] == "http://127.0.0.1:8188"


def test_arquivos_ausentes(app):
    assert dc._comfy_desktop() == []
    assert not dc.so_comfy_cloud()


@pytest.mark.parametrize("texto", ["{ quebrado", "{}", "[1, null]"])
def test_json_invalido(app, texto):
    (app / "installations.json").write_text(texto)
    (app / "settings.json").write_text(texto)
    assert dc._comfy_desktop() == []
    assert not dc.so_comfy_cloud()


def test_gravar_so_nuvem(tmp_path, monkeypatch):
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"comfy_dir": "C:/x", "comfy_iniciar": False, "app_porta": 8600}))
    monkeypatch.setattr(dc, "CONFIG", config)
    monkeypatch.setattr(dc, "EXEMPLO", tmp_path / "nao-existe.json")
    dc._gravar_so_nuvem()
    salvo = json.loads(config.read_text())
    assert salvo["comfy_dir"] == "" and "comfy_iniciar" not in salvo and salvo["app_porta"] == 8600


def _comfy(raiz):
    (raiz / "comfy").mkdir(parents=True)
    (raiz / "models" / "checkpoints").mkdir(parents=True)
    (raiz / "main.py").write_text("")
    return raiz


def test_comfy_aberto_diz_a_pasta(tmp_path, monkeypatch):
    raiz = _comfy(tmp_path / "qualquer" / "ComfyUI")
    respostas = {"http://127.0.0.1:8190/system_stats": {"system": {}},
                 "http://127.0.0.1:8190/internal/folder_paths": {
                     "custom_nodes": ["D:/outro"], "checkpoints": ["F:/modelos/checkpoints", str(raiz / "models" / "checkpoints")]}}
    monkeypatch.setattr(dc, "_perguntar", respostas.get)
    a, = dc._comfy_aberto()
    assert (a["pasta"], a["url"]) == (raiz, "http://127.0.0.1:8190")


def test_comfy_aberto_sem_resposta_util(monkeypatch):
    monkeypatch.setattr(dc, "_perguntar", lambda url: {"system": {}} if url.endswith("stats") else None)
    assert dc._comfy_aberto() == []


def test_pasta_digitada(tmp_path):
    raiz = _comfy(tmp_path / "Portatil" / "ComfyUI")
    assert dc.pasta_digitada(str(raiz)) == raiz
    assert dc.pasta_digitada(f'"{raiz.parent}"') == raiz
    assert dc.pasta_digitada(str(tmp_path)) is None
