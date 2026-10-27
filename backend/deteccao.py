"""Reconhece a tela de bloqueio que o Ideogram 4 as vezes devolve.

NAO e um filtro de conteudo sendo burlado — nao ha filtro. A tela e uma imagem
que o proprio modelo aprendeu a produzir, e ele cai nela por combinacao de seed
e condicionamento. Medido em quatro variantes do mesmo cartaz:

    original, seed nova .............. gerou
    sem quebras de linha ............. bloqueou
    sem os nomes inventados .......... gerou
    sem o bloco de creditos inteiro .. bloqueou

Tirar conteudo nao resolve e manter tudo com outra seed resolve — logo, o
gatilho nao e o que foi pedido. A saida certa e a mesma que um usuario tomaria:
gerar de novo.

A deteccao e por comparacao com uma referencia, e nao por "imagem muito lisa":
um cartaz minimalista legitimo tambem tem pouca variacao. As telas de bloqueio
sao pixel a pixel a mesma imagem — diferenca de 0,15 a 0,32 entre elas, contra
52 a 71 para qualquer imagem boa. Duas ordens de grandeza de folga.
"""

import io
import pathlib

REFERENCIA = pathlib.Path(__file__).parent / "referencias" / "ideogram_bloqueio.png"

# Bem acima do maior desvio entre duas telas de bloqueio (0,32) e bem abaixo da
# menor distancia para uma imagem boa (51,8).
LIMITE = 8.0


def _miniatura(dados: bytes):
    from PIL import Image
    import numpy as np
    im = Image.open(io.BytesIO(dados)).convert("RGB").resize((64, 64), Image.LANCZOS)
    return np.asarray(im, dtype=float)


def e_tela_de_bloqueio(dados: bytes) -> bool:
    """True se a imagem for a tela de bloqueio do Ideogram."""
    if not REFERENCIA.exists():
        return False
    try:
        import numpy as np
        ref = _miniatura(REFERENCIA.read_bytes())
        return float(np.abs(_miniatura(dados) - ref).mean()) < LIMITE
    except Exception:
        # Deteccao e conveniencia: falhar aqui nunca deve derrubar a geracao.
        return False
