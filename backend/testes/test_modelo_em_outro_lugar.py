"""Quem ja usa ComfyUI: o mesmo arquivo em outra subpasta conta como instalado
e o grafo passa a pedir o lugar real (pacotes.achar_em_outro_lugar/ajustar_grafo)."""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import config  # noqa: E402
import pacotes  # noqa: E402

ARQ = {"arquivo": "modelo.safetensors", "pasta": "vae", "subpasta": "LTX/2.5", "tamanho": 5}


def test_acha_pelo_nome_em_outra_subpasta(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODELOS_DIR", tmp_path)
    (tmp_path / "vae" / "meus").mkdir(parents=True)
    (tmp_path / "vae" / "meus" / "modelo.safetensors").write_bytes(b"12345")
    assert pacotes.achar_em_outro_lugar(ARQ, ["outro.safetensors", "meus\\modelo.safetensors"]) == "meus\\modelo.safetensors"


def test_tamanho_diferente_nao_conta(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "MODELOS_DIR", tmp_path)
    (tmp_path / "vae" / "meus").mkdir(parents=True)
    (tmp_path / "vae" / "meus" / "modelo.safetensors").write_bytes(b"123")
    assert pacotes.achar_em_outro_lugar(ARQ, ["meus\\modelo.safetensors"]) is None


def test_grafo_passa_a_pedir_o_lugar_real(monkeypatch):
    async def mapa():
        return {"ltx/2.5/modelo.safetensors": "meus\\modelo.safetensors"}
    monkeypatch.setattr(pacotes, "mapa_local", mapa)
    g = {"1": {"class_type": "VAELoader", "inputs": {"vae_name": "LTX\\2.5\\modelo.safetensors"}},
         "2": {"class_type": "X", "inputs": {"texto": "nada a ver"}}}
    g = asyncio.run(pacotes.ajustar_grafo(g))
    assert g["1"]["inputs"]["vae_name"] == "meus\\modelo.safetensors"
    assert g["2"]["inputs"]["texto"] == "nada a ver"
