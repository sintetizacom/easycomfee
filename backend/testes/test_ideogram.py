# -*- coding: utf-8 -*-
"""Testes dos guardas da caption do Ideogram 4.

Nao usam GPU nem motor: sao funcoes puras sobre o JSON de layout. Rodar com

    backend\\.venv\\Scripts\\python.exe backend\\testes\\test_ideogram.py

CADA CASO AQUI E UMA FALHA QUE JA ACONTECEU numa geracao real, e o nome diz
qual. Se um deles quebrar, o defeito correspondente voltou.

Uma licao registrada em codigo: estes testes passaram 7/7 numa versao em que o
guarda de eixos estava, na pratica, desligado — o `desc` inventado no teste nao
tinha a expressao "stacked vertically" que o LLM de verdade escreve. Teste
unitario verde nao substitui uma geracao real; ele so impede a regressao do que
ja foi visto.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import ideogram as I  # noqa: E402

_falhas = []


def conferir(nome, obtido, esperado):
    if obtido != esperado:
        _falhas.append(f"{nome}: esperado {esperado!r}, obtido {obtido!r}")


def caption(elementos, fundo=""):
    return {"high_level_description": "x",
            "compositional_deconstruction": {"background": fundo,
                                             "elements": elementos}}


# --------------------------------------------------------------------------
# Fundo: o cartaz de cinema saiu com o xadrez do Photoshop PINTADO nos pixels
# porque o campo `background` tinha tres palavras. O arquivo era RGB, sem alfa.
# --------------------------------------------------------------------------
def teste_fundo_fraco():
    for texto in ["gray-ice background", "black backdrop", "",
                  "A plain white background", "transparent background"]:
        conferir(f"fundo fraco {texto!r}", I._fundo_e_fraco(texto), True)
    for texto in ["A weathered brick wall lit from the left, warm tone, shallow depth",
                  "dark wood surface with natural grain and matte finish"]:
        conferir(f"fundo descrito {texto[:24]!r}", I._fundo_e_fraco(texto), False)


def teste_transparente_nao_e_cor():
    # Deixar passar produzia "a solid, evenly printed transparent field, flat
    # and opaque" — contradicao, e o xadrez voltava.
    novo = I._corrigir_fundo(caption([], "transparent background"),
                             "cartaz, paleta preta e laranja")
    fundo = novo["compositional_deconstruction"]["background"]
    conferir("sem 'transparent' no fundo reescrito",
             "transparent" in fundo.lower(), False)
    # Negacao nomeia o que proibe: o modelo desenha o xadrez se ele for citado.
    conferir("sem negacao no fundo reescrito",
             any(p in fundo.lower() for p in ("no pattern", "no checkerboard")),
             False)


def teste_cor_de_fundo_nao_briga_com_o_texto():
    pretos = [{"type": "text", "desc": "large black uppercase letters"},
              {"type": "text", "desc": "small orange text"}]
    # Paleta inteira em uso pelo texto: fundo preto deixaria titulo preto sobre
    # preto, e laranja deixaria as aberturas vermelhas sobre laranja.
    cor = I._cor_de_fundo("cartaz, paleta preta e laranja", pretos)
    conferir("fundo nao repete cor de texto", cor in ("black", "orange"), False)
    conferir("so preto no texto -> laranja",
             I._cor_de_fundo("cartaz, paleta preta e laranja",
                             [{"type": "text", "desc": "black"}]), "orange")


def teste_cor_do_fundo_e_nao_do_objeto():
    # "barco vermelho, fundo cinza-gelo" escolhia vermelho: a cor do barco,
    # porque era a primeira da frase. Em portugues o adjetivo vem DEPOIS.
    conferir("cor ancorada em 'fundo'",
             I._cores_da_ideia("barco vermelho sobre fundo cinza-gelo")[0], "grey")
    conferir("cor ancorada em 'paleta'",
             I._cores_da_ideia("cartaz, paleta preta e laranja")[0], "black")


# --------------------------------------------------------------------------
# Eixos: o LLM emite [x1,y1,x2,y2] em vez de [y1,x1,y2,x2] e a peca sai girada.
# --------------------------------------------------------------------------
DESC_CAFE = ("Text in black serif font, stacked vertically, centered on the "
             "label. All text is uppercase.")


def teste_um_bloco_de_texto_girado():
    # A embalagem SERRA ALTA tinha UM elemento de texto, e a regra por maioria
    # exigia dois: a peca passava batido e saia com o rotulo deitado.
    e = {"bbox": [200, 200, 700, 300], "desc": DESC_CAFE,
         "text": "SERRA ALTA\nTORRA MÉDIA\nORIGEM: MANTIQUEIRA"}
    conferir("rotulo do cafe vira", I._pede_virar(e), True)


def teste_empilhado_nao_e_girado():
    # "stacked vertically" sao LINHAS empilhadas, layout normal. Ler isso como
    # "texto girado" desligava o guarda — e desligou, numa geracao inteira.
    for desc, vira in [("three lines vertically stacked", True),
                       ("label centered vertically on the bag", True),
                       ("vertical text along the spine", False),
                       ("text rotated 90 degrees", False),
                       ("the word runs vertically up the side", False),
                       ("vertical banner on the right edge", False)]:
        # O texto e o do rotulo do cafe de proposito: com linhas curtas
        # ("UM/DOIS/TRES") a caixa alta ate serve, e o guarda corretamente nao
        # vira — o que testaria o regex errado.
        e = {"bbox": [200, 200, 700, 300], "desc": desc,
             "text": "SERRA ALTA\nTORRA MÉDIA\nORIGEM: MANTIQUEIRA"}
        conferir(f"desc {desc!r}", I._pede_virar(e), vira)


def teste_caixa_correta_fica_como_esta():
    e = {"bbox": [40, 40, 300, 960], "desc": "condensed",
         "text": "ORQUESTRA DE FERRO"}
    conferir("caixa ja larga nao vira", I._pede_virar(e), False)


# --------------------------------------------------------------------------
# Placeholders: "BANDA 1 / BANDA 2 / BANDA 3" foram IMPRESSAS no cartaz.
# --------------------------------------------------------------------------
def teste_placeholders():
    for t in ["BANDA 1", "banda 2", "TEXTO", "Título 3", "Lorem ipsum dolor",
              "LEGENDA", "chamada 1", "xxx"]:
        conferir(f"placeholder {t!r}", I._e_placeholder(t), True)
    for t in ["ORQUESTRA DE FERRO", "14 DE MARÇO", "TEATRO MUNICIPAL", "NOVA",
              "SERRA ALTA", "CIDADES QUE RESPIRAM", "BANDA LARGA",
              "NOME DA RUA 7"]:
        conferir(f"conteudo real {t!r}", I._e_placeholder(t), False)


# --------------------------------------------------------------------------
# Margem: "ORQUESTRA DE FERRO" saia "RQUESTRA DE FERR", duas rodadas seguidas.
# --------------------------------------------------------------------------
def teste_margem():
    c = caption([{"type": "text", "bbox": [0, 0, 300, 1000], "text": "T"},
                 {"type": "text", "bbox": [320, 120, 400, 880], "text": "ja tem"},
                 {"type": "obj", "bbox": [0, 0, 1000, 1000], "desc": "sangrada"}])
    els = I._dar_margem(c)["compositional_deconstruction"]["elements"]
    conferir("texto colado na borda recua", els[0]["bbox"], [40, 40, 300, 960])
    conferir("texto com folga nao muda", els[1]["bbox"], [320, 120, 400, 880])
    conferir("ilustracao pode sangrar", els[2]["bbox"], [0, 0, 1000, 1000])


# --------------------------------------------------------------------------
# Ocupar a pagina: as seis caixas do cartaz de show paravam na altura 800.
# No cartaz de cinema o vazio embaixo e espaco negativo deliberado.
# --------------------------------------------------------------------------
def teste_ocupar_pagina():
    show = caption([{"type": "text", "bbox": [40 + i * 130, 40,
                                              170 + i * 130, 960], "text": "x"}
                    for i in range(6)])
    antes = show["compositional_deconstruction"]["elements"][-1]["bbox"][2]
    depois = I._ocupar_pagina(show)["compositional_deconstruction"]["elements"][-1]["bbox"][2]
    conferir("fileira curta se estica", depois > antes, True)

    cinema = caption([{"type": "text", "bbox": [40, 40, 333, 960], "text": "t"},
                      {"type": "obj", "bbox": [666, 300, 900, 700]}])
    copia = [list(e["bbox"]) for e in cinema["compositional_deconstruction"]["elements"]]
    I._ocupar_pagina(cinema)
    conferir("pagina ja usada fica intacta",
             [e["bbox"] for e in cinema["compositional_deconstruction"]["elements"]],
             copia)


# --------------------------------------------------------------------------
# Rotulos em fileira: "NOVA\nCRESCENTE\n..." num elemento so fazia o Ideogram
# desenhar a fileira certa MAIS um fantasma truncado ("Ouile", "Rride").
# --------------------------------------------------------------------------
def teste_separar_rotulos():
    lua = caption([{"type": "text", "bbox": [150, 100, 800, 900],
                    "text": "NOVA\nCRESCENTE\nCHEIA\nMINGUANTE\nNOVA",
                    "desc": "Five labels inside each corresponding circle"}])
    I._separar_rotulos(lua)
    els = lua["compositional_deconstruction"]["elements"]
    conferir("cinco rotulos separados", len(els), 5)
    # O desc no plural mandava desenhar um circulo em volta de cada rotulo.
    conferir("desc do rotulo nao fala em circulo",
             "circle" in els[0]["desc"].lower(), False)

    # O rotulo do cafe e UM paragrafo: separar quebraria a peca.
    cafe = caption([{"type": "text", "bbox": [223, 200, 346, 700],
                     "text": "SERRA ALTA\nTORRA MÉDIA\nORIGEM: MANTIQUEIRA"}])
    I._separar_rotulos(cafe)
    conferir("paragrafo do cafe fica inteiro",
             len(cafe["compositional_deconstruction"]["elements"]), 1)


def main():
    for nome, fn in sorted(globals().items()):
        if nome.startswith("teste_"):
            fn()
    if _falhas:
        print(f"{len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("  -", f)
        return 1
    print("todos os guardas do Ideogram passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
