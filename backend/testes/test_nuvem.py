import asyncio

import config
import nuvem

NOS = {"UNETLoader", "LoadImage", "SaveVideo"}
MODELOS = {"modelo.safetensors": "modelo.safetensors"}


def teste_conferir_aponta_no_e_modelo_que_faltam():
    g = {"1": {"class_type": "UNETLoader", "inputs": {"unet_name": "LTX/2.5/modelo.safetensors"}},
         "2": {"class_type": "NoDaMaquina", "inputs": {"x": "LTX/2.5/outro.safetensors"}}}
    assert nuvem.conferir(g, NOS, MODELOS) == ["modelo outro.safetensors", "no NoDaMaquina"]


def teste_preparar_traduz_modelo_e_sobe_entrada(tmp_path, monkeypatch):
    (tmp_path / "foto.png").write_bytes(b"png")
    monkeypatch.setattr(config, "COMFY_ENTRADA", tmp_path)
    async def capacidades(forcar=False):
        return NOS, MODELOS
    async def subir(c, caminho):
        return "enviada_" + caminho.name
    monkeypatch.setattr(nuvem, "capacidades", capacidades)
    monkeypatch.setattr(nuvem, "_subir", subir)
    g = {"1": {"class_type": "UNETLoader", "inputs": {"unet_name": "LTX\2.5\modelo.safetensors"}},
         "2": {"class_type": "LoadImage", "inputs": {"image": "foto.png"}}}
    pronto = asyncio.run(nuvem.preparar(g))
    assert pronto["1"]["inputs"]["unet_name"] == "modelo.safetensors"
    assert pronto["2"]["inputs"]["image"] == "enviada_foto.png"
    assert g["1"]["inputs"]["unet_name"].startswith("LTX")  # original intacto


def teste_preparar_recusa_antes_de_enviar(monkeypatch):
    async def capacidades(forcar=False):
        return NOS, MODELOS
    monkeypatch.setattr(nuvem, "capacidades", capacidades)
    g = {"1": {"class_type": "NoDaMaquina", "inputs": {}}}
    try:
        asyncio.run(nuvem.preparar(g))
        assert False
    except nuvem.IndisponivelNaNuvem as e:
        assert "NoDaMaquina" in str(e)
