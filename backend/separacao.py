"""Separar uma musica em faixas (voz, bateria, baixo...), estilo Moises.

Roda fora do ComfyUI, num ambiente Python proprio, chamado como processo.
Teste de 08/10/2026 (analises/separacao-faixas-2026-10-08): 3,5 min de
musica em 11 s com o Demucs de 6 faixas.
"""
import config
import asyncio
import json
import pathlib
import re

AMBIENTE = config.SEPARADOR_DIR
PYTHON = AMBIENTE / "Scripts" / "python.exe"
MODELOS = AMBIENTE / "modelos"
SCRIPT = pathlib.Path(__file__).parent / "separador_externo.py"

# Cada modo e um modelo. O piano do Demucs de 6 faixas e fraco (o proprio
# Demucs avisa); no teste, os teclados do lo-fi foram para "outros".
MODOS = {
    "4": ("htdemucs_ft.yaml", "4 faixas: voz, bateria, baixo e outros"),
    "6": ("htdemucs_6s.yaml", "6 faixas: acrescenta guitarra e piano"),
    "voz": ("model_bs_roformer_ep_317_sdr_12.9755.ckpt", "Voz e instrumental (karaokê)"),
}
NOMES = {"Vocals": "Voz", "Drums": "Bateria", "Bass": "Baixo", "Other": "Outros",
         "Guitar": "Guitarra", "Piano": "Piano", "Instrumental": "Instrumental"}
TEMPO_MAXIMO = 1800


def disponivel() -> dict:
    if not PYTHON.exists():
        return {"disponivel": False, "motivo": "O ambiente do separador não está instalado."}
    return {"disponivel": True, "motivo": "",
            "modos": [{"id": k, "rotulo": v[1]} for k, v in MODOS.items()]}


async def separar(entrada: pathlib.Path, modo: str, destino: pathlib.Path, base: str,
                  formato: str = "flac"):
    """Devolve [(nome_do_arquivo, nome_da_faixa)] ja renomeados em `destino`."""
    modelo = MODOS[modo][0]
    destino.mkdir(parents=True, exist_ok=True)
    temporaria = destino / "_trabalho"
    temporaria.mkdir(exist_ok=True)
    proc = await asyncio.create_subprocess_exec(
        str(PYTHON), str(SCRIPT), str(entrada), modelo, str(temporaria), str(MODELOS),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), TEMPO_MAXIMO)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError("A separação passou de 30 minutos e foi interrompida.")
    if proc.returncode != 0:
        ultima = (err.decode("utf-8", "replace").strip().splitlines() or ["sem detalhe"])[-1]
        raise RuntimeError(f"O separador falhou: {ultima}")
    arquivos = json.loads(out.decode("utf-8", "replace").strip().splitlines()[-1])["arquivos"]

    seguro = re.sub(r'[<>:"/\\|?*]+', "_", base).strip() or "musica"
    feitos = []
    for a in arquivos:
        m = re.search(r"\(([^)]+)\)", a)
        faixa = NOMES.get(m.group(1), m.group(1)) if m else "Faixa"
        n = 1
        while (destino / f"{seguro} - {faixa}_{n:03d}.{formato}").exists():
            n += 1
        final = destino / f"{seguro} - {faixa}_{n:03d}.{formato}"
        if formato == "mp3":
            # O separador grava FLAC; o MP3 sai dele a 320 kbps.
            conv = await asyncio.create_subprocess_exec(
                "ffmpeg", "-v", "error", "-y", "-i", str(temporaria / a),
                "-c:a", "libmp3lame", "-b:a", "320k", str(final),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
            _, erro = await conv.communicate()
            if conv.returncode != 0:
                raise RuntimeError("A conversão para MP3 falhou: "
                                   + erro.decode("utf-8", "replace").strip()[-200:])
            (temporaria / a).unlink()
        else:
            (temporaria / a).replace(final)
        feitos.append((final.name, faixa))
    return feitos
