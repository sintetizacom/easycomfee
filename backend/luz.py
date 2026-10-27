"""Mapa de direcao de luz.

Desenha uma esfera cinza iluminada de uma direcao. E a representacao que o
widget 3D mostra e, ao mesmo tempo, a imagem enviada ao modelo como segunda
referencia — tem uma implementacao so para os dois usos nao divergirem.

Nota honesta sobre o alcance disto: nos testes o modelo lê bem a direcao
horizontal do mapa e mal a altura. O mapa ajuda, mas nao e controle fisico de
luz. Ver README.
"""

import hashlib
import io
import math
import pathlib

import numpy as np
from PIL import Image

CACHE = pathlib.Path(__file__).parent / "cache_luz"
LADO = 512

# Temperatura de cor -> multiplicador RGB aproximado. Serve para o mapa mostrar
# a cor que o prompt vai pedir, e nao so um cinza.
TEMPERATURAS = {
    "quente": (1.00, 0.82, 0.62),
    "neutra": (1.00, 1.00, 1.00),
    "fria": (0.72, 0.85, 1.00),
}


def direcao(azimute: float, elevacao: float) -> tuple[float, float, float]:
    """Vetor da luz. Azimute 0 = de frente, positivo para a direita."""
    az, el = math.radians(azimute), math.radians(elevacao)
    return (math.cos(el) * math.sin(az), math.sin(el), math.cos(el) * math.cos(az))


def desenhar(azimute: float, elevacao: float, intensidade: float = 1.0,
             temperatura: str = "neutra", lado: int = LADO) -> bytes:
    """PNG da esfera iluminada. Vetorizado: o widget pede isto a cada arrasto."""
    lx, ly, lz = direcao(azimute, elevacao)
    eixo = np.linspace(-1.0, 1.0, lado, dtype=np.float32)
    dx = eixo[None, :]
    dy = -eixo[:, None]

    raio2 = dx * dx + dy * dy
    dentro = raio2 <= 1.0
    nz = np.sqrt(np.clip(1.0 - raio2, 0.0, None))

    # Lambert puro, com um gama para a esfera nao ficar chapada demais.
    luz = np.clip(dx * lx + dy * ly + nz * lz, 0.0, None) ** 0.85
    valor = np.clip(0.04 + 0.96 * luz * intensidade, 0.0, 1.0)

    r, g, b = TEMPERATURAS.get(temperatura, TEMPERATURAS["neutra"])
    fundo = 0.06
    canais = [np.where(dentro, valor * c, fundo) for c in (r, g, b)]
    img = (np.stack(canais, axis=-1) * 255).astype(np.uint8)

    saida = io.BytesIO()
    Image.fromarray(img, "RGB").save(saida, "PNG")
    return saida.getvalue()


def arquivo(azimute: float, elevacao: float, intensidade: float,
            temperatura: str) -> pathlib.Path:
    """Grava o mapa em disco e devolve o caminho, reaproveitando o que ja existe."""
    chave = hashlib.sha1(
        f"{azimute:.1f}|{elevacao:.1f}|{intensidade:.2f}|{temperatura}".encode()
    ).hexdigest()[:16]
    CACHE.mkdir(exist_ok=True)
    destino = CACHE / f"luz_{chave}.png"
    if not destino.exists():
        destino.write_bytes(desenhar(azimute, elevacao, intensidade, temperatura))
    return destino


def em_palavras(azimute: float, elevacao: float, intensidade: float,
                temperatura: str) -> str:
    """Traduz a posicao para a frase que vai no prompt.

    O modelo entende texto muito melhor que o mapa, entao esta e a parte que
    mais carrega o resultado. O mapa entra como reforco.
    """
    az = (azimute + 180) % 360 - 180
    if abs(az) <= 20:
        lado = "directly in front of the subject"
    elif abs(az) >= 160:
        lado = "from directly behind the subject, rimming the edges"
    elif az > 0:
        lado = ("from the right side" if az >= 65
                else "from the front right, about 45 degrees off axis")
    else:
        lado = ("from the left side" if az <= -65
                else "from the front left, about 45 degrees off axis")

    if elevacao >= 55:
        altura = "high above, almost overhead, casting short downward shadows"
    elif elevacao >= 20:
        altura = "above eye level, angled down"
    elif elevacao > -20:
        altura = "at eye level"
    elif elevacao > -50:
        altura = "from below eye level, angled up"
    else:
        altura = "from far below, lighting the face from underneath"

    if intensidade >= 1.15:
        forca = "hard and bright, with deep contrast and defined shadows"
    elif intensidade >= 0.8:
        forca = "firm but natural"
    elif intensidade >= 0.5:
        forca = "soft and diffused, with gentle falloff"
    else:
        forca = "very dim and moody, mostly shadow"

    cor = {"quente": "warm golden", "fria": "cool blue-white",
           "neutra": "neutral white"}.get(temperatura, "neutral white")

    # MEDIDO: "The key light comes from the right side" nao move a luz. Com a
    # base iluminada pela esquerda (diferenca esquerda-direita de +41,2 em
    # brilho medio dos tercos laterais), azimute -90 e +90 devolveram +37,1 e
    # +38,2 — a mesma coisa, e praticamente o original. As instrucoes saiam
    # corretas e diferentes; o modelo e que ignorava.
    #
    # Duas trocas resolveram, medidas com a mesma seed:
    #
    #   frase atual ................................ +4,7  (so apagou a direcao)
    #   descrever a FONTE naquele lado ............. -14,5  (virou)
    #   remover a luz original + descrever a fonte . -36,4  (virou forte)
    #
    # Faz sentido com o exemplo do autor da LoRA, que descreve o TIPO de fonte
    # ("luz suave difusa por cortinas"), nunca uma posicao abstrata. Ela
    # responde a fonte, nao a coordenada.
    sombra = {"from the right side": "to the left",
              "from the front right, about 45 degrees off axis": "back and to the left",
              "from the left side": "to the right",
              "from the front left, about 45 degrees off axis": "back and to the right",
              "from directly behind the subject, rimming the edges": "toward the camera",
              "directly in front of the subject": "straight back behind the subject",
              }.get(lado, "away from the light")

    return (f"Remove the original lighting of the image and relight it with a "
            f"single {cor} light source placed {lado}, {altura}. The light is "
            f"{forca}, and it throws the shadows {sombra}.")
