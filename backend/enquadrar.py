"""Onde o texto pode pousar numa foto sem atropelar o assunto.

O LLM que escreve a caption do Ideogram nunca ve a imagem de fundo: para ele a
peca e uma folha em branco. Num retrato de estudio isso pos "OFICIO" em cima
dos olhos e a chamada em cima da boca — o texto estava perfeito e a peca,
inutil.

A saida nao e pedir ao modelo que adivinhe, e MEDIR a foto. Um diagramador
olha a imagem e poe o titulo onde ha superficie calma; e isso que o codigo faz
aqui, e de forma deterministica: mede a agitacao de cada linha da imagem e
devolve as faixas mais quietas, na ordem em que aparecem.

A agitacao sozinha nao bastou, e o teste mostrou por que: BOCHECHA LISA TEM
POUCA BORDA. No retrato de estudio a faixa do nariz a boca foi medida como uma
das mais calmas da imagem, e por ela o texto cairia bem no meio do rosto. A
energia de borda sabe onde ha detalhe, nao sabe o que e assunto.

Por isso o rosto entra como uma regra propria, por cima da medida. A deteccao
e a cascata de Haar do OpenCV: roda em milissegundos na CPU e nao toca a GPU —
usar o SAM 3, que ja esta no projeto, custaria uma troca de modelo na placa a
cada geracao.
"""

import io
import pathlib

import cv2
import numpy
from PIL import Image, ImageFilter, ImageStat

# A imagem e reduzida antes de medir. A 160 px de largura o grao e o ruido
# somem e o que sobra e a estrutura, que e o que importa aqui — e a conta fica
# instantanea.
LARGURA_DE_ANALISE = 160

# Uma faixa util precisa caber uma linha de texto com folga. Em unidades de
# bbox do Ideogram (0 a 1000), 70 e a altura de um rotulo pequeno.
ALTURA_MINIMA = 70

# Cerca de 9% da altura da imagem. Larga o bastante para atravessar um fio
# de cabelo ou uma dobra, estreita o bastante para nao borrar a fronteira
# entre o rosto e o fundo.
JANELA_DE_SUAVIZACAO = 21


def perfil_de_agitacao(dados: bytes) -> list[float]:
    """Quanto cada linha da imagem tem de borda, de 0 (lisa) a 1 (agitada).

    Trabalha sobre a imagem inteira em escala de cinza: o filtro de contorno
    responde a bordas, e a media por linha diz se aquela altura da foto e
    superficie limpa ou detalhe.
    """
    im = Image.open(io.BytesIO(dados)).convert("L")
    altura = max(1, round(im.height * LARGURA_DE_ANALISE / im.width))
    im = im.resize((LARGURA_DE_ANALISE, altura), Image.BILINEAR)
    bordas = im.filter(ImageFilter.FIND_EDGES)

    linhas = []
    for y in range(altura):
        faixa = bordas.crop((0, y, LARGURA_DE_ANALISE, y + 1))
        linhas.append(ImageStat.Stat(faixa).mean[0])

    # A borda da propria imagem sempre acende no filtro; a primeira e a ultima
    # linha herdam o valor da vizinha para nao virarem falsos picos.
    if altura >= 3:
        linhas[0], linhas[-1] = linhas[1], linhas[-2]

    # Sem suavizar, um unico fio de cabelo ou uma dobra de tecido cria um pico
    # de uma linha que parte a faixa calma em dois pedacos curtos demais para
    # serem usados. O que interessa aqui e a estrutura da foto, nao a linha.
    linhas = _suavizar(linhas, JANELA_DE_SUAVIZACAO)

    teto = max(linhas) or 1.0
    return [v / teto for v in linhas]


def _suavizar(valores: list[float], janela: int) -> list[float]:
    meio = janela // 2
    return [sum(valores[max(0, i - meio):i + meio + 1])
            / len(valores[max(0, i - meio):i + meio + 1])
            for i in range(len(valores))]


# A cascata acha o rosto, nao a cabeca. Um titulo encostando na testa ou no
# queixo fica tao ruim quanto em cima dos olhos, entao a area protegida cresce
# para cima (cabelo) e para baixo (queixo e pescoco).
FOLGA_ACIMA = 0.7
FOLGA_ABAIXO = 0.5
VIZINHOS = 8
LARGURA_MINIMA_DO_ROSTO = 0.10

_cascata = None


def _detector():
    global _cascata
    if _cascata is None:
        caminho = pathlib.Path(cv2.data.haarcascades) / \
            "haarcascade_frontalface_default.xml"
        _cascata = cv2.CascadeClassifier(str(caminho))
    return _cascata


def faixas_de_rosto(dados: bytes) -> list[tuple]:
    """Alturas ocupadas por rostos, em unidades de bbox (0 a 1000)."""
    im = Image.open(io.BytesIO(dados)).convert("L")
    escala = LARGURA_DE_ANALISE * 3 / im.width      # 480 px: a cascata precisa
    im = im.resize((round(im.width * escala),       # de mais detalhe que a
                    round(im.height * escala)), Image.BILINEAR)  # medida de borda
    # Na rua a noite a cascata achou um "rosto" no asfalto, entre os reflexos.
    # Dois filtros derrubam isso sem perder o retrato: mais vizinhos exigidos
    # para confirmar a deteccao, e um tamanho minimo — um rosto com menos de
    # um decimo da largura da foto e um figurante ao fundo, nao o assunto da
    # peca, e proteger a faixa dele desperdicaria metade da pagina.
    minimo = round(im.width * LARGURA_MINIMA_DO_ROSTO)
    achados = _detector().detectMultiScale(numpy.array(im), 1.1, VIZINHOS,
                                           minSize=(minimo, minimo))
    faixas = []
    for _, y, _, altura in achados:
        topo = (y - altura * FOLGA_ACIMA) / im.height * 1000
        base = (y + altura * (1 + FOLGA_ABAIXO)) / im.height * 1000
        faixas.append((max(0, round(topo)), min(1000, round(base))))
    return sorted(faixas)


def faixas_calmas(perfil: list[float], limite: float = 0.35) -> list[tuple]:
    """Trechos contiguos abaixo do limite, em unidades de bbox (0 a 1000).

    Devolve (inicio, fim, agitacao_media), da mais calma para a mais agitada,
    ja descartando o que e estreito demais para receber uma linha de texto.
    """
    if not perfil:
        return []
    passo = 1000 / len(perfil)
    achadas, inicio = [], None
    for i, v in enumerate(perfil + [1.0]):     # o 1.0 fecha a ultima faixa
        if v <= limite and inicio is None:
            inicio = i
        elif v > limite and inicio is not None:
            trecho = perfil[inicio:i]
            achadas.append((round(inicio * passo), round(i * passo),
                            sum(trecho) / len(trecho)))
            inicio = None
    largas = [f for f in achadas if f[1] - f[0] >= ALTURA_MINIMA]
    return sorted(largas, key=lambda f: f[2])


def _subtrair(calmas: list, proibidas: list) -> list:
    """Tira as faixas de rosto de dentro das faixas calmas.

    Uma faixa calma cortada ao meio por um rosto vira duas; cada pedaco so
    sobrevive se ainda couber uma linha de texto.
    """
    saida = []
    for inicio, fim, agitacao in calmas:
        pedacos = [(inicio, fim)]
        for pa, pb in proibidas:
            novos = []
            for a, b in pedacos:
                if pb <= a or pa >= b:
                    novos.append((a, b))
                    continue
                if pa > a:
                    novos.append((a, pa))
                if pb < b:
                    novos.append((pb, b))
            pedacos = novos
        saida += [(a, b, agitacao) for a, b in pedacos
                  if b - a >= ALTURA_MINIMA]
    return sorted(saida, key=lambda f: f[2])


# Respiro entre dois blocos ao reempacotar, em unidades de bbox.
RESPIRO = 24

# Quando o que sobra da pagina e menor que a soma dos blocos, eles encolhem
# em vez de o encaixe desistir — foi o que aconteceu no primeiro retrato,
# onde faltavam 53 unidades de 498 e o texto voltou inteiro para cima do
# rosto. Abaixo deste piso a peca vira ilegivel e e melhor nao mexer.
ESCALA_MINIMA = 0.65


def _livres(proibidas: list) -> list:
    """O que sobra da pagina depois de tirar as faixas proibidas."""
    trechos, cursor = [], 0
    for a, b in sorted(proibidas):
        if a > cursor:
            trechos.append((cursor, a))
        cursor = max(cursor, b)
    if cursor < 1000:
        trechos.append((cursor, 1000))
    return trechos


def encaixar(caption: dict, dados: bytes) -> dict:
    """Tira o texto de cima do rosto, mantendo a ordem de leitura.

    O rosto e restricao DURA; faixa calma e so preferencia. Foi o teste que
    ensinou a diferenca: uma primeira versao tratava tudo como preferencia,
    e num retrato ela mudou o titulo de cima dos olhos para cima da boca —
    trocou um defeito por outro, e pior, porque parecia resolvido.

    So age quando ha conflito de verdade. Se nenhum bloco encosta num rosto, a
    caption volta intacta: mexer no que esta bom so introduz risco. E se o que
    sobra da pagina nao comporta os blocos, tambem volta intacta — nao havendo
    lugar bom, inventar um seria pior que a escolha do LLM.
    """
    comp = caption.get("compositional_deconstruction", {})
    textos = [e for e in comp.get("elements") or []
              if e.get("type") == "text"
              and isinstance(e.get("bbox"), list) and len(e["bbox"]) == 4]
    if not textos:
        return caption

    rostos = faixas_de_rosto(dados)
    if not rostos:
        return caption

    textos.sort(key=lambda e: e["bbox"][0])
    encosta = [e for e in textos
               if any(a < e["bbox"][2] and b > e["bbox"][0] for a, b in rostos)]
    if not encosta:
        return caption

    alturas = [e["bbox"][2] - e["bbox"][0] for e in textos]
    preciso = sum(alturas) + RESPIRO * (len(textos) - 1)

    # Entre os trechos livres, o mais calmo que comporte todos os blocos. Usar
    # so o maior poria o texto na area mais agitada quando as duas coubessem.
    perfil = perfil_de_agitacao(dados)
    livres = _livres(rostos)
    cabem = [t for t in livres if t[1] - t[0] >= preciso]
    escala = 1.0
    if not cabem:
        maior = max(livres, key=lambda t: t[1] - t[0], default=None)
        if maior is None:
            return caption
        folga = (maior[1] - maior[0] - RESPIRO * (len(textos) - 1))
        escala = folga / sum(alturas) if sum(alturas) else 0
        if escala < ESCALA_MINIMA:
            return caption
        # Arredondar para cima devolvia uma soma maior que o espaco medido,
        # e o primeiro bloco acabava uma unidade DENTRO do rosto — visto na
        # foto de duas pessoas. Truncar nunca estoura a faixa.
        alturas = [max(1, int(a * escala)) for a in alturas]
        preciso = sum(alturas) + RESPIRO * (len(textos) - 1)
        cabem = [maior]
    escolhido = min(cabem, key=lambda t: _agitacao_media(perfil, t))

    # Empacota de cima para baixo, centrando o conjunto no trecho: a ordem de
    # leitura e preservada por construcao.
    inicio, fim = escolhido
    topo = max(inicio, inicio + ((fim - inicio) - preciso) / 2)
    for e, altura in zip(textos, alturas):
        e["bbox"] = [round(topo), e["bbox"][1], round(topo + altura), e["bbox"][3]]
        topo += altura + RESPIRO
    return caption


def _agitacao_media(perfil: list[float], trecho: tuple) -> float:
    if not perfil:
        return 0.0
    a = round(trecho[0] / 1000 * len(perfil))
    b = max(a + 1, round(trecho[1] / 1000 * len(perfil)))
    fatia = perfil[a:b] or [0.0]
    return sum(fatia) / len(fatia)


# --------------------------------------------------------------- contraste

# Razao de contraste da WCAG. 3:1 e o piso para texto grande; abaixo disso a
# linha comeca a sumir, que foi o que aconteceu com "ENSAIO FOTOGRAFICO" em
# tinta clara sobre uma camiseta branca.
CONTRASTE_MINIMO = 3.0


def _luminancia(canal: float) -> float:
    c = canal / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luz(rgb: tuple) -> float:
    r, g, b = (_luminancia(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _razao(a: float, b: float) -> float:
    claro, escuro = max(a, b), min(a, b)
    return (claro + 0.05) / (escuro + 0.05)


def _do_hex(cor: str) -> tuple:
    c = cor.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def contraste_por_bloco(caption: dict, dados: bytes, tinta: str) -> list:
    """Contraste de cada bloco de texto contra o pedaco de foto sob ele.

    Mede a regiao exata da bbox, nao a foto inteira: no ensaio de costas o
    titulo caia sobre cabelo escuro (contraste otimo) e a linha seguinte sobre
    a camiseta branca (contraste 1.2). Uma media da imagem inteira teria dito
    que estava tudo bem.
    """
    comp = caption.get("compositional_deconstruction", {})
    textos = [e for e in comp.get("elements") or []
              if e.get("type") == "text" and isinstance(e.get("bbox"), list)]
    if not textos:
        return []

    im = Image.open(io.BytesIO(dados)).convert("RGB")
    luz_tinta = _luz(_do_hex(tinta))
    saida = []
    for i, e in enumerate(textos):
        caixa = _em_pixels(e["bbox"], im)
        vizinhas = [_em_pixels(o["bbox"], im)
                    for j, o in enumerate(textos) if j != i]
        media = _media_exclusiva(im, caixa, vizinhas)
        saida.append((e.get("text", ""), _razao(luz_tinta, _luz(media))))
    return saida


def _em_pixels(bbox: list, im) -> tuple:
    y1, x1, y2, x2 = bbox
    return (round(x1 / 1000 * im.width), round(y1 / 1000 * im.height),
            max(1, round(x2 / 1000 * im.width)),
            max(1, round(y2 / 1000 * im.height)))


def _media_exclusiva(im, caixa: tuple, vizinhas: list) -> list:
    """Cor media da caixa, ignorando o que outro bloco ja ocupa.

    A medicao acontece ANTES da composicao, entao ela ve a foto. Eu supunha
    que isso errava pouco porque so as letras sao pintadas — medi e a
    suposicao era falsa: tipografia de display cobre de 36% a 67% da propria
    caixa. Onde dois blocos se sobrepoem, boa parte do que o segundo "ve" ja
    vai estar coberta pelo primeiro.

    Caixas sobrepostas so existem no layout manual. A area exclusiva e a
    unica sobre a qual da para afirmar alguma coisa; quando nao sobra nenhuma,
    a caixa inteira volta a valer, que e o comportamento antigo.
    """
    recorte = im.crop(caixa)
    mascara = Image.new("L", recorte.size, 255)
    houve_corte = False
    for vx1, vy1, vx2, vy2 in vizinhas:
        ix1, iy1 = max(caixa[0], vx1), max(caixa[1], vy1)
        ix2, iy2 = min(caixa[2], vx2), min(caixa[3], vy2)
        if ix2 > ix1 and iy2 > iy1:
            mascara.paste(0, (ix1 - caixa[0], iy1 - caixa[1],
                              ix2 - caixa[0], iy2 - caixa[1]))
            houve_corte = True
    if not houve_corte:
        return ImageStat.Stat(recorte).mean
    if not mascara.getbbox():          # nada exclusivo sobrou
        return ImageStat.Stat(recorte).mean
    return ImageStat.Stat(recorte, mascara).mean


def melhor_tinta(caption: dict, dados: bytes, candidatas: list) -> str:
    """A cor que deixa o bloco MAIS FRACO o mais legivel possivel.

    Otimiza o pior caso, nao a media: uma peca em que uma linha some ja esta
    errada, por melhor que estejam as outras.
    """
    return max(candidatas,
               key=lambda c: min((r for _, r in
                                  contraste_por_bloco(caption, dados, c)),
                                 default=0))


def tintas_por_bloco(caption: dict, dados: bytes, base: str,
                     paleta: list) -> list:
    """Para cada bloco, a melhor cor da paleta — e so quando vale a troca.

    A tinta escolhida pelo usuario vale enquanto der conta. Trocar a cor de um
    bloco que ja esta legivel quebraria a unidade da peca por nada; a troca so
    acontece onde a linha sumiria.

    Existe porque uma cor so nao resolve toda foto: no ensaio de costas o
    titulo cai sobre cabelo escuro, a chamada sobre camiseta branca e o rodape
    sobre calca escura. Em claro some a chamada, em escuro some o rodape.
    """
    comp = caption.get("compositional_deconstruction", {})
    textos = [e for e in comp.get("elements") or []
              if e.get("type") == "text" and isinstance(e.get("bbox"), list)]
    razoes = dict(enumerate(r for _, r in
                            contraste_por_bloco(caption, dados, base)))

    saida = []
    for i, e in enumerate(textos):
        if razoes.get(i, 99) >= CONTRASTE_MINIMO:
            continue
        um = {"compositional_deconstruction": {"elements": [e]}}
        melhor = max(paleta, key=lambda c: contraste_por_bloco(um, dados, c)[0][1])
        ganho = contraste_por_bloco(um, dados, melhor)[0][1]
        # Trocar por algo que tambem some nao ajuda ninguem: melhor manter a
        # cor da peca e deixar o aviso falar.
        if ganho >= CONTRASTE_MINIMO:
            saida.append({"indice": i, "bbox": list(e["bbox"]), "cor": melhor,
                          "texto": e.get("text", ""), "razao": ganho})
    return _com_folga(saida, textos, base)


# O glifo nao respeita a caixa: o rabo do Q, um acento ou uma perna descem
# alguns pixels abaixo dela. Repintar so o retangulo deixava esses pedacos na
# cor base — visivel como uma lasca clara sob o Q de "QUARTA".
FOLGA_DE_REPINTURA = 18


def _com_folga(trocas: list, textos: list, base: str) -> list:
    """Estica cada bloco repintado, sem invadir vizinho de outra cor."""
    cor_final = {i: base for i in range(len(textos))}
    for t in trocas:
        cor_final[t["indice"]] = t["cor"]

    for t in trocas:
        i = t["indice"]
        y1, x1, y2, x2 = t["bbox"]
        acima, abaixo = FOLGA_DE_REPINTURA, FOLGA_DE_REPINTURA
        for j, outro in enumerate(textos):
            if j == i or cor_final[j] == t["cor"]:
                continue        # mesma cor: invadir nao muda nada
            oy1, _, oy2, _ = outro["bbox"]
            if oy2 <= y1:
                acima = min(acima, max(0, (y1 - oy2) // 2))
            elif oy1 >= y2:
                abaixo = min(abaixo, max(0, (oy1 - y2) // 2))
            else:
                # Vizinho SOBREPOSTO. Os dois ramos acima so conheciam
                # "inteiramente acima" e "inteiramente abaixo", entao este
                # caso escapava e levava os 18 pontos inteiros para dentro de
                # letra alheia, repintando-a com a cor errada.
                #
                # Caixas sobrepostas so aparecem no layout manual, onde o
                # usuario desenha onde quiser. Ali a invasao ja e escolha
                # dele; o que nao pode e o codigo PIORAR a sobreposicao.
                acima = abaixo = 0
                break
        t["bbox"] = [max(0, y1 - acima), x1, min(1000, y2 + abaixo), x2]
    return trocas


# --------------------------------------------------------- texto ja na foto

# MSER: regioes de brilho estavel. Letra e uma delas, com proporcao e tamanho
# limitados, e aparece ALINHADA com outras iguais. E o detector de texto
# classico, anterior as redes, e roda em CPU sem baixar modelo nenhum.
#
# ELE E AVISO, NAO REGRA — e a medicao e que decidiu isso. Varri altura e
# largura minimas e em nenhum ponto consegui separar o letreiro da mercearia
# das manchas alinhadas do asfalto molhado na rua a noite. Como restricao dura
# ele empurraria o texto de uma peca que hoje sai bem; como aviso, mesmo o
# "falso" positivo da rua e defensavel, porque aquela foto tem letreiros de
# verdade e o texto vai competir com eles.
LARGURA_MSER = 480
ALTURA_MINIMA_DA_LETRA = 0.05     # fracao da altura da foto
LARGURA_MINIMA_DA_LINHA = 0.50    # fracao da largura da foto
# Numero de REGIOES ESTAVEIS na linha, nao de letras: o MSER acha varias por
# glifo, aninhadas, e quanto mais nitida e contrastada a tipografia, mais ele
# acha. Foi a unica medida que separou os dois casos.
#
# Medi tambem variacao de altura e de espacamento entre as regioes, apostando
# que letra seria mais regular que mancha. Nao separou: na fachada a variacao
# de altura ia de 0.01 a 0.10 e na rua de 0.02 a 0.10, sobrepostas. Ja a
# contagem separou limpo — fachada com grupos de 16, 19 e 105; asfalto
# molhado com 5, 8 e 11.
REGIOES_POR_LINHA = 15


def faixas_de_texto(dados: bytes) -> list:
    """Alturas onde a foto ja traz tipografia grande, em unidades de bbox."""
    im = Image.open(io.BytesIO(dados)).convert("L")
    im = im.resize((LARGURA_MSER, round(im.height * LARGURA_MSER / im.width)),
                   Image.BILINEAR)
    a = numpy.array(im)
    detector = cv2.MSER_create(delta=5, min_area=60,
                               max_area=int(a.size * 0.02))
    regioes, _ = detector.detectRegions(a)

    letras = []
    for r in regioes:
        x, y, w, h = cv2.boundingRect(r.reshape(-1, 1, 2))
        if w and h and 0.15 < w / h < 2.0 and 0.01 < h / a.shape[0] < 0.12:
            letras.append((x, y, w, h))

    # Agrupa por linha de base e corpo parecidos: e o alinhamento que separa
    # uma palavra de um punhado de manchas soltas.
    passo = a.shape[0] * 0.02
    grupos = {}
    for caixa in letras:
        grupos.setdefault((round(caixa[1] / passo), round(caixa[3] / passo)),
                          []).append(caixa)

    faixas = []
    for g in grupos.values():
        if len(g) < REGIOES_POR_LINHA:
            continue
        corpo = sum(h for _, _, _, h in g) / len(g)
        vao = max(x + w for x, _, w, _ in g) - min(x for x, _, _, _ in g)
        if (corpo / a.shape[0] >= ALTURA_MINIMA_DA_LETRA
                and vao / a.shape[1] >= LARGURA_MINIMA_DA_LINHA):
            topo = min(y for _, y, _, _ in g) / a.shape[0] * 1000
            base = max(y + h for _, y, _, h in g) / a.shape[0] * 1000
            faixas.append((round(topo), round(base)))
    return _unir(faixas)


def _unir(faixas: list) -> list:
    saida = []
    for a, b in sorted(faixas):
        if saida and a <= saida[-1][1]:
            saida[-1] = (saida[-1][0], max(saida[-1][1], b))
        else:
            saida.append((a, b))
    return saida


def texto_sobre_texto(caption: dict, dados: bytes) -> list:
    """Blocos que vao cair em cima de tipografia que ja existe na foto.

    O aviso de contraste nao pega este caso: na fachada da mercearia a linha
    caiu sobre o letreiro pintado com contraste otimo — creme sobre verde
    escuro — e mesmo assim nenhum dos dois textos se lia. Legibilidade nao e
    so diferenca de luminancia.
    """
    faixas = faixas_de_texto(dados)
    if not faixas:
        return []
    comp = caption.get("compositional_deconstruction", {})
    return [e.get("text", "") for e in comp.get("elements") or []
            if e.get("type") == "text" and isinstance(e.get("bbox"), list)
            and any(a < e["bbox"][2] and b > e["bbox"][0] for a, b in faixas)]
