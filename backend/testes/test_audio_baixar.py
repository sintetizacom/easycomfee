"""Download de musica/voz em MP3 ou FLAC (/api/audio/baixar), convertido na hora."""
import asyncio
import pathlib
import subprocess
import sys
import tempfile

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import app as A  # noqa: E402
import comfy  # noqa: E402


def _flac() -> bytes:
    with tempfile.TemporaryDirectory() as d:
        f = pathlib.Path(d) / "s.flac"
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                        "-c:a", "flac", str(f)], check=True)
        return f.read_bytes()


def test_baixar_mp3_e_flac(monkeypatch):
    original = _flac()

    async def falso(nome, subpasta, tipo):
        return original
    monkeypatch.setattr(comfy, "imagem", falso)

    async def pedir(formato):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=A.app),
                                     base_url="http://127.0.0.1:8600") as c:
            return await c.get("/api/audio/baixar", params={"nome": "musica_00001_.flac", "subpasta": "audio", "formato": formato})
    mp3 = asyncio.run(pedir("mp3"))
    assert mp3.status_code == 200 and mp3.headers["content-type"] == "audio/mpeg"
    assert 'filename="musica_00001_.mp3"' in mp3.headers["content-disposition"]
    assert mp3.content[:3] == b"ID3" or mp3.content[0] == 0xFF
    flac = asyncio.run(pedir("flac"))
    assert flac.status_code == 200 and flac.content == original  # ja era FLAC: vai como esta
    assert asyncio.run(pedir("wav")).status_code == 422
