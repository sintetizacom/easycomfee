import asyncio

import app
import chaves
import comfy
import config


def _motor(monkeypatch, comfy_dir, chave):
    gravados = []
    monkeypatch.setattr(config, "COMFY_DIR", comfy_dir)
    monkeypatch.setattr(chaves, "chave", lambda: chave)
    monkeypatch.setattr(comfy, "_gravar_preferencias", lambda **k: gravados.append(k))
    monkeypatch.setitem(comfy.MODO, "motor", "local")
    return asyncio.run(app.motor_atual())["modo"]


def test_so_nuvem_com_chave_vai_para_a_nuvem(monkeypatch):
    assert _motor(monkeypatch, None, "k") == "nuvem"


def test_so_nuvem_sem_chave_fica_local(monkeypatch):
    assert _motor(monkeypatch, None, None) == "local"


def test_comfy_local_nao_troca_sozinho(monkeypatch):
    assert _motor(monkeypatch, "C:/x", "k") == "local"
