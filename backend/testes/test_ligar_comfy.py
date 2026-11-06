import asyncio

import pytest
from fastapi import HTTPException

import app
import comfy
import motores


def _preparar(monkeypatch, vivo, religa, modo="local"):
    ligou = []

    async def _vivo():
        return vivo
    monkeypatch.setattr(app, "_comfy_local_vivo", _vivo)
    monkeypatch.setattr(motores, "pode_religar", lambda: religa)
    monkeypatch.setattr(motores, "ligar", lambda: ligou.append(1) or True)
    monkeypatch.setitem(comfy.MODO, "motor", modo)
    return ligou


def test_botao_so_no_local_que_o_app_sabe_ligar(monkeypatch):
    _preparar(monkeypatch, False, True)
    assert asyncio.run(app.estado_comfy()) == {"vivo": False, "pode_ligar": True}
    _preparar(monkeypatch, False, False)
    assert asyncio.run(app.estado_comfy())["pode_ligar"] is False
    _preparar(monkeypatch, False, True, "nuvem")
    assert asyncio.run(app.estado_comfy())["pode_ligar"] is False


def test_ligar_fora_do_ar(monkeypatch):
    ligou = _preparar(monkeypatch, False, True)
    assert asyncio.run(app.ligar_comfy()) == {"ligando": True}
    assert ligou


def test_ja_ligado_nao_liga_outro(monkeypatch):
    ligou = _preparar(monkeypatch, True, True)
    assert asyncio.run(app.ligar_comfy()) == {"ligando": False}
    assert not ligou


def test_comfy_da_pessoa_e_recusado(monkeypatch):
    _preparar(monkeypatch, False, False)
    with pytest.raises(HTTPException):
        asyncio.run(app.ligar_comfy())
