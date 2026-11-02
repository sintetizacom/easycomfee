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


# Pelo ComfyUI (Plenio, no segundo motor): 4 faixas com o BS-RoFormer. O "rest"
# (o que o modelo nao pegou) vai junto com "outros": somadas, as faixas devolvem
# a musica. Cada faixa e um Stem Mixer com o solo dela e um SaveAudio (FLAC).
MODELO_PLENIO = "model_bs_roformer_ep_17_sdr_9.6568.ckpt"
FAIXAS_PLENIO = {"vocals": "Voz", "drums": "Bateria", "bass": "Baixo", "other": "Outros"}


def plenio_disponivel() -> dict:
    if not (config.MODELOS_DIR / "audio_separation" / MODELO_PLENIO).exists():
        return {"disponivel": False,
                "motivo": "Install the stem separation model in Config Models (Music)."}
    return {"disponivel": True, "motivo": ""}


def grafo_plenio(entrada: str) -> dict:
    g = {
        "entrada": {"class_type": "LoadAudio", "inputs": {"audio": entrada}},
        "modelo": {"class_type": "PlenioAudioModelLoader",
                   "inputs": {"kind": "separation", "kind.model": MODELO_PLENIO}},
        "separa": {"class_type": "PlenioSeparateStems",
                   "inputs": {"audio": ["entrada", 0], "model": ["modelo", 0]}},
    }
    for faixa in FAIXAS_PLENIO:
        solo = {faixa: {"solo": True}} | ({"rest": {"solo": True}} if faixa == "other" else {})
        g[f"mix_{faixa}"] = {"class_type": "PlenioStemMixer", "inputs": {
            "stems": ["separa", 0],
            "mix": json.dumps({"schema": "plenio.stem_mix/1", "strips": solo})}}
        g[f"salva_{faixa}"] = {"class_type": "SaveAudio", "inputs": {
            "audio": [f"mix_{faixa}", 0], "filename_prefix": f"_separar/{faixa}"}}
    return g


async def gravar_plenio(saidas: dict, ler, destino: pathlib.Path, base: str,
                        formato: str = "flac"):
    """As faixas que o grafo salvou, renomeadas em `destino` (e em MP3, se pedido).
    `ler(nome, subpasta)` devolve os bytes de um arquivo de saida do motor."""
    destino.mkdir(parents=True, exist_ok=True)
    seguro = re.sub(r'[<>:"/\|?*]+', "_", base).strip() or "musica"
    feitos = []
    for chave, faixa in FAIXAS_PLENIO.items():
        audio = (saidas.get(f"salva_{chave}") or {}).get("audio") or []
        if not audio:
            continue
        dados = await ler(audio[0]["filename"], audio[0].get("subfolder", ""))
        n = 1
        while (destino / f"{seguro} - {faixa}_{n:03d}.{formato}").exists():
            n += 1
        final = destino / f"{seguro} - {faixa}_{n:03d}.{formato}"
        if formato == "mp3":
            conv = await asyncio.create_subprocess_exec(
                "ffmpeg", "-v", "error", "-y", "-f", "flac", "-i", "pipe:0",
                "-c:a", "libmp3lame", "-b:a", "320k", str(final),
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE)
            _, erro = await conv.communicate(dados)
            if conv.returncode != 0:
                raise RuntimeError("A conversão para MP3 falhou: "
                                   + erro.decode("utf-8", "replace").strip()[-200:])
        else:
            final.write_bytes(dados)
        feitos.append((final.name, faixa))
    return feitos
