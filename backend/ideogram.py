"""Ideogram 4: escrita do JSON de layout e os guardas que o corrigem.

Separado de `prompting.py` porque sao duas coisas diferentes — la mora a
expansao de prompt dos modelos simples, aqui a montagem da caption.

Cada guarda abaixo nasceu de uma falha observada numa geracao real, e o
comentario de cada um registra qual. A ordem em que rodam importa: separar
rotulos antes de dividir a ilustracao, e dar margem antes de ocupar a pagina.

Convencao de bbox do Ideogram 4: [y1, x1, y2, x2], normalizada de 0 a 1000 nos
DOIS eixos, com origem no canto superior esquerdo.
"""

import json
import math
import pathlib
import re

import comfy
import workflows

PASTA = pathlib.Path(__file__).parent / "prompts"

# System prompt oficial do ComfyUI que converte uma ideia em JSON de layout.
GABARITO_IDEOGRAM = (PASTA / "ideogram4_caption.txt").read_text(encoding="utf-8")


def _so_json(bruto: str) -> dict:
    """Extrai o objeto JSON de uma resposta do modelo, tolerando ruido."""
    texto = bruto.strip()
    texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.M).strip()
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fim == -1:
        raise ValueError(f"resposta sem JSON: {bruto[:200]}")
    return json.loads(texto[inicio:fim + 1])


def _so_lista(bruto: str) -> list:
    """Extrai um array JSON. O `_so_json` so procura chaves, e por isso todo
    preenchimento de placeholder falhava calado e caia na remocao."""
    texto = re.sub(r"^```(?:json)?|```$", "", bruto.strip(), flags=re.M).strip()
    inicio, fim = texto.find("["), texto.rfind("]")
    if inicio == -1 or fim == -1:
        raise ValueError(f"resposta sem lista: {bruto[:200]}")
    return json.loads(texto[inicio:fim + 1])



PISTAS_TRANSPARENCIA = ("transparen", "alpha", "recorte", "cutout", "sticker",
                        "adesivo", "sem fundo", "no background", "png")


def _quer_transparencia(ideia: str) -> bool:
    baixa = ideia.lower()
    return any(p in baixa for p in PISTAS_TRANSPARENCIA)


# Um fundo descrito com duas ou tres palavras — "gray-ice background", "black
# backdrop" — nao e uma superficie, e um rotulo. No cartaz de cinema suico o
# Ideogram recebeu exatamente isso e PINTOU o xadrez cinza do Photoshop nos
# pixels: o arquivo saiu RGB, sem canal alfa nenhum, com o quadriculado como
# conteudo. Ele aprendeu a associar "fundo cinza sem cena descrita" a textura
# de PNG transparente dos bancos de imagem.
#
# Por isso o guarda nao procura a palavra "transparent" na caption: ela nunca
# esteve la. Ele mede se o fundo foi DESCRITO, e completa quando nao foi,
# preservando a cor que o usuario pediu.
_COR_SOLTA = re.compile(
    r"^(a |an |the )?[\w -]{0,24}?\b(background|backdrop|field|surface)\b\.?$", re.I)


_NAO_E_COR = re.compile(r"\b(transparen\w*|alpha|none|empty|plain|no)\b", re.I)

# Quando o fundo precisa ser reescrito, a paleta que o usuario pediu e a melhor
# fonte de cor que temos — melhor que "neutral", que num cartaz de serigrafia
# preto e laranja nao quer dizer nada.
_CORES_PT = {
    "preta": "black", "preto": "black", "branca": "white", "branco": "white",
    "laranja": "orange", "vermelha": "deep red", "vermelho": "deep red",
    "azul": "blue", "verde": "green", "amarela": "yellow", "amarelo": "yellow",
    "cinza": "grey", "bege": "beige", "creme": "cream", "rosa": "pink",
    "roxa": "purple", "roxo": "purple", "marrom": "brown", "dourada": "gold",
    "dourado": "gold", "sepia": "sepia", "kraft": "kraft paper brown",
}


# Palavras que, perto de uma cor, dizem que aquela cor e do FUNDO e nao de um
# objeto. Sem isso, "barco vermelho sobre fundo cinza-gelo" escolhia vermelho:
# a cor do barco, porque era a primeira que aparecia na frase.
_PISTAS_FUNDO = {"fundo", "fundos", "paleta", "papel", "base", "background",
                 "backdrop", "pano", "chapado"}


def _cores_da_ideia(ideia: str) -> list:
    """Cores citadas na ideia, em ingles, as de fundo primeiro."""
    palavras = re.findall(r"[a-zá-úâ-ûã-õç]+", ideia.lower())
    ancoras = [i for i, p in enumerate(palavras) if p in _PISTAS_FUNDO]
    achadas = {}
    for i, p in enumerate(palavras):
        cor = _CORES_PT.get(p)
        if not cor or cor in achadas:
            continue
        # So conta a cor que vem DEPOIS da pista: em portugues o adjetivo
        # segue o substantivo ("fundo cinza-gelo", "paleta preta e laranja").
        # Medir distancia nos dois sentidos fazia "barco vermelho, fundo
        # cinza-gelo" ancorar o vermelho, que e a cor do barco.
        perto = min((i - a for a in ancoras if 0 < i - a <= 3), default=999)
        achadas[cor] = (perto, i)
    return sorted(achadas, key=achadas.get)


def _cores_dos_textos(elementos: list) -> set:
    """TODAS as cores usadas em texto, lidas do `desc` que o LLM escreveu.

    A primeira versao olhava so a cor DOMINANTE. Num cartaz preto e laranja o
    dominante era preto, o fundo virou laranja — e os tres nomes de abertura,
    que eram laranja, sairam em vermelho sobre laranja para nao sumirem. Uma
    colisao resolvida cria outra um nivel abaixo se so a maioria for olhada.
    """
    cores = set()
    for e in elementos:
        if e.get("type") == "text":
            cores.update(_CORES_EN.findall(str(e.get("desc", "")).lower()))
    if "gray" in cores:
        cores.add("grey")
    if "grey" in cores:
        cores.add("gray")
    return cores


_CORES_EN = re.compile(
    r"\b(black|white|orange|red|blue|green|yellow|grey|gray|beige|cream|pink|"
    r"purple|brown|gold|sepia)\b")

# Quando o fundo e escolhido por nos, ele nao pode ser a mesma cor do texto.
# Na primeira versao eu pegava a primeira cor da paleta: num cartaz "preto e
# laranja" isso deu fundo preto com titulo preto por cima, quase ilegivel.
_CLARO_SEGURO = "bone white paper"


def _cor_de_fundo(ideia: str, elementos: list) -> str:
    usadas = _cores_dos_textos(elementos)
    for cor in _cores_da_ideia(ideia):
        if cor not in usadas:
            return cor
    # A paleta inteira ja esta em uso pelo texto. Papel e a saida classica da
    # serigrafia: deixa conviver um titulo escuro e um bloco de cor viva.
    return "black" if usadas <= {"white", "cream", "beige", "gold", "yellow"} \
        and usadas else _CLARO_SEGURO


def _fundo_e_fraco(fundo: str) -> bool:
    limpo = fundo.strip()
    if not limpo:
        return True
    return len(limpo.split()) <= 5 and bool(_COR_SOLTA.match(limpo))


def _corrigir_fundo(caption: dict, ideia: str) -> dict:
    if _quer_transparencia(ideia):
        return caption
    comp = caption.get("compositional_deconstruction", {})
    fundo = str(comp.get("background", ""))

    # O fallback antigo era um estudio fotografico, que entrava como fundo de
    # um cartaz de serigrafia preto e laranja. O substituto e neutro quanto a
    # tecnica: descreve uma superficie chapada, nao um cenario.
    if "transparent" in fundo.lower() or _fundo_e_fraco(fundo):
        cor = re.sub(r"\b(background|backdrop|field|surface)\b", "",
                     fundo, flags=re.I).strip(" .,-")
        # "transparent" nao e uma cor. Deixar passar produzia "a solid, evenly
        # printed transparent field, flat and opaque" — uma contradicao, e o
        # xadrez voltou por causa dela.
        if not cor or _NAO_E_COR.search(cor):
            cor = _cor_de_fundo(ideia, comp.get("elements") or [])
        # A frase antiga terminava em "no pattern, no grid, no checkerboard".
        # Negacao e justamente o que um modelo de difusao desenha: nomear o
        # xadrez para proibi-lo e nomear o xadrez. A descricao agora e so
        # positiva.
        comp["background"] = (
            f"A single flat expanse of {cor} ink covering the whole canvas edge "
            "to edge, one uniform matte tone, unbroken and featureless apart "
            "from a faint paper grain.")

    descricao = caption.get("high_level_description", "")
    caption["high_level_description"] = re.sub(
        r"\s*,?\s*on a transparent background", "", descricao, flags=re.I)
    return caption


# Texto vertical existe de verdade — lombada de livro, banner, faixa lateral.
# Quando o proprio LLM diz que e vertical, a caixa alta esta certa e nao se
# mexe nela.
#
# Cuidado com o falso positivo que custou uma geracao: o rotulo do cafe tinha
# "stacked vertically" no desc, que quer dizer LINHAS EMPILHADAS uma sobre a
# outra — layout normal — e nao glifos girados. "empilhado na vertical" e
# "escrito na vertical" sao coisas opostas. As frases de empilhamento saem do
# texto antes da busca.
_EMPILHAMENTO = re.compile(
    r"\b(stacked|arranged|aligned|listed|centered|centred|set|spaced)\s+"
    r"vertically\b|\bvertically\s+"
    r"(stacked|arranged|aligned|listed|centered|centred|spaced)\b", re.I)

_DIZ_VERTICAL = re.compile(
    r"\b(vertical text|text is vertical|vertical lettering|vertical banner|"
    r"rotated|sideways|spine|lombada|girad[oa]|turned 90|90 degrees|"
    r"runs? vertically|running vertically|reads? vertically|"
    r"printed vertically|written vertically)\b", re.I)

# Largura media de um caractere em relacao a altura da linha, numa condensada
# de cartaz. So precisa ser aproximado: a decisao e entre duas alternativas
# muito distantes (a caixa e a caixa trocada), nao uma medida fina.
_LARGURA_DO_CARACTERE = 0.55
_MARGEM_DE_DECISAO = 0.35


def _proporcao_pedida(texto: str) -> float:
    """Razao largura/altura que este texto precisa para caber sem girar."""
    linhas = [l for l in str(texto).splitlines() if l.strip()] or [""]
    maior = max(len(l) for l in linhas)
    return (maior * _LARGURA_DO_CARACTERE) / len(linhas)


def _pede_virar(elemento: dict) -> bool:
    """O texto cabe muito melhor na caixa trocada do que na que veio?"""
    desc = _EMPILHAMENTO.sub(" ", str(elemento.get("desc", "")))
    if _DIZ_VERTICAL.search(desc):
        return False
    y1, x1, y2, x2 = elemento["bbox"]
    altura, largura = y2 - y1, x2 - x1
    if altura <= 0 or largura <= 0:
        return False
    pedida = _proporcao_pedida(elemento.get("text", ""))
    if pedida <= 0:
        return False
    erro_atual = abs(math.log((largura / altura) / pedida))
    erro_trocado = abs(math.log((altura / largura) / pedida))
    return erro_trocado + _MARGEM_DE_DECISAO < erro_atual


def _desvirar_bboxes(caption: dict) -> dict:
    """Conserta as caixas quando o LLM emite [x1,y1,x2,y2] em vez de [y1,x1,y2,x2].

    O Ideogram 4 usa Y PRIMEIRO, e o gabarito oficial diz isso. O modelo local
    de 8B escreve na ordem comum em visao computacional, X primeiro — e o erro
    e SISTEMATICO: nas cinco pecas de teste, os 18 elementos de texto sairam
    como colunas altas e estreitas, sem uma excecao.

    O estrago nao era sutil. "ORQUESTRA DE FERRO" virou tres colunas verticais
    empilhadas; "SERRA ALTA" e "TORRA MEDIA" sairam impressas giradas 90 graus
    na embalagem. O texto nao estava sendo escrito errado: estava sendo
    espremido numa caixa da forma errada.

    A deteccao e por MAIORIA, nao por elemento: linha de texto e quase sempre
    mais larga que alta, entao varias caixas altas seguidas indicam troca
    sistematica. Trocar elemento a elemento quebraria o caso legitimo — texto
    vertical existe, em lombada de livro e em banner.
    """
    comp = caption.get("compositional_deconstruction", {})
    elementos = comp.get("elements") or []
    textos = [e for e in elementos
              if e.get("type") == "text" and isinstance(e.get("bbox"), list)
              and len(e["bbox"]) == 4]
    if not textos:
        return caption

    # Com um unico bloco nao ha maioria para consultar, e a peca passava batido:
    # a embalagem SERRA ALTA saiu com o rotulo inteiro girado 90 graus numa
    # caixa de 100 de largura por 500 de altura. Com um so elemento a decisao
    # vem da forma que o PROPRIO texto exige.
    if len(textos) == 1:
        if not _pede_virar(textos[0]):
            return caption
    else:
        altos = sum(1 for e in textos
                    if (e["bbox"][2] - e["bbox"][0]) > (e["bbox"][3] - e["bbox"][1]))
        if altos <= len(textos) / 2:
            return caption

    for e in elementos:
        b = e.get("bbox")
        if isinstance(b, list) and len(b) == 4:
            e["bbox"] = [b[1], b[0], b[3], b[2]]
    return caption


# O reforco em texto pede que o modelo invente conteudo onde o usuario apenas
# DESCREVEU um texto ("tres nomes de bandas de abertura"). Ele obedece parte
# das vezes; no cartaz de show devolveu "BANDA 1", "BANDA 2" e "BANDA 3", que
# foram impressos na peca. Regra numero N da sessao: garantia mora no codigo.
#
# A deteccao e deterministica. O preenchimento e um pedido curto e isolado ao
# LLM, com uma tarefa unica — que e onde o 8B funciona bem. Se ainda assim ele
# devolver um placeholder, o elemento e removido: melhor um bloco a menos do
# que "BANDA 1" impresso em corpo 40.
_PLACEHOLDER = re.compile(
    r"^\s*(?:"
    r"(?:banda|texto|t[ií]tulo|chamada|linha|item|nome|legenda|bloco|"
    r"cr[eé]dito|r[oó]tulo|band|text|title|headline|line|name|caption|label)"
    r"s?\s*[-–#]?\s*\d+"
    r"|texto|legenda|t[ií]tulo|chamada|rodap[ée]|cr[eé]ditos|subt[ií]tulo"
    r"|lorem ipsum.*|placeholder.*|sample text|your text here|xxx+|tbd|n/?a"
    r")\s*$", re.I)


def _e_placeholder(texto: str) -> bool:
    return bool(_PLACEHOLDER.match(texto or ""))


async def _preencher_placeholders(caption: dict, ideia: str) -> dict:
    comp = caption.get("compositional_deconstruction", {})
    elementos = comp.get("elements") or []
    suspeitos = [e for e in elementos
                 if e.get("type") == "text" and _e_placeholder(e.get("text", ""))]
    if not suspeitos:
        return caption

    pedido = (
        "A designer is laying out this piece:\n" + ideia.strip() +
        "\n\nSome text blocks were left as placeholders. Write the real words "
        "for each one, in the same language as the rest of the piece. Keep each "
        "one short and plausible for its role — invented names, dates or lines "
        "that a real piece would carry. Never answer with a generic word like "
        "'texto', 'banda 1' or 'title'.\n\nBlocks:\n" +
        "\n".join(f"{i + 1}. role: {e.get('desc', '')} | placeholder: "
                  f"{e.get('text', '')}" for i, e in enumerate(suspeitos)) +
        "\n\nAnswer with a JSON array of exactly "
        f"{len(suspeitos)} strings and nothing else.")

    try:
        saidas = await comfy.executar(workflows.escrever_texto(pedido, 400))
        novos = _so_lista(await comfy.texto_de(saidas))
    except Exception:
        novos = None

    if not isinstance(novos, list):
        novos = []
    for elemento, novo in zip(suspeitos, novos):
        if isinstance(novo, str) and novo.strip() and not _e_placeholder(novo):
            elemento["text"] = novo.strip()

    comp["elements"] = [e for e in elementos
                        if not (e.get("type") == "text"
                                and _e_placeholder(e.get("text", "")))]
    return caption


# O LLM escreve bboxes de texto coladas na borda — [0, 0, 300, 1000] e o
# padrao dele para um titulo. O Ideogram preenche a caixa inteira, e a peca
# sai com a primeira e a ultima letra cortadas: "ORQUESTRA DE FERRO" virou
# "RQUESTRA DE FERR" em duas rodadas seguidas.
#
# So mexe em quem ENCOSTA na borda: uma caixa que o LLM ja posicionou com
# folga fica como esta, e sangramento de ilustracao (type "obj") continua
# permitido, porque num cartaz ele costuma ser intencional.
MARGEM = 40
_ENCOSTA = 8


def _dar_margem(caption: dict) -> dict:
    comp = caption.get("compositional_deconstruction", {})
    for e in comp.get("elements") or []:
        b = e.get("bbox")
        if e.get("type") != "text" or not isinstance(b, list) or len(b) != 4:
            continue
        y1, x1, y2, x2 = b
        if x1 <= _ENCOSTA:
            x1 = MARGEM
        if x2 >= 1000 - _ENCOSTA:
            x2 = 1000 - MARGEM
        if y1 <= _ENCOSTA:
            y1 = MARGEM
        if y2 >= 1000 - _ENCOSTA:
            y2 = 1000 - MARGEM
        if x2 > x1 and y2 > y1:
            e["bbox"] = [y1, x1, y2, x2]
    return caption


# O LLM nao diagrama: ele empilha faixas contiguas de cima para baixo e para
# quando acabam os elementos. No cartaz de show as seis caixas ocupavam ate a
# altura 800 e o terco inferior ficava vazio, o que nao acontece em cartaz de
# show nenhum.
#
# O guarda so age quando a pagina esta MESMO sobrando. No cartaz de cinema a
# ilustracao do barco vai ate 900 e o vazio embaixo e espaco negativo
# deliberado — ali ele nao dispara, e e assim que deve ser.
FUNDO_USADO = 860
ESTICAO_MAXIMO = 1.6


def _ocupar_pagina(caption: dict) -> dict:
    comp = caption.get("compositional_deconstruction", {})
    caixas = [e for e in comp.get("elements") or []
              if isinstance(e.get("bbox"), list) and len(e["bbox"]) == 4]
    if len(caixas) < 2:
        return caption

    topo = min(e["bbox"][0] for e in caixas)
    base = max(e["bbox"][2] for e in caixas)
    if base >= FUNDO_USADO or base <= topo:
        return caption

    fator = (1000 - MARGEM - topo) / (base - topo)
    if not 1.0 < fator <= ESTICAO_MAXIMO:
        return caption

    for e in caixas:
        y1, x1, y2, x2 = e["bbox"]
        e["bbox"] = [round(topo + (y1 - topo) * fator), x1,
                     round(topo + (y2 - topo) * fator), x2]
    return caption


# O LLM junta rotulos de uma fileira num unico elemento com quebras de linha —
# "NOVA\nCRESCENTE\nCHEIA\nMINGUANTE\nNOVA" para cinco circulos lado a lado. O
# Ideogram entao tenta obedecer as duas coisas ao mesmo tempo, "cinco linhas" e
# "uma fileira", e DESENHA AS DUAS: a fileira certa mais um fantasma truncado
# ("Ouile", "Rride", "Reka", "AUDIO").
#
# Medido com quatro geracoes de mesma seed, mudando so a geometria: com um
# elemento por rotulo o fantasma some por completo; com o bloco unico ele
# aparece tanto em caixa apertada quanto em caixa grande.
#
# So separa rotulo CURTO em fileira. As tres linhas do rotulo do cafe
# ("SERRA ALTA / TORRA MEDIA / ORIGEM: MANTIQUEIRA") sao um paragrafo so e
# devem continuar juntas — por isso o limite de caracteres por linha.
MAX_CARACTERES_ROTULO = 15
MIN_ROTULOS = 3
ALTURA_DO_ROTULO = 70
RESPIRO_ENTRE_ROTULOS = 8


def _separar_rotulos(caption: dict) -> dict:
    comp = caption.get("compositional_deconstruction", {})
    elementos = comp.get("elements") or []
    saida, fileiras = [], []
    for e in elementos:
        linhas = [l.strip() for l in str(e.get("text", "")).splitlines()
                  if l.strip()]
        b = e.get("bbox")
        if (e.get("type") != "text" or len(linhas) < MIN_ROTULOS
                or not isinstance(b, list) or len(b) != 4
                or max(len(l) for l in linhas) > MAX_CARACTERES_ROTULO):
            saida.append(e)
            continue

        y1, x1, y2, x2 = b
        # Fileira so faz sentido em caixa mais larga que alta. Caixa alta e
        # empilhamento legitimo, e fica como esta.
        if (x2 - x1) <= (y2 - y1):
            saida.append(e)
            continue

        # Os rotulos ficam na BASE da caixa: no infografico eles vem embaixo
        # dos circulos, que ocupam o resto dela.
        topo = max(y1, y2 - ALTURA_DO_ROTULO)
        passo = (x2 - x1) / len(linhas)
        # O `desc` da fileira fala no plural e descreve a RELACAO entre os
        # itens. No infografico da lua ele dizia "centered vertically within
        # each corresponding circle, scaled to fit neatly inside each circle" —
        # e o Ideogram desenhou um circulo em volta de cada rotulo, criando uma
        # segunda fileira. Herdar esse texto em cinco caixas repete a ordem
        # cinco vezes, entao cada rotulo recebe uma descricao propria e neutra.
        cor = " ".join(sorted(set(_CORES_EN.findall(
            str(e.get("desc", "")).lower()))))
        # Só descricao positiva: "no frame, no disc" nomearia a moldura e o
        # disco, e o modelo desenha o que se nomeia — a mesma licao do softbox
        # e do xadrez.
        desc_rotulo = (f"One short {cor} label".strip() +
                       ", centred under its item, printed straight onto the "
                       "flat background as bare lettering.")
        e = {**e, "desc": desc_rotulo}
        novos = [{**e, "text": linha,
                  "bbox": [topo,
                           round(x1 + i * passo + RESPIRO_ENTRE_ROTULOS),
                           y2,
                           round(x1 + (i + 1) * passo - RESPIRO_ENTRE_ROTULOS)]}
                 for i, linha in enumerate(linhas)]
        saida.extend(novos)
        fileiras.append({"y1": y1, "y2": y2, "x1": x1, "x2": x2,
                         "quantos": len(linhas), "rotulos": novos})
    comp["elements"] = saida
    return fileiras


# Depois de separar os rotulos ainda sobra o problema que os criou: a caixa da
# ILUSTRACAO. No infografico da lua ela tinha 700 unidades de altura para uma
# fileira de cinco discos que precisa de ~170, e o Ideogram alinha o conteudo
# na base de uma caixa grande demais — foi o que deixou a pagina 70% vazia e o
# que fez o fantasma aparecer no topo.
#
# A sonda de geometria mostrou a forma certa: uma faixa com a altura de um item
# da fileira, os rotulos logo abaixo, e o grupo centrado no espaco livre.
# A primeira tentativa encolheu a ilustracao para uma FAIXA unica de 800 de
# largura com os rotulos logo abaixo. Saiu pior: o Ideogram leu as duas caixas
# largas e vizinhas como uma grade e desenhou DUAS fileiras de circulos.
#
# Era o mesmo mecanismo do `\n`, um nivel acima — bloco unico que representa N
# itens vira N itens desenhados de formas conflitantes. A sonda de geometria ja
# tinha mostrado a saida: na variante que ficou boa os cinco discos eram cinco
# `obj` SEPARADOS, um por coluna. E isso que se reproduz aqui.
RESPIRO_FILEIRA = 30
RECUO_DA_COLUNA = 20
ALTURA_MAXIMA_DA_FAIXA = 320


async def _dividir_ilustracao(comp: dict, fileira: dict) -> None:
    y1, y2, x1, x2 = fileira["y1"], fileira["y2"], fileira["x1"], fileira["x2"]
    rotulos = fileira["rotulos"]
    quantos = fileira["quantos"]
    elementos = comp.get("elements") or []

    def encosta(e):
        b = e.get("bbox")
        if e.get("type") == "obj" and isinstance(b, list) and len(b) == 4:
            return b[0] < y2 and b[2] > y1 and b[1] < x2 and b[3] > x1
        return False

    faixas = [e for e in elementos if encosta(e)]
    if len(faixas) != 1:
        return
    faixa = faixas[0]

    nomes = [r["text"] for r in rotulos]
    partes = await _descrever_itens(faixa.get("desc", ""), nomes)
    # Sem uma descricao por item, clonar a da fileira faria cada caixa desenhar
    # a fileira inteira. Melhor nao mexer.
    if len(partes) != quantos:
        return

    # A altura sai da LARGURA REAL da coluna, nao da largura da fileira
    # dividida. Usando (x2-x1)/quantos a caixa saia 160 de altura por 104 de
    # largura — retrato — e o Ideogram empilhou DOIS circulos dentro de cada
    # uma, recriando a fileira dupla um nivel abaixo. Item de fileira quer
    # caixa quadrada.
    largura_coluna = (rotulos[0]["bbox"][3] - rotulos[0]["bbox"][1]
                      - 2 * RECUO_DA_COLUNA)
    altura = min(largura_coluna, ALTURA_MAXIMA_DA_FAIXA)
    altura_grupo = altura + RESPIRO_FILEIRA + ALTURA_DO_ROTULO
    abaixo = [e["bbox"][0] for e in elementos
              if e is not faixa and e not in rotulos
              and isinstance(e.get("bbox"), list) and e["bbox"][0] >= y2]
    limite = min(abaixo, default=1000 - MARGEM) - RESPIRO_FILEIRA
    topo = max(MARGEM, MARGEM + (limite - MARGEM - altura_grupo) / 2)
    base = round(topo + altura)

    novos = []
    for i, desc in enumerate(partes):
        esq = rotulos[i]["bbox"][1] + RECUO_DA_COLUNA
        dir_ = rotulos[i]["bbox"][3] - RECUO_DA_COLUNA
        novos.append({"type": "obj", "bbox": [round(topo), esq, base, dir_],
                      "desc": desc})

    alto_rotulo = base + RESPIRO_FILEIRA
    for r in rotulos:
        r["bbox"] = [alto_rotulo, r["bbox"][1],
                     alto_rotulo + ALTURA_DO_ROTULO, r["bbox"][3]]

    lugar = elementos.index(faixa)
    comp["elements"] = elementos[:lugar] + novos + elementos[lugar + 1:]


async def _descrever_itens(desc_da_fileira: str, nomes: list) -> list:
    """Uma descricao visual para cada item da fileira, no singular."""
    pedido = (
        "An illustration shows a horizontal row of items, described as:\n"
        f"{desc_da_fileira}\n\n"
        "Write one short visual description for EACH item below, describing "
        "only that single item, in the singular. Never mention the row, the "
        "other items, or how many there are.\n\nItems:\n" +
        "\n".join(f"{i + 1}. {n}" for i, n in enumerate(nomes)) +
        f"\n\nAnswer with a JSON array of exactly {len(nomes)} strings and "
        "nothing else.")
    try:
        saidas = await comfy.executar(workflows.escrever_texto(pedido, 400))
        partes = _so_lista(await comfy.texto_de(saidas))
    except Exception:
        return []
    return [p.strip() for p in partes if isinstance(p, str) and p.strip()]


async def caption_ideogram(ideia: str, proporcao: str) -> dict:
    """Converte uma ideia livre no JSON de layout que o Ideogram 4 espera."""
    # O contrato oficial trata aspas como conteudo literal e o resto como
    # descricao. Quem escreve em portugues nao poe aspas — e entao "tres
    # chamadas menores na lateral esquerda" virava texto impresso na peca,
    # junto com "codigo de barras no rodape" e "BANDA 1 / BANDA 2 / BANDA 3".
    # O reforco separa as duas coisas e manda inventar conteudo plausivel onde
    # o usuario descreveu um texto sem dizer qual.
    reforco = (
        "\n\nDo NOT use a transparent background unless the user idea "
        "explicitly asks for one. Include at least three elements."
        "\n\nThe user writes in Portuguese and rarely uses quotation marks. "
        "Only words the user actually wants printed may become the `text` of a "
        "text element. A phrase that describes the layout, the quantity or the "
        "role of a text block — 'três chamadas menores', 'código de barras no "
        "rodapé', 'bloco de créditos', 'nomes das bandas de abertura', "
        "'legenda embaixo' — is an INSTRUCTION, never the printed words. For "
        "those, invent short, plausible content that fits the piece and the "
        "language of the rest, and put the layout intent in `desc` instead. "
        "Never print the words 'texto', 'legenda', 'título', 'chamada', "
        "'rodapé', 'banda 1', 'lorem ipsum' or any placeholder.")
    instrucao = (GABARITO_IDEOGRAM
                 .replace("{{ratio}}", proporcao)
                 .replace("{{original_prompt}}", ideia + reforco))
    saidas = await comfy.executar(workflows.escrever_texto(instrucao, 2048))
    bruto = _so_json(await comfy.texto_de(saidas))
    limpo = await _preencher_placeholders(_desvirar_bboxes(bruto), ideia)
    arrumado = _corrigir_fundo(limpo, ideia)
    comp = arrumado.get("compositional_deconstruction", {})
    for fileira in _separar_rotulos(arrumado):
        await _dividir_ilustracao(comp, fileira)
    return _ocupar_pagina(_dar_margem(arrumado))




FUNDO_RECORTAVEL = (
    "A single flat expanse of pure black ink covering the whole canvas edge to "
    "edge, one uniform matte tone, unbroken and featureless.")

# Descreve o ESTADO das letras, nunca o que evitar. Cada frase saiu de um
# defeito visto: o miolo vazado na cena de rua, e a chapa clara atras do
# titulo na mesma peca.
# O `desc` que o LLM escreveu costuma pedir o vazado explicitamente — na cena
# de rua vinha "white outlined condensed letters". Mandar preencher logo
# depois de uma palavra dessas deixa a instrucao brigando consigo mesma, entao
# elas saem do texto herdado antes.
_VAZADO = re.compile(
    r"\b(outlined?|hollow|open[- ]faced?|stroked?|inline|contour(ed)?|"
    r"see[- ]through|knocked[- ]out|reversed out|on a (white |light )?"
    r"(box|plate|panel|banner|plaque|slab)|boxed)\b", re.I)

# Tudo que o LLM pede de ENFEITE vira tinta na composicao, porque a mascara
# recorta luminancia e nao sabe o que e letra. Na fachada da mercearia os
# `desc` pediam "a slight drop shadow", "a subtle underline" e "a thin
# horizontal line": a sombra virou uma chapa clara atras do titulo e as duas
# linhas viraram reguas brancas atravessando a peca.
_ADORNO = re.compile(
    r",?\s*\bwith\s+(a|an|the)?\s*[\w -]{0,20}?"
    r"\b(drop shadow|shadow|underline|horizontal (line|rule)|thin line|"
    r"glow|halo|gradient|border|frame)\b[^,.]*"
    r"|\bunderlined\b|\bdrop[- ]shadowed\b", re.I)

# O removedor de cor tirava o substantivo e deixava o modificador: "in dark
# blue" virava "in dark", que manda escurecer a letra no exato campo preto de
# onde ela precisa se destacar. O modificador sai junto com a cor.
_COR_COM_MODIFICADOR = re.compile(
    r"\b((dark|light|pale|deep|bright|warm|cool|soft|off|muted|dusty)[- ]?)*"
    r"(black|white|orange|red|blue|green|yellow|grey|gray|beige|cream|pink|"
    r"purple|brown|gold|sepia|amber|ivory)\b", re.I)

LETRA_CHAPADA = (
    "Each glyph is one solid mass of flat pure white, uniformly filled from "
    "edge to edge of its own outline. The pure black field runs right up to "
    "the edge of every letter and fills all the space between and around the "
    "words.")


def preparar_para_recorte(caption: dict) -> dict:
    """Forca a peca ao formato de que a composicao precisa: branco sobre preto.

    A mascara sai da LUMINANCIA da peca, entao a polaridade nao pode ficar a
    cargo do LLM: se ele escolher fundo claro ou letra escura, a mascara sai
    invertida e o resultado e a foto aparecendo dentro das letras.

    A cor final do texto nao se perde — ela vem da chapa de tinta na hora de
    compor, nao daqui.

    Pedir so a polaridade nao basta. Na cena de rua a noite o Ideogram
    desenhou a tipografia VAZADA — contorno claro e miolo escuro — e a mascara
    reproduziu fielmente so o contorno, deixando a foto aparecer por dentro da
    letra. Em fundo claro isso passa; em fundo escuro destroi a legibilidade.
    Na mesma peca ele pos uma CHAPA clara atras do titulo, que virou um bloco
    de tinta na composicao.

    Por isso o preenchimento e a extensao do branco tambem sao ditos, e ditos
    de forma positiva: "no outline, no box" nomearia o contorno e a chapa, e o
    modelo desenha o que se nomeia — a mesma licao do softbox e do xadrez.
    """
    comp = caption.get("compositional_deconstruction", {})
    comp["background"] = FUNDO_RECORTAVEL
    for e in comp.get("elements") or []:
        if e.get("type") != "text":
            continue
        # O vazado sai ANTES da cor: "on a white box" so casa enquanto o
        # "white" ainda esta na frase.
        desc = _ADORNO.sub("", str(e.get("desc", "")))
        desc = _COR_COM_MODIFICADOR.sub("", _VAZADO.sub("", desc))
        # Tirar a cor deixa a preposicao orfa: "text in , centered" le mal e
        # o modelo tenta dar sentido ao que sobrou.
        desc = re.sub(r"\b(in|of|with)\s*(?=[,.]|$)", "", desc)
        desc = re.sub(r"\s+([,.])", r"\1", desc)
        desc = re.sub(r"\s{2,}", " ", desc).strip(" ,;.")
        e["desc"] = " ".join(filter(None, (desc, LETRA_CHAPADA)))
    caption["high_level_description"] = (
        "Solid pure white lettering on a plain black field. " +
        str(caption.get("high_level_description", "")))
    return caption


def minificar(caption: dict) -> str:
    return json.dumps(caption, ensure_ascii=False, separators=(",", ":"))
