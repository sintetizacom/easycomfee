"""Download que cai no meio: o instalador tenta de novo sozinho e continua do .part."""
import asyncio

import httpx

import instalador as ins

DADOS = bytes(range(256)) * 400  # 100 KB


def _servidor(quedas: list[int]):
    """Cai (fecha a conexao) nas primeiras len(quedas) respostas, depois de mandar N bytes."""
    def tratar(req: httpx.Request):
        ini = int(req.headers.get("range", "bytes=0-")[6:].rstrip("-") or 0)
        corpo = DADOS[ini:]
        if quedas:
            corpo = corpo[:quedas.pop(0)]
        return httpx.Response(206 if ini else 200, content=corpo)
    return httpx.MockTransport(tratar)


def test_continua_depois_de_cair(tmp_path, monkeypatch):
    monkeypatch.setattr(ins, "destino", lambda arq: tmp_path / "m.gguf")
    monkeypatch.setattr(ins, "ESPERA", (0,))
    monkeypatch.setattr(ins.pacotes, "url_download", lambda arq: "https://x/m.gguf")
    monkeypatch.setattr(ins, "_cabecalhos", lambda: {})
    arq = {"arquivo": "m.gguf", "tamanho": len(DADOS), "repo": "r"}

    async def rodar():
        async with httpx.AsyncClient(transport=_servidor([30_000, 25_000])) as c:
            await ins._baixar_insistindo(c, arq, 0)
    asyncio.run(rodar())
    assert (tmp_path / "m.gguf").read_bytes() == DADOS
    assert not (tmp_path / "m.gguf.part").exists()


def test_part_ja_completo_so_termina(tmp_path, monkeypatch):
    monkeypatch.setattr(ins, "destino", lambda arq: tmp_path / "m.gguf")
    (tmp_path / "m.gguf.part").write_bytes(DADOS)
    arq = {"arquivo": "m.gguf", "tamanho": len(DADOS), "repo": "r"}
    asyncio.run(ins._baixar(None, arq, 0))
    assert (tmp_path / "m.gguf").read_bytes() == DADOS
