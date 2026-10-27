"""Miniaturas em cache para a galeria.

Sem isso o navegador baixa 1 a 2 MB por imagem so para desenhar um quadrado de
96 px, e a galeria fica impraticavel depois de algumas dezenas de gera1coes.
"""

import asyncio
import hashlib
import io
import os
import pathlib
import shutil

from PIL import Image

import comfy

CACHE = pathlib.Path(__file__).parent / "cache_miniaturas"
LADO = 320  # cobre telas retina para uma miniatura de 96-160 px

# Uma imagem so e convertida uma vez, mesmo com varios pedidos simultaneos.
_trabalhando: dict[str, asyncio.Lock] = {}


def _caminho(nome: str, subpasta: str) -> pathlib.Path:
    chave = hashlib.sha1(f"{subpasta}/{nome}".encode()).hexdigest()
    return CACHE / f"{chave}.webp"


# Extensoes que o SaveVideo pode devolver. A miniatura de um video e um
# QUADRO dele, nao um icone generico: a galeria fica legivel.
VIDEO = (".mp4", ".webm", ".mkv", ".mov")


def tem_audio(caminho) -> bool | None:
    """O arquivo tem faixa de audio? None quando nao da para saber.

    Existe porque o `VHS_LoadVideoPath` EXPLODE ao tentar extrair audio de um
    video que nao tem: "VHS failed to extract audio from ...". Quem pede a
    saida de audio dele precisa saber antes se ela existe.

    Usa o ffprobe, que acompanha o ffmpeg. Se ele nao estiver ali, devolve
    None em vez de mentir — e quem chama decide. Nao usamos OpenCV aqui
    porque ele simplesmente nao enxerga faixas de audio.
    """
    import subprocess
    exe = shutil.which("ffprobe")
    if not exe:
        configurado = os.environ.get("FFPROBE_PATH")
        candidatos = ([pathlib.Path(configurado)] if configurado else [])
        programas = pathlib.Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        candidatos.extend((programas / "kdenlive/bin/ffprobe.exe",
                           programas / "Krita (x64)/bin/ffprobe.exe"))
        exe = next((str(p) for p in candidatos if p.is_file()), None)
    if not exe:
        return None
    try:
        saida = subprocess.run(
            [exe, "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0",
             str(caminho)],
            capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    if saida.returncode != 0:
        return None
    return "audio" in saida.stdout


def e_video(nome: str) -> bool:
    return nome.lower().endswith(VIDEO)


def _quadro_do_video(dados: bytes) -> bytes:
    """Primeiro quadro util de um video, como PNG.

    Usa OpenCV, que ja estava no projeto para a deteccao de rosto — evita
    acrescentar av ou imageio so para isto.

    Pega o quadro do DECIMO da duracao, nao o primeiro: em muitos videos o
    quadro zero e escuro ou desfocado, e a miniatura sairia inutil.
    """
    import tempfile

    import cv2
    import numpy as np

    # OpenCV nao le de memoria: precisa de arquivo. O temporario e apagado
    # logo em seguida.
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(dados)
        caminho = f.name
    try:
        cap = cv2.VideoCapture(caminho)
        if not cap.isOpened():
            raise ValueError("não consegui abrir o vídeo")
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total > 10:
            cap.set(cv2.CAP_PROP_POS_FRAMES, total // 10)
        ok, quadro = cap.read()
        cap.release()
        if not ok:
            raise ValueError("não consegui ler quadro algum")
        # OpenCV entrega BGR; o Pillow espera RGB.
        im = Image.fromarray(cv2.cvtColor(quadro, cv2.COLOR_BGR2RGB))
        saida = io.BytesIO()
        im.save(saida, "PNG")
        return saida.getvalue()
    finally:
        try:
            pathlib.Path(caminho).unlink()
        except OSError:
            pass


def dados_do_video(dados: bytes) -> dict:
    """Duracao, fps e dimensoes de um video. Zeros se nao der para ler."""
    import tempfile

    import cv2

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(dados)
        caminho = f.name
    try:
        cap = cv2.VideoCapture(caminho)
        if not cap.isOpened():
            return {"duracao": 0.0, "fps": 0.0, "largura": 0, "altura": 0}
        quadros = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        d = {"duracao": round(quadros / fps, 2) if fps else 0.0,
             "fps": round(fps, 2),
             "largura": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
             "altura": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)}
        cap.release()
        return d
    finally:
        try:
            pathlib.Path(caminho).unlink()
        except OSError:
            pass


def _reduzir(dados: bytes) -> bytes:
    with Image.open(io.BytesIO(dados)) as im:
        im = im.convert("RGB")
        im.thumbnail((LADO, LADO), Image.LANCZOS)
        saida = io.BytesIO()
        im.save(saida, "WEBP", quality=82, method=4)
        return saida.getvalue()


async def obter(nome: str, subpasta: str = "", tipo: str = "output") -> bytes:
    destino = _caminho(nome, subpasta)
    if destino.exists():
        return destino.read_bytes()

    trava = _trabalhando.setdefault(str(destino), asyncio.Lock())
    async with trava:
        if destino.exists():
            return destino.read_bytes()
        original = await comfy.imagem(nome, subpasta, tipo)
        # A conversao e trabalho de CPU; fora do laco para nao travar o servidor.
        if e_video(nome):
            quadro = await asyncio.to_thread(_quadro_do_video, original)
            pequena = await asyncio.to_thread(_reduzir, quadro)
        else:
            pequena = await asyncio.to_thread(_reduzir, original)
        CACHE.mkdir(exist_ok=True)
        destino.write_bytes(pequena)
        return pequena
