"""Relight (LTX-2.3 IC-LoRA Relight): a "bola de luz" que o LoRA le em cada quadro.

Cartao do modelo: um quadrado cinza neutro (RGB 173) de 143 px num quadro de 1280x704,
a 22 px do topo e da direita; dentro dele, uma esfera fosca na metade de cima, com
cerca de 1/3 da largura, iluminada da direcao pedida e com a sombra do lado oposto.
A bola entra POR ULTIMO, depois de toda escala: o video sai do ffmpeg ja no tamanho
que o grafo usa. Testado com o modelo em 02/11/2026.
"""
import math
import pathlib
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

_SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

LUZES = ["hard directional sunlight", "hard high-angle sunlight", "hard low-angle sunlight",
         "soft diffused daylight", "soft warm afternoon light", "cool soft daylight",
         "dim overcast light", "strong backlight with rim light", "soft hazy backlight",
         "warm golden low front sun", "warm golden low side sun", "frontal sunlight"]
# Direcao -> angulo da bola (0 = de frente para a camera, 90 = da direita).
DIRECOES = {"the front": 0, "the front-right": 45, "the right": 90, "the back-right": 135,
            "behind": 180, "the back-left": 225, "the left": 270, "the front-left": 315}
# Altura do sol pela luz (o cartao separa baixo < 33 graus, medio e alto >= 58).
_ALTURA = {"hard high-angle sunlight": 70, "hard low-angle sunlight": 18, "warm golden low front sun": 15,
           "warm golden low side sun": 15}


def texto(luz: str, direcao: str) -> str:
    return f"relight the video to match the light-direction ball. {luz} from {direcao}"


def bola(lado: int, direcao: str, luz: str) -> Image.Image:
    """O quadrado cinza com a esfera iluminada, `lado` x `lado` px."""
    escala = 4  # desenha grande e reduz: borda lisa
    n = lado * escala
    img = Image.new("RGB", (n, n), (173, 173, 173))
    az = math.radians(DIRECOES[direcao])
    el = math.radians(_ALTURA.get(luz, 45))
    # Luz no espaco da camera: x para a direita, y para cima, z para a camera.
    lx, ly, lz = math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el)
    r = n / 6
    cx, cy = n / 2, n * 0.36
    # Sombra no chao, do lado oposto a luz (para tras da bola = para cima na imagem).
    comp = r * (0.6 + 1.6 * math.cos(el))
    sx, sy = cx - math.sin(az) * comp, cy + r * 0.9 - math.cos(az) * comp * 0.45
    sombra = Image.new("L", (n, n), 0)
    ImageDraw.Draw(sombra).ellipse((sx - r * 1.1, sy - r * 0.35, sx + r * 1.1, sy + r * 0.35), fill=120)
    sombra = sombra.filter(ImageFilter.GaussianBlur(r * 0.25))
    img = Image.composite(Image.new("RGB", (n, n), (110, 110, 110)), img, sombra)
    # Esfera fosca (Lambert) com um pouco de luz ambiente.
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    nx, ny = (xx - cx) / r, -(yy - cy) / r
    dentro = nx ** 2 + ny ** 2 <= 1
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))
    brilho = np.clip(nx * lx + ny * ly + nz * lz, 0, 1) * 0.85 + 0.12
    arr = np.asarray(img).astype(np.float32)
    arr[dentro] = (brilho[dentro] * 235)[:, None]
    return Image.fromarray(arr.clip(0, 255).astype(np.uint8)).resize((lado, lado), Image.LANCZOS)


def preparar(dados: bytes, largura: int, altura: int, quadros: int, direcao: str, luz: str) -> bytes:
    """O video a 24 fps, no tamanho do grafo (escala ate cobrir e corte no centro),
    com a bola no canto superior direito. Devolve o mp4."""
    lado = max(48, round(143 * largura / 1280))
    margem = max(8, round(22 * largura / 1280))
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        (d / "e.mp4").write_bytes(dados)
        bola(lado, direcao, luz).save(d / "bola.png")
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(d / "e.mp4"), "-i", str(d / "bola.png"),
             "-filter_complex",
             f"[0:v]fps=24,scale={largura}:{altura}:force_original_aspect_ratio=increase:flags=lanczos,"
             f"crop={largura}:{altura},setsar=1[v];[v][1:v]overlay=W-w-{margem}:{margem}",
             "-frames:v", str(quadros), "-map", "0:a?", "-c:a", "aac",
             "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", str(d / "s.mp4")],
            capture_output=True, text=True, timeout=600, creationflags=_SEM_JANELA)
        if r.returncode:
            raise RuntimeError(r.stderr.strip()[-300:])
        return (d / "s.mp4").read_bytes()
