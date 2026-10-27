# coding: utf-8
"""Prévia do que o espaço latente do LTX perde.

Por que existe: o método de ampliar "no latente" destrói o que for pequeno no
quadro — rosto distante, objeto miúdo. Isso foi isolado: um `encode -> decode`
pelo VAE, sem ampliar e sem amostrar nada, já derrete um rosto de ~60 px.

Por que é uma PRÉVIA e não um aviso automático: não existe, com o que há à
mão, um número confiável para prever o estrago. Três tentativas falharam e
estão registradas no NOTAS-MOTOR:

  1. detectar o rosto — o Haar cascade marcou casca de árvore;
  2. medir a perda — SSIM e nitidez separam os casos AO CONTRÁRIO;
  3. usar a métrica só para ESCOLHER ONDE olhar — ela apontou o brilho da
     jaqueta, que muda muito em número e nada aos olhos, enquanto o rosto
     derretido passou batido.

A terceira é a mais instrutiva: nem para localizar ela serve. Por isso aqui
não há recorte automático nem palpite. Devolvem-se os dois quadros inteiros,
alinhados, e quem julga é quem está olhando — que foi o que resolveu em um
segundo todas as vezes.
"""
from __future__ import annotations

import base64

import cv2

# Teto do lado maior devolvido. Alto de proposito: a tela tem uma LUPA, e para
# ela funcionar o quadro precisa chegar em resolucao real. Foi a licao da
# primeira versao — os dois quadros lado a lado, no tamanho da tela, pareciam
# iguais, porque o rosto derretido ocupava 60 px. O dano so aparece a 1:1.
LADO_MAXIMO = 1920


def _quadro(caminho: str, indice: int = 0):
    cap = cv2.VideoCapture(str(caminho))
    if indice:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(indice))
    ok, f = cap.read()
    cap.release()
    return f if ok else None


def _png(img) -> str:
    h, w = img.shape[:2]
    maior = max(h, w)
    if maior > LADO_MAXIMO:
        escala = LADO_MAXIMO / maior
        # INTER_AREA ao REDUZIR preserva o que existe sem inventar nitidez.
        img = cv2.resize(img, (int(w * escala), int(h * escala)),
                         interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise ValueError("não consegui codificar o quadro")
    return "data:image/png;base64," + base64.b64encode(buf).decode()


def comparar(caminho_antes: str, caminho_depois: str, indice_antes: int = 0,
             indice_depois: int = 0) -> dict:
    """Os dois quadros, alinhados, prontos para a tela.

    `indice_antes` existe porque a prévia carrega uma JANELA do vídeo: o
    quadro 0 do resultado corresponde ao quadro `pular` do original. Comparar
    quadros diferentes mostraria movimento, não perda — e o movimento é
    convincente o bastante para enganar quem estiver olhando rápido.
    """
    antes = _quadro(caminho_antes, indice_antes)
    depois = _quadro(caminho_depois, indice_depois)
    if antes is None or depois is None:
        raise ValueError("não consegui ler os quadros para comparar")
    if depois.shape != antes.shape:
        depois = cv2.resize(depois, (antes.shape[1], antes.shape[0]))
    return {
        "antes": _png(antes),
        "depois": _png(depois),
        "tamanho": {"largura": int(antes.shape[1]), "altura": int(antes.shape[0])},
    }
