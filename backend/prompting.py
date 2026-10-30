"""Expansao de prompt para os modelos de pipeline simples.

A escrita da caption do Ideogram 4 mora em `ideogram.py` — sao problemas
diferentes e cresceram demais para um arquivo so.
"""

import re

import comfy
import workflows

# Base comum aos dois modos de expansao.
#
# Cada linha aqui saiu de um erro observado, nao de teoria:
#
# "no metaphor" — o modelo escreveu "smoke swirling like secrets", e um gerador
#   de imagem nao tem o que fazer com "segredos".
#
# O paragrafo do portugues — em "detetive PARADO sob um poste", o modelo leu o
#   participio como sobrenome e escreveu "Detective Parado". E em "modelo de
#   casaco vermelho", uma palavra neutra em portugues, ele escolheu o genero
#   sozinho ("her pose") e devolveu uma mulher onde o teste anterior dera um
#   homem. Sao dois erros do mesmo tipo: traduzir sem saber que o original e
#   portugues.
#
# O paragrafo sobre luz — o defeito mais reproduzivel que medimos. O LLM
#   escrevia "two softboxes at 45-degree angles" e o modelo DESENHAVA os
#   softboxes dentro do quadro. Apareceu no estilo 3D em Krea, Klein, Z-Image e
#   Mage, nos dois modos de expansao: quatro modelos, duas condicoes. E a mesma
#   licao da LoRA de angulo e da regra de corte — descrever o EFEITO funciona,
#   ditar o meio nao.
_BASE = """You are a prompt engineer for text-to-image models.
Expand the user's idea into one vivid, concrete English prompt of at most 90 words.
Describe only what a camera would see: no metaphor, no simile, no abstractions.
Do not invent text or logos unless the user asked for them.

The user's idea arrives in Portuguese. Translate it faithfully. Common nouns
and adjectives are never proper names — "detetive parado" is a detective who is
standing still, not a person called Parado.

When the Portuguese word does not mark gender ("modelo", "criança",
"profissional", "artista"), refer to that person by repeating the noun every
time — "the model raises the model's hand" reads oddly, so prefer "the model
raises a hand". Never use he, she, his or her for that person.

Describe light by its effect, never by the equipment that makes it. Write where
it comes from, how hard or soft it is, its colour and the shadows it leaves.
Never name a softbox, a lamp, a reflector, a light stand or a studio rig: the
image model draws whatever you name, and a softbox named in the prompt ends up
standing inside the picture.

Reply with the prompt only, no preamble."""

# Dois modos, porque medimos que um so nao serve.
#
# Em quatro testes, a expansao livre mexeu em algo NAO pedido em tres deles:
# virou plano geral em macro de maos (pescador), trocou o genero do sujeito
# (modelo de casaco) e promoveu o violoncelo a metade do quadro (violoncelista).
# No quarto — o detetive — foi justamente essa liberdade que transformou uma rua
# de suburbio em cena de filme.
#
# Ou seja: o problema nao era o gabarito estar errado, era ter um gabarito so.
EXPANSOES = {
    # A ancoragem do ultimo paragrafo veio de um teste que falhou. "Nao mude o
    # enquadramento" nao tem objeto quando o usuario nunca declarou um: no
    # prompt vago do pescador, o modo fiel escreveu "his hands knotting frayed
    # netting against the planks" e o resultado cortou a cabeca do homem —
    # ficou MAIS fechado que o modo livre. A regra era obedecida e mesmo assim
    # o quadro mudava, porque escrever exige escolher.
    #
    # ESTE GABARITO E CURTO DE PROPOSITO. Tentei separar a regra em dois casos
    # (pessoa e objeto) para resolver o relogio de perfil do estilo Produto, e
    # medi tres formulacoes:
    #
    #   frase unica, gabarito curto ...... relogio ruim, pescador BOM
    #   separada pessoa/objeto ........... relogio BOM,  pescador ruim
    #   separada + proibicao solta ....... relogio ruim, pescador ruim
    #
    # Nenhuma acertou as duas. O padrao aponta para capacidade, nao redacao: a
    # cada regra nova o modelo de 8B sustenta pior as anteriores. A exigencia
    # especifica do produto foi entao para o `positivo` do estilo, que vai
    # direto ao modelo de imagem sem disputar espaco aqui.
    "fiel": _BASE + """

Keep every decision the user already made. Do not change the framing, the camera
distance or angle, which element dominates the frame, the setting, or the
subject's gender, age, number or identity. Do not add new objects or people.
Enrich only what the user left unsaid: material, texture, surface, the quality
and direction of the light, the weather and the mood.

Never crop the subject out of the frame. The person or object the user named
must be visible and recognisable, with the head included when it is a person,
unless the user explicitly asked for a close-up or a detail shot.""",
    "livre": _BASE + """

You may choose the camera angle, the framing and the lens, and you may add
supporting detail that fits the genre, as long as the subject the user named
stays the subject.""",
}

EXPANSAO_PADRAO = "fiel"


# Palavras que marcam genero em portugues. Se alguma aparece, o usuario DECIDIU
# e nada deve ser mexido.
_GENERO_DITO = re.compile(
    r"\b(mulher(es)?|homem|homens|menina|menino|garota|garoto|moca|moça|rapaz|"
    r"senhora|senhor|dama|ele|ela|feminin[ao]|masculin[ao]|"
    r"atriz|ator|bailarin[ao]|cantor(a)?|dançarin[ao]|"
    r"m[aã]e|pai|filha|filho|irm[aã]|irmao|irmão|esposa|marido|noiva|noivo)\b",
    re.I)

# A troca precisa respeitar a funcao do pronome, senao estraga o ingles. Uma
# primeira versao trocava tudo por "their" e produzia "behind their" (devia ser
# "them") e "They holds" (concordancia quebrada).
#
# Possessivo vira ARTIGO, nao "their": "the coat is wet" le melhor que "their
# coat is wet" e nao levanta a questao de quantas pessoas ha na cena.
_POSSESSIVO = re.compile(r"\b(her|his)\b(?=\s+[a-z])", re.I)
_OBJETO = re.compile(r"\b(her|him)\b", re.I)
_SUJEITO = re.compile(r"\b(she|he)\b(\s+)(\w+)", re.I)

# Verbos irregulares na terceira pessoa. Os regulares perdem o -s final.
_SEM_S = {"is": "are", "has": "have", "does": "do", "was": "were",
          "goes": "go", "stands": "stand", "holds": "hold", "wears": "wear"}


def neutralizar(ingles: str, ideia_pt: str) -> str:
    """Tira pronome de genero quando o usuario nao declarou genero nenhum.

    A instrucao no gabarito reduz o problema mas nao resolve: num teste o modo
    fiel escorregou para "Her posture" e o livre ficou limpo; ao reformular a
    regra, os dois trocaram de lado. Um modelo local de 8B nao segue restricao
    sutil de forma confiavel, entao a garantia vem daqui, nao da persuasao.

    So age quando a ideia em portugues NAO marca genero — se o usuario escreveu
    "uma mulher de casaco", o "her" e a traducao correta e deve ficar.
    """
    if _GENERO_DITO.search(ideia_pt):
        return ingles

    def como_veio(original: str, novo: str) -> str:
        return novo.capitalize() if original[0].isupper() else novo

    def sujeito(m):
        verbo = m.group(3)
        neutro = _SEM_S.get(verbo.lower())
        if neutro is None and verbo.lower().endswith("s"):
            neutro = verbo[:-1]
        return como_veio(m.group(1), "they") + m.group(2) + (neutro or verbo)

    texto = _SUJEITO.sub(sujeito, ingles)
    texto = _POSSESSIVO.sub(lambda m: como_veio(m.group(0), "the"), texto)
    return _OBJETO.sub(lambda m: como_veio(m.group(0), "them"), texto)


async def expandir(ideia: str, seed: int = 0, orientacao: str = "",
                   modo: str = EXPANSAO_PADRAO) -> str:
    """Enriquece um prompt curto. Usado pelos modelos de pipeline simples.

    `orientacao` vem do estilo escolhido e diz ao modelo COMO escrever — por
    exemplo, "escreva como fotografia: nomeie a lente, a luz e os materiais".
    Sem ela o LLM devolve sempre o mesmo registro, e o estilo so agia depois,
    no acrescimo ao prompt final.

    Este parametro FALTAVA: o app.py ja o passava e a funcao nao o aceitava,
    entao toda geracao com "Enriquecer o prompt" ligado falhava com
    "expandir() takes from 1 to 2 positional arguments but 3 were given" —
    e essa caixa vem marcada por padrao.

    `modo` escolhe entre "fiel" e "livre"; ver EXPANSOES.
    """
    instrucao = EXPANSOES.get(modo, EXPANSOES[EXPANSAO_PADRAO])
    if orientacao.strip():
        instrucao += f"\n\nStyle direction: {orientacao.strip()}"
    instrucao += f"\n\nUser idea: {ideia}"
    saidas = await comfy.executar(
        workflows.escrever_texto(instrucao, 320, criativo=True, seed=seed))
    texto = (await comfy.texto_de(saidas)).strip()
    if not texto:
        return ideia
    return neutralizar(texto, ideia)


# O gabarito oficial tem uma secao sobre fundo transparente que o modelo de 8B


# Cinema Studio, "Director mode". Testado em 24/10/2026: com "shot on ARRI
# Alexa 65" no prompt, o Z-Image e o Krea desenharam o personagem SEGURANDO a
# camera. Aqui o LLM descreve so o que aparece no quadro, e o equipamento vira
# qualidade da imagem (grao, profundidade, perspectiva), nunca objeto.
DIRETOR = (
    "You are a director of photography writing the prompt for ONE film frame "
    "for an image model. Write one paragraph of 70 to 110 words in English, "
    "describing only what is visible in the frame: the framing, the subject and "
    "what they are doing, the place, the light, the colors and the texture of "
    "the image. Turn every technical choice below into what it LOOKS like "
    "(grain, depth of field, perspective, distortion, color), never into an "
    "object. The image is seen through the camera: never mention cameras, "
    "lenses, film stock, brands, crews or filmmaking equipment, and nobody in "
    "the frame holds or uses a camera. Keep every person, object and action of "
    "the scene. If the scene is in Portuguese, write in English anyway. Output "
    "only the paragraph, no title, no quotes."
)


async def diretor(cena: str, enquadramento: str, visual: str, seed: int = 0) -> str:
    instrucao = (f"{DIRETOR}\n\nFraming: {enquadramento or 'free'}\n"
                 f"Look of the shot: {visual or 'natural cinematic look'}\n"
                 f"Scene: {cena}")
    saidas = await comfy.executar(
        workflows.escrever_texto(instrucao, 400, criativo=True, seed=seed))
    texto = (await comfy.texto_de(saidas)).strip().strip('"')
    return neutralizar(texto, cena) if texto else ""


# 3D render -> Video, botao "Write it for me" (30/10/2026): o leigo digita poucas palavras
# (ate em portugues) e o modelo de texto local escreve o NOME do elemento e a CENA no formato
# que funcionou nos testes. O resto da instrucao do quadro o app monta (AbaApps.instrucaoMaquete).
MAQUETE = {
    "nome": (
        "Write the name of ONE object or character for an image model, in English: a short noun phrase "
        "of 3 to 12 words with its type, color, make or model if any, and its most distinctive details "
        "(for example: green Lamborghini Huracan with black wheels). No verbs, no place, no light, no "
        "camera words. If the idea is in Portuguese, write in English anyway. Output only the phrase."
    ),
    "cena": (
        "Write ONE sentence of 15 to 40 words in English describing a film scene for an image model: what "
        "the main object or character does, the place, the time of day and light, and the mood. Never "
        "mention cameras, lenses, renders, 3D, blocks or how the shot is made. If the idea is in "
        "Portuguese, write in English anyway. Output only the sentence."
    ),
}


async def maquete(ideia: str, campo: str, objeto: str = "", seed: int = 0) -> str:
    instrucao = MAQUETE[campo]
    if campo == "cena" and objeto.strip():
        instrucao += f"\n\nThe main object is: {objeto.strip()}"
    instrucao += f"\n\nUser idea: {ideia}"
    saidas = await comfy.executar(
        workflows.escrever_texto(instrucao, 120, criativo=True, seed=seed))
    texto = (await comfy.texto_de(saidas)).strip().strip('"').strip()
    return texto.splitlines()[0].strip() if texto else ""
