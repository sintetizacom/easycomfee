import asyncio

import httpx

import config
import instalador


ARQ = {"arquivo": "x.safetensors", "pasta": "loras", "subpasta": "LTX/2.5",
       "repo": "r/r", "caminho": "x.safetensors", "tamanho": 10, "opcional": False}


def _cliente(responder):
    return httpx.AsyncClient(transport=httpx.MockTransport(responder))


def teste_baixa_na_subpasta_que_o_grafo_pede(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODELOS_DIR", tmp_path)
    async def rodar():
        async with _cliente(lambda p: httpx.Response(200, content=b"0123456789")) as c:
            await instalador._baixar(c, ARQ, 0)
    asyncio.run(rodar())
    assert (tmp_path / "loras/LTX/2.5/x.safetensors").read_bytes() == b"0123456789"
    assert not (tmp_path / "loras/LTX/2.5/x.safetensors.part").exists()


def teste_continua_de_onde_parou(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODELOS_DIR", tmp_path)
    parcial = tmp_path / "loras/LTX/2.5/x.safetensors.part"
    parcial.parent.mkdir(parents=True)
    parcial.write_bytes(b"01234")
    pedidos = []
    def responder(p):
        pedidos.append(p.headers.get("Range"))
        return httpx.Response(206, content=b"56789")
    async def rodar():
        async with _cliente(responder) as c:
            await instalador._baixar(c, ARQ, 0)
    asyncio.run(rodar())
    assert pedidos == ["bytes=5-"]
    assert (tmp_path / "loras/LTX/2.5/x.safetensors").read_bytes() == b"0123456789"


def teste_arquivo_incompleto_nao_vira_modelo(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODELOS_DIR", tmp_path)
    async def rodar():
        async with _cliente(lambda p: httpx.Response(200, content=b"012")) as c:
            await instalador._baixar(c, ARQ, 0)
    try:
        asyncio.run(rodar())
        assert False, "deveria falhar"
    except RuntimeError:
        pass
    assert not (tmp_path / "loras/LTX/2.5/x.safetensors").exists()


def teste_extrair_tensores_copia_so_os_prefixos(tmp_path):
    import json, struct
    import instalador
    dados = {"a.x": b"\x01" * 8, "b.y": b"\x02" * 4, "a.z": b"\x03" * 4}
    cab, pos = {"__metadata__": {"_quantization_metadata": json.dumps(
        {"format_version": "1.0", "layers": {"a.x": {}, "b.y": {}}})}}, 0
    for k, v in dados.items():
        cab[k] = {"dtype": "U8", "shape": [len(v)], "data_offsets": [pos, pos + len(v)]}
        pos += len(v)
    texto = json.dumps(cab).encode()
    origem = tmp_path / "o.safetensors"
    origem.write_bytes(struct.pack("<Q", len(texto)) + texto + b"".join(dados.values()))
    final = tmp_path / "f.safetensors"
    instalador.extrair_tensores(origem, final, ["a."])
    bruto = final.read_bytes()
    n = struct.unpack("<Q", bruto[:8])[0]
    novo = json.loads(bruto[8:8 + n])
    assert set(novo) == {"__metadata__", "a.x", "a.z"}
    assert json.loads(novo["__metadata__"]["_quantization_metadata"])["layers"] == {"a.x": {}}
    corpo = bruto[8 + n:]
    for k in ("a.x", "a.z"):
        a, b = novo[k]["data_offsets"]
        assert corpo[a:b] == dados[k]
