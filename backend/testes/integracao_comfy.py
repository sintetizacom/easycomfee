# -*- coding: utf-8 -*-
r"""Valida grafos do projeto contra o /object_info do ComfyUI vivo.

Nao envia nada a /prompt: nenhum modelo e carregado e nenhuma tarefa e
enfileirada. O teste confere classes, nomes de entradas (inclusive autogrow e
DynamicCombo), obrigatorios, faixas/enums e tipos das conexoes.

Rodar com:

    backend\.venv\Scripts\python.exe backend\testes\integracao_comfy.py
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent))

import presets as P      # noqa: E402
import workflows as W    # noqa: E402
import config           # noqa: E402

_falhas = []


def falhar(texto):
    _falhas.append(texto)


def catalogo_vivo(base):
    try:
        with urllib.request.urlopen(f"{base}/object_info", timeout=20) as resposta:
            return json.load(resposta)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as e:
        raise RuntimeError(f"ComfyUI não respondeu em {base}: {e}") from e


def campos(schema):
    entrada = schema.get("input", {})
    todos = {}
    for secao in ("required", "optional"):
        todos.update(entrada.get(secao, {}))
    return todos


def opcao_dinamica(especificacao, valor):
    opcoes = especificacao[1].get("options", [])
    return next((o for o in opcoes if o.get("key") == valor), None)


def resolver_especificacao(schema, entradas, chave):
    """Resolve inclusive `model.images.image_1` e `images.image_1`."""
    partes = chave.split(".")
    atuais = campos(schema)
    prefixo = []
    i = 0
    while i < len(partes):
        parte = partes[i]
        if parte not in atuais:
            return None
        especificacao = atuais[parte]
        prefixo.append(parte)
        i += 1
        if i == len(partes):
            return especificacao

        tipo = especificacao[0]
        opcoes = especificacao[1] if len(especificacao) > 1 else {}
        if tipo == "COMFY_DYNAMICCOMBO_V3":
            valor = entradas.get(".".join(prefixo))
            opcao = opcao_dinamica(especificacao, valor)
            if not opcao:
                return None
            atuais = {}
            for secao in ("required", "optional"):
                atuais.update(opcao.get("inputs", {}).get(secao, {}))
            continue
        if tipo == "COMFY_AUTOGROW_V3":
            nome = partes[i]
            modelo = opcoes.get("template", {})
            nomes = modelo.get("names", [])
            if nomes and nome not in nomes:
                return None
            internos = {}
            for secao in ("required", "optional"):
                internos.update(modelo.get("input", {}).get(secao, {}))
            # Cada instancia do autogrow recebe o tipo do unico campo do
            # template; o nome da instancia substitui o nome desse campo.
            if len(internos) != 1 or i != len(partes) - 1:
                return None
            return next(iter(internos.values()))
        return None
    return None


def obrigatorios(schema, entradas):
    faltantes = []
    campos_raiz = campos(schema)

    def conferir_grupo(campos_req, prefixo=""):
        for nome, especificacao in campos_req.items():
            chave = f"{prefixo}.{nome}" if prefixo else nome
            tipo = especificacao[0]
            opcoes = especificacao[1] if len(especificacao) > 1 else {}
            alias_raiz = bool(prefixo and nome in campos_raiz and nome in entradas)
            presente = chave in entradas or alias_raiz
            valor = entradas[chave] if chave in entradas else entradas.get(nome)
            if tipo == "COMFY_DYNAMICCOMBO_V3":
                if not presente:
                    faltantes.append(chave)
                    continue
                opcao = opcao_dinamica(especificacao, valor)
                if not opcao:
                    faltantes.append(f"{chave} (opção inválida)")
                    continue
                conferir_grupo(opcao.get("inputs", {}).get("required", {}), chave)
            elif tipo == "COMFY_AUTOGROW_V3":
                minimo = int(opcoes.get("template", {}).get("min", 0))
                quantidade = sum(k.startswith(chave + ".") for k in entradas)
                if quantidade < minimo:
                    faltantes.append(f"{chave} (mínimo {minimo})")
            elif not presente:
                # Alguns nós mantêm uma entrada de compatibilidade na raiz
                # para um campo hoje aninhado no DynamicCombo. SaveVideo, por
                # exemplo, aceita `codec` na raiz para satisfazer
                # `format.codec`.
                faltantes.append(chave)

    conferir_grupo(schema.get("input", {}).get("required", {}))
    return faltantes


def tipo_de_saida(catalogo, grafo, fio):
    origem, indice = fio
    if origem not in grafo:
        return None, f"nó de origem ausente: {origem}"
    classe = grafo[origem]["class_type"]
    saidas = catalogo[classe].get("output", [])
    if indice < 0 or indice >= len(saidas):
        return None, f"saída {indice} não existe em {origem}/{classe}"
    return saidas[indice], None


def validar_literal(nome, valor, especificacao):
    tipo = especificacao[0]
    opcoes = especificacao[1] if len(especificacao) > 1 else {}
    if isinstance(tipo, list) and valor not in tipo:
        falhar(f"{nome}: valor {valor!r} não consta do catálogo")
    if tipo == "COMBO" and opcoes.get("options") and valor not in opcoes["options"]:
        falhar(f"{nome}: opção {valor!r} inválida")
    if tipo == "COMFY_DYNAMICCOMBO_V3" and not opcao_dinamica(especificacao, valor):
        falhar(f"{nome}: ramo dinâmico {valor!r} inválido")
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        if "min" in opcoes and valor < opcoes["min"]:
            falhar(f"{nome}: {valor} abaixo do mínimo {opcoes['min']}")
        if "max" in opcoes and valor > opcoes["max"]:
            falhar(f"{nome}: {valor} acima do máximo {opcoes['max']}")


def validar_grafo(catalogo, nome, grafo):
    antes = len(_falhas)
    for nid, no in grafo.items():
        classe = no.get("class_type")
        if classe not in catalogo:
            falhar(f"{nome}/{nid}: classe ausente no ComfyUI: {classe}")
            continue
        schema = catalogo[classe]
        entradas = no.get("inputs", {})
        for faltante in obrigatorios(schema, entradas):
            falhar(f"{nome}/{nid}/{classe}: entrada obrigatória ausente: {faltante}")
        for chave, valor in entradas.items():
            especificacao = resolver_especificacao(schema, entradas, chave)
            if especificacao is None:
                falhar(f"{nome}/{nid}/{classe}: entrada desconhecida: {chave}")
                continue
            if (isinstance(valor, list) and len(valor) == 2
                    and isinstance(valor[0], str) and isinstance(valor[1], int)):
                obtido, erro = tipo_de_saida(catalogo, grafo, valor)
                if erro:
                    falhar(f"{nome}/{nid}/{chave}: {erro}")
                    continue
                esperado = especificacao[0]
                curingas = {"*", "COMFY_MATCHTYPE_V3"}
                tipos_esperados = (esperado.split(",") if isinstance(esperado, str)
                                  else esperado if isinstance(esperado, list) else [])
                if (tipos_esperados
                        and obtido not in tipos_esperados
                        and not any(tipo in curingas for tipo in tipos_esperados)
                        and obtido not in curingas):
                    falhar(f"{nome}/{nid}/{chave}: liga {obtido} em {esperado}")
            else:
                validar_literal(f"{nome}/{nid}/{chave}", valor, especificacao)
    return len(_falhas) == antes


def grafos_representativos(catalogo):
    imagens = catalogo["LoadImage"]["input"]["required"]["image"][0]
    if not imagens:
        raise RuntimeError("ComfyUI não possui imagens disponíveis em input")
    imagem = imagens[0]
    imagem2 = imagens[1] if len(imagens) > 1 else imagem
    # Qualquer video gerado antes serve; o caminho vem do ambiente.
    video = os.environ.get("VIDEO_TESTE", "")
    casos = {}

    for modelo in P.SIMPLE:
        casos[f"imagem/{modelo}"] = W.gerar_simples(
            modelo, "uma foto", "", 1, 1024, 1024)
    casos["imagem/ideogram"] = W.gerar_ideogram(
        '{"high_level_description":"cartaz","compositional_deconstruction":{"background":"preto","elements":[]}}',
        1, 1024, 1024)

    refs = [imagem, imagem2]
    casos["edicao/klein"] = W.editar_klein("troque", refs, 2)
    casos["edicao/mage"] = W.editar_mage("mude", refs, 3)
    casos["edicao/qwen"] = W.editar_qwen("mude", refs, 4)
    casos["edicao/estilo"] = W.gerar_com_estilo("nova cena", refs, 5, 1024, 768)
    casos["edicao/folha"] = W.gerar_folha_personagem(
        imagem, P.EDICAO["folha"]["gatilho"], 7)
    casos["edicao/cabeca"] = W.trocar_cabeca(
        refs, P.EDICAO["cabeca"]["gatilho"], 7)
    instrucao = W.instrucao_de_personagem({}, "")
    casos["edicao/personagem"] = W.trocar_personagem(
        instrucao, [imagem, imagem2, imagem2], 6,
        P.PERSONAGEM["unet_alternativo"], 20, 5.0)
    for tipo in P.CONTROLE["tipos"]:
        casos[f"edicao/controle-{tipo}"] = W.gerar_com_controle(
            "uma casa", imagem, tipo, 7)
    for metodo in ("seedvr", "classico", "criativo"):
        casos[f"edicao/ampliar-{metodo}"] = W.ampliar(
            imagem, metodo, 2.0, seed=8,
            ajustes={"semelhanca": 0.2} if metodo == "criativo" else {})
    casos["edicao/topaz"] = W.ampliar_topaz(imagem, 2.0, largura=832, altura=1216)
    casos["edicao/rosto"] = W.ajustar_rosto(imagem, {"smile": 0.5})
    casos["edicao/magnific"] = W.reluz_magnific(
        imagem, "luz lateral", referencia=imagem2)
    casos["edicao/recorte"] = W.recortar_fundo(imagem)
    google = next(k for k, v in P.NUVEM.items() if v["familia"] == "gemini")
    casos["nuvem/gemini"] = W.gerar_nuvem(
        google, "edite", 9, referencias=refs)
    openai = next(v["modelo"] for v in P.NUVEM.values()
                  if v["familia"] == "openai")
    casos["nuvem/openai"] = W.gerar_openai(
        openai, "edite", 10, referencias=refs)

    casos["video/ltx-texto"] = W.gerar_video_ltx(
        "neblina", 11, largura=832, altura=448, duracao=2, com_audio=False)
    casos["video/ltx-msr"] = W.gerar_video_ltx_msr(
        "duas pessoas", 12, refs, largura=832, altura=448, duracao=2,
        com_audio=False)
    casos["video/ltx-flf"] = W.gerar_video_ltx_flf(
        "aproximacao", 13, imagem, imagem2, largura=832, altura=448,
        duracao=2, com_audio=False)
    casos["video/minimax-nuvem"] = W.gerar_video_minimax_nuvem(
        "movimento", 17, modo="primeiro_ultimo", imagem=imagem,
        imagem_final=imagem2)
    casos["video/minimax-ref-nuvem"] = W.gerar_video_minimax_ref_nuvem(
        "duas pessoas", 18, refs)
    casos["video/wan"] = W.gerar_video_wan3(
        "movimento", 19, modo="primeiro_ultimo", imagem=imagem,
        imagem_final=imagem2, com_audio=False)
    casos["video/limpar"] = W.limpar_video(video, 20, resolucao=720,
                                            com_audio=False)
    return casos


def main():
    try:
        catalogo = catalogo_vivo(config.COMFY_URL)
        segundo = (catalogo if config.COMFY_URL_FLUX3 == config.COMFY_URL else
                   catalogo_vivo(config.COMFY_URL_FLUX3))
    except RuntimeError as e:
        print(e)
        return 2
    try:
        casos = grafos_representativos(catalogo)
    except (KeyError, IndexError, RuntimeError) as e:
        print(f"Não foi possível montar os grafos de integração: {e}")
        return 2
    aprovados = sum(validar_grafo(segundo if nome == "imagem/flux3" else catalogo,
                                nome, grafo) for nome, grafo in casos.items())
    if _falhas:
        print(f"{len(_falhas)} FALHA(S) em {len(casos)} grafos:")
        for erro in _falhas:
            print("  -", erro)
        return 1
    print(f"{aprovados} grafos conferidos contra o ComfyUI vivo; nada executado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
