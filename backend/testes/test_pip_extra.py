"""Nos com pip_extra (o Plenio: faster-whisper e a cuBLAS 12) instalam isso junto do requirements."""
import asyncio
import json
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import instalador_nos as I  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent


def test_plenio_traz_faster_whisper_e_cublas():
    nos = json.loads((RAIZ / "catalogo" / "nos.json").read_text(encoding="utf-8"))
    nos = nos["nos"] if isinstance(nos, dict) else nos
    plenio = next(n for n in nos if n["pasta"].startswith("Plenio"))
    assert any(x.startswith("faster-whisper") for x in plenio["pip_extra"])
    assert "nvidia-cublas-cu12" in plenio["pip_extra"]


def test_pip_recebe_requirements_e_extras(monkeypatch):
    chamadas = []

    class Proc:
        returncode = 0
        async def communicate(self):
            return b"ok", None

    async def falso(*args, **kw):
        chamadas.append(args)
        return Proc()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", falso)
    with tempfile.TemporaryDirectory() as d:
        pasta = pathlib.Path(d)
        (pasta / "requirements.txt").write_text("numpy\n")
        py = pasta / "python.exe"; py.write_text("")
        monkeypatch.setattr(config, "COMFY_PYTHON", py)
        asyncio.run(I._dependencias(pasta, {"pip_extra": ["faster-whisper==1.2.1", "nvidia-cublas-cu12"]}))
        args = chamadas[0]
        assert "-r" in args and "faster-whisper==1.2.1" in args and "nvidia-cublas-cu12" in args
        chamadas.clear()
        (pasta / "requirements.txt").unlink()
        asyncio.run(I._dependencias(pasta, {"pip_extra": ["nvidia-cublas-cu12"]}))
        assert "-r" not in chamadas[0] and "nvidia-cublas-cu12" in chamadas[0]


def test_etapa_pelo_tipo_do_no():
    import app as A

    class T:
        _grafo = {"5": {"class_type": "PlenioTranscribeLyrics"}, "7": {"class_type": "YuE2GenerateMusic"},
                  "9": {"class_type": "VAEDecodeTiled"}, "1": {"class_type": "UNETLoader"}, "4": {"class_type": "Algo"}}
    t = T()
    assert A._etapa_da_classe(t, "5") == "transcrevendo a letra"
    assert A._etapa_da_classe(t, "7") == "compondo e cantando"
    assert A._etapa_da_classe(t, "9") == "decodificando"
    assert A._etapa_da_classe(t, "1") == "carregando o modelo"
    assert A._etapa_da_classe(t, "4") is None
