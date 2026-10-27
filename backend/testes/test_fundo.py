# -*- coding: utf-8 -*-
"""Testes dos guardas que compoem texto sobre uma foto enviada.

Nao usam GPU nem motor. Rodar com

    backend\\.venv\\Scripts\\python.exe backend\\testes\\test_fundo.py

As fixtures sao quatro fotos reais NA LARGURA EM QUE SAO ENVIADAS (832 px):
um retrato de estudio, uma parede de quatro faixas, a fachada de uma
mercearia com letreiro pintado e uma rua molhada a noite.

Imagem sintetica nao serviria — a cascata de Haar so responde a rosto de
verdade, e o perfil de agitacao precisa de textura real. E o tamanho tambem
nao pode mudar: guardei-as a 416 px para economizar disco e o detector de
letreiro passou a achar texto no asfalto molhado, porque ele reamostra para
480 px e partir de 416 significa AMPLIAR. Fixture que nao reproduz o caminho
de producao testa outra coisa.

Como em `test_ideogram.py`, cada caso aqui e uma falha que ja aconteceu.
"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent))

import enquadrar as E      # noqa: E402
import ideogram as I       # noqa: E402

ROSTO = (RAIZ / "fixtures" / "rosto.jpg").read_bytes()
LETREIRO = (RAIZ / "fixtures" / "letreiro.jpg").read_bytes()
FAIXAS = (RAIZ / "fixtures" / "faixas.jpg").read_bytes()
ESCURA = (RAIZ / "fixtures" / "escura.jpg").read_bytes()

PALETA = ["#F2EBDC", "#FFFFFF", "#111111", "#C8A87C", "#C8342B"]

_falhas = []


def conferir(nome, obtido, esperado):
    if obtido != esperado:
        _falhas.append(f"{nome}: esperado {esperado!r}, obtido {obtido!r}")


def conferir_que(nome, condicao, detalhe=""):
    if not condicao:
        _falhas.append(f"{nome}: falso{(' — ' + detalhe) if detalhe else ''}")


def caption(caixas, textos=None):
    textos = textos or [f"T{i}" for i in range(len(caixas))]
    return {"high_level_description": "peca",
            "compositional_deconstruction": {
                "background": "",
                "elements": [{"type": "text", "bbox": list(b), "text": t,
                              "desc": "One line of display type."}
                             for b, t in zip(caixas, textos)]}}


def alturas(cap):
    return [[e["bbox"][0], e["bbox"][2]]
            for e in cap["compositional_deconstruction"]["elements"]]


# --------------------------------------------------------------------------
# Rosto. A energia de borda sozinha nao bastava: bochecha lisa tem pouca
# borda, e a faixa do nariz a boca era medida como uma das mais calmas da
# foto — por ela o texto cairia bem no meio do rosto.
# --------------------------------------------------------------------------
def teste_acha_rosto():
    faixas = E.faixas_de_rosto(ROSTO)
    conferir("um rosto no retrato", len(faixas), 1)
    inicio, fim = faixas[0]
    conferir_que("a faixa cobre a metade superior", inicio < 100 < fim,
                 f"faixa {faixas[0]}")


def teste_parede_nao_tem_rosto():
    # Na rua a noite a cascata achou um "rosto" no asfalto entre os reflexos.
    # O filtro de tamanho minimo e de vizinhos derrubou esse tipo de engano.
    conferir("parede sem rosto", E.faixas_de_rosto(FAIXAS), [])


# --------------------------------------------------------------------------
# Encaixe.
# --------------------------------------------------------------------------
def teste_tira_o_texto_do_rosto():
    cap = caption([[100, 100, 300, 900], [350, 100, 500, 900],
                   [800, 100, 900, 900]])
    E.encaixar(cap, ROSTO)
    rostos = E.faixas_de_rosto(ROSTO)
    for y1, y2 in alturas(cap):
        conferir_que(f"bloco {y1}-{y2} fora do rosto",
                     not any(a < y2 and b > y1 for a, b in rostos),
                     f"rostos {rostos}")


def teste_ordem_de_leitura_preservada():
    # Uma primeira versao reatribuia as alturas ordenadas no fim e devolvia o
    # titulo para dentro do rosto. A ordem tem de sair por construcao.
    cap = caption([[100, 100, 300, 900], [350, 100, 500, 900],
                   [800, 100, 900, 900]], ["TITULO", "CHAMADA", "RODAPE"])
    E.encaixar(cap, ROSTO)
    tops = [y for y, _ in alturas(cap)]
    conferir("ordem de leitura", tops, sorted(tops))


def teste_encolhe_em_vez_de_desistir():
    # Faltavam 53 unidades de 498 e o encaixe devolvia tudo para cima do
    # rosto, porque so sabia dizer "nao cabe".
    cap = caption([[100, 100, 300, 900], [350, 100, 500, 900],
                   [800, 100, 900, 900]])
    antes = [y2 - y1 for y1, y2 in alturas(cap)]
    E.encaixar(cap, ROSTO)
    depois = [y2 - y1 for y1, y2 in alturas(cap)]
    conferir_que("os blocos encolheram", sum(depois) < sum(antes),
                 f"{sum(antes)} -> {sum(depois)}")
    conferir_que("nao encolheu demais",
                 sum(depois) >= sum(antes) * E.ESCALA_MINIMA)


def teste_sem_rosto_nao_mexe():
    # Mexer no que esta bom so introduz risco.
    cap = caption([[100, 100, 300, 900], [800, 100, 900, 900]])
    antes = alturas(cap)
    E.encaixar(cap, FAIXAS)
    conferir("foto sem rosto fica intacta", alturas(cap), antes)


def teste_livres():
    conferir("um trecho proibido no meio",
             E._livres([(300, 600)]), [(0, 300), (600, 1000)])
    conferir("dois trechos que se tocam",
             E._livres([(3, 517), (39, 521)]), [(0, 3), (521, 1000)])


# --------------------------------------------------------------------------
# Contraste. Medir a foto INTEIRA diria que o ensaio de costas estava bem,
# porque o titulo sobre cabelo escuro pontua alto; e a linha sobre a camiseta
# branca que sumia.
# --------------------------------------------------------------------------
FAIXA_BRANCA = [40, 80, 180, 920]
FAIXA_PRETA = [300, 80, 440, 920]


def teste_contraste_por_regiao():
    cap = caption([FAIXA_BRANCA, FAIXA_PRETA], ["NA BRANCA", "NA PRETA"])
    claro = dict(E.contraste_por_bloco(cap, FAIXAS, "#F2EBDC"))
    conferir_que("tinta clara some na faixa branca",
                 claro["NA BRANCA"] < E.CONTRASTE_MINIMO,
                 f"{claro['NA BRANCA']:.2f}")
    conferir_que("tinta clara aparece na faixa preta",
                 claro["NA PRETA"] >= E.CONTRASTE_MINIMO,
                 f"{claro['NA PRETA']:.2f}")

    escuro = dict(E.contraste_por_bloco(cap, FAIXAS, "#111111"))
    conferir_que("tinta escura inverte o resultado",
                 escuro["NA BRANCA"] >= E.CONTRASTE_MINIMO
                 > escuro["NA PRETA"],
                 f"{escuro}")


def teste_troca_so_o_bloco_que_some():
    cap = caption([FAIXA_BRANCA, FAIXA_PRETA], ["NA BRANCA", "NA PRETA"])
    trocas = E.tintas_por_bloco(cap, FAIXAS, "#F2EBDC", PALETA)
    conferir("so um bloco troca", [t["texto"] for t in trocas], ["NA BRANCA"])
    conferir_que("a troca resolve de fato",
                 trocas[0]["razao"] >= E.CONTRASTE_MINIMO,
                 f"{trocas[0]['razao']:.2f}")


def teste_quatro_blocos_trocam():
    # O encadeamento de varias composicoes so foi exercitado quando quatro
    # blocos cairam todos em faixa clara.
    claras = [[40, 80, 130, 920], [140, 80, 230, 920],
              [540, 80, 630, 920], [660, 80, 750, 920]]
    cap = caption(claras)
    trocas = E.tintas_por_bloco(cap, FAIXAS, "#F2EBDC", PALETA)
    conferir("quatro trocas", len(trocas), 4)


def teste_folga_de_repintura():
    # O glifo nao respeita a caixa: o rabo do Q descia abaixo dela e ficava na
    # cor base, como uma lasca clara pendurada na letra.
    colados = [[40, 80, 130, 920], [140, 80, 230, 920]]
    cap = caption(colados)
    trocas = E.tintas_por_bloco(cap, FAIXAS, "#F2EBDC", PALETA)
    for t in trocas:
        original = colados[t["indice"]]
        conferir_que(f"bloco {t['indice']} ganhou folga",
                     t["bbox"][0] < original[0] and t["bbox"][2] > original[2],
                     f"{original} -> {t['bbox']}")


def teste_mede_so_a_area_exclusiva():
    """Com caixas sobrepostas, o que o segundo bloco "ve" ja esta coberto pelo
    primeiro. Eu supunha que isso errava pouco porque so as letras sao
    pintadas; medi em tres pecas reais e a tinta cobre de 36% a 67% da caixa.

    Aqui a caixa GRANDE esta quase toda na faixa branca; a segunda so tem area
    exclusiva na faixa preta. Medindo a caixa inteira, a segunda pareceria
    clara e trocaria de cor sem precisar.
    """
    grande = [40, 80, 280, 920]        # branca 40-230 + um pedaco da preta
    sobreposta = [60, 80, 300, 920]    # exclusiva: 280-300, so faixa preta
    cap = caption([grande, sobreposta], ["GRANDE", "SOBREPOSTA"])
    razoes = dict(E.contraste_por_bloco(cap, FAIXAS, "#F2EBDC"))
    conferir_que("a grande some na faixa branca",
                 razoes["GRANDE"] < E.CONTRASTE_MINIMO, f"{razoes['GRANDE']:.2f}")
    conferir_que("a sobreposta e julgada pela area exclusiva, que e escura",
                 razoes["SOBREPOSTA"] >= E.CONTRASTE_MINIMO,
                 f"{razoes['SOBREPOSTA']:.2f}")


def teste_folga_nao_cresce_sobre_bloco_que_se_sobrepoe():
    """Caixas sobrepostas so existem no layout MANUAL, onde o usuario desenha
    onde quiser — no automatico o empacotamento as separa. A folga de
    repintura tratava apenas vizinho inteiramente acima ou inteiramente
    abaixo; um que se sobrepoe nao caia em nenhum dos dois ramos e recebia os
    18 pontos de folga inteiros, repintando letra alheia com a cor errada.
    """
    # A primeira cai na faixa branca e precisa de tinta escura; a segunda
    # invade a faixa preta e fica com a clara. Cores finais diferentes.
    caixas = [[40, 80, 180, 920], [170, 80, 320, 920]]
    cap = caption(caixas, ["NA BRANCA", "INVADE"])
    trocas = E.tintas_por_bloco(cap, FAIXAS, "#F2EBDC", PALETA)
    conferir("so a da faixa branca troca",
             [t["texto"] for t in trocas], ["NA BRANCA"])
    conferir("sem folga quando o vizinho se sobrepoe",
             trocas[0]["bbox"], caixas[0])


def teste_folga_respeita_vizinho_de_outra_cor():
    # Dois blocos vizinhos com cores finais diferentes: a folga tem de parar
    # no meio do caminho, senao a repintura invade letra alheia.
    cap = caption([[150, 80, 260, 920], [280, 80, 390, 920]],
                  ["CLARA", "PRETA"])
    trocas = E.tintas_por_bloco(cap, FAIXAS, "#F2EBDC", PALETA)
    for t in trocas:
        conferir_que("a folga nao invade o vizinho",
                     t["bbox"][2] <= 280 and t["bbox"][0] >= 130,
                     f"{t['texto']} -> {t['bbox']}")


# --------------------------------------------------------------------------
# Preparo da peca para o recorte.
# --------------------------------------------------------------------------
def teste_forca_branco_sobre_preto():
    # A mascara sai da luminancia: se o LLM escolher fundo claro, ela sai
    # invertida e a foto aparece DENTRO das letras.
    cap = caption([[100, 100, 300, 900]])
    cap["compositional_deconstruction"]["background"] = "a bright white wall"
    I.preparar_para_recorte(cap)
    fundo = cap["compositional_deconstruction"]["background"]
    conferir("fundo forcado a preto", fundo, I.FUNDO_RECORTAVEL)


def teste_tira_o_vazado_do_desc():
    # A caption da cena escura trazia "white outlined condensed letters", e
    # mandar preencher logo depois disso deixava a instrucao brigando consigo
    # mesma — o titulo saia com contorno claro e miolo vazado.
    cap = caption([[100, 100, 300, 900]])
    cap["compositional_deconstruction"]["elements"][0]["desc"] = (
        "White outlined condensed letters set on a white box")
    I.preparar_para_recorte(cap)
    desc = cap["compositional_deconstruction"]["elements"][0]["desc"]
    herdado = desc.split("Each glyph")[0].lower()
    for palavra in ("outlined", "box"):
        conferir_que(f"'{palavra}' saiu do desc herdado",
                     palavra not in herdado, herdado)
    conferir_que("a ordem de preencher entrou", "solid mass" in desc)


# --------------------------------------------------------------------------
# Texto que ja existe na foto. E AVISO, nao regra: varri altura e largura
# minimas e em nenhum ponto o detector separou o letreiro da mercearia das
# manchas alinhadas do asfalto molhado. Como restricao dura empurraria peca
# que hoje sai bem.
# --------------------------------------------------------------------------
def teste_acha_letreiro():
    faixas = E.faixas_de_texto(LETREIRO)
    conferir_que("achou letreiro na fachada", len(faixas) >= 1, str(faixas))


def teste_reflexo_nao_e_letreiro():
    # Na rua a noite o asfalto molhado formava manchas alinhadas que o MSER
    # lia como palavra, e o aviso acusava os TRES blocos — virava ruido.
    # Altura e espacamento nao separavam (variacao sobreposta, 0.01-0.10 nos
    # dois casos); o que separou foi a contagem de regioes estaveis, que mede
    # nitidez: fachada com 16, 19 e 105 por linha, asfalto com 5, 8 e 11.
    conferir("reflexo nao vira letreiro", E.faixas_de_texto(ESCURA), [])


def teste_parede_lisa_nao_tem_letreiro():
    conferir("faixas sem letreiro", E.faixas_de_texto(FAIXAS), [])
    conferir("retrato sem letreiro", E.faixas_de_texto(ROSTO), [])


def teste_acusa_texto_sobre_texto():
    faixas = E.faixas_de_texto(LETREIRO)
    a, b = faixas[0]
    cap = caption([[a, 80, b, 920], [900, 80, 970, 920]], ["EM CIMA", "LONGE"])
    conferir("so o bloco sobreposto e acusado",
             E.texto_sobre_texto(cap, LETREIRO), ["EM CIMA"])


def teste_sem_letreiro_nao_acusa():
    cap = caption([[100, 80, 300, 920]], ["QUALQUER"])
    conferir("foto lisa nao gera aviso", E.texto_sobre_texto(cap, FAIXAS), [])


def main():
    for nome, fn in sorted(globals().items()):
        if nome.startswith("teste_"):
            fn()
    if _falhas:
        print(f"{len(_falhas)} FALHA(S):")
        for f in _falhas:
            print("  -", f)
        return 1
    print("todos os guardas de fundo passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
