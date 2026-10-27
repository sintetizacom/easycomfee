# -*- coding: utf-8 -*-
"""Contratos puros das ferramentas de edicao.

Nao usa GPU, ComfyUI nem creditos. Confere o catalogo e os grafos que seriam
enviados ao motor, incluindo nomes de entradas dinamicas e encadeamentos cujo
erro costuma aparecer apenas depois de carregar modelos grandes.
"""
import asyncio
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent))

import app as A          # noqa: E402
import presets as P      # noqa: E402
import workflows as W    # noqa: E402
import biblioteca        # noqa: E402

# Numa copia recem-clonada a galeria ainda nao existe (o app a cria ao subir).
biblioteca.criar_tabelas()

_falhas = []


def conferir(nome, obtido, esperado):
    if obtido != esperado:
        _falhas.append(f"{nome}: esperado {esperado!r}, obtido {obtido!r}")


def conferir_que(nome, condicao, detalhe=""):
    if not condicao:
        _falhas.append(f"{nome}: falso{(' — ' + detalhe) if detalhe else ''}")


def validar_grafo(nome, grafo):
    """Todo fio [no, saida] aponta para um no existente e ha uma saida salva."""
    conferir_que(f"{nome}: salva resultado", "salva" in grafo)

    def visitar(valor, caminho):
        if (isinstance(valor, list) and len(valor) == 2
                and isinstance(valor[0], str) and isinstance(valor[1], int)):
            conferir_que(f"{nome}: fio {caminho}", valor[0] in grafo,
                         f"no ausente {valor[0]!r}")
        elif isinstance(valor, dict):
            for chave, item in valor.items():
                visitar(item, f"{caminho}.{chave}")
        elif isinstance(valor, list):
            for i, item in enumerate(valor):
                visitar(item, f"{caminho}[{i}]")

    visitar(grafo, "grafo")


def teste_catalogo_expoe_todas_as_ferramentas():
    original = A.comfy.unets_disponiveis

    async def com_fasth3():
        # O FastH3 saiu do app; o catalogo nao pode mais oferece-lo nem
        # com o arquivo no disco.
        return {"Minimax/fastvideo_fasth3_8step_v2_pruned_int8_convrot.safetensors"}

    try:
        A.comfy.unets_disponiveis = com_fasth3
        catalogo = asyncio.run(A.modelos())
    finally:
        A.comfy.unets_disponiveis = original

    ids = [item["id"] for item in catalogo["edicao"]]
    esperados = set(P.EDICAO) | {
        "personagem", "controle", "ampliar", "angulo", "reluz", "rosto",
        "recorte",
    }
    conferir("12 ferramentas no catalogo", set(ids), esperados)
    conferir("sem ferramenta duplicada", len(ids), len(set(ids)))
    grupos = {g["id"] for g in catalogo["grupos_edicao"]}
    conferir_que("todas as ferramentas tem grupo valido",
                 all(i["grupo"] in grupos for i in catalogo["edicao"]))
    ids_video = {g["id"] for g in catalogo["video"]["geradores"]}
    conferir("MiniMax local fora do catalogo",
             ids_video & {"minimax", "fasth3", "planos"}, set())


def teste_editores_encaminham_referencias_e_modelos():
    refs = [f"r{i}.png" for i in range(4)]

    klein = W.editar_klein("troque", refs, 11, negativo="artefato")
    validar_grafo("Klein", klein)
    conferir("Klein encadeia quarta referencia",
             klein["guia"]["inputs"]["positive"], ["refp3", 0])
    conferir("Klein leva negativo", klein["neg"]["inputs"]["text"], "artefato")

    mage = W.editar_mage("mude", refs, 12)
    validar_grafo("Mage", mage)
    entradas_mage = mage["cond"]["inputs"]
    conferir("Mage limita tres imagens",
             sorted(k for k in entradas_mage if k.startswith("images.")),
             ["images.image_1", "images.image_2", "images.image_3"])

    qwen = W.editar_qwen("mude", refs, 13, lora="efeito.safetensors")
    validar_grafo("Qwen", qwen)
    conferir("Qwen limita terceira imagem", "image4" in qwen["pos"]["inputs"], False)
    conferir("Qwen liga LoRA antes do shift",
             qwen["shift"]["inputs"]["model"], ["lora", 0])

    estilo = W.gerar_com_estilo("nova cena", refs, 14, 1024, 768)
    validar_grafo("Estilo", estilo)
    conferir("Estilo limita tres referencias", "image4" in estilo["cond"]["inputs"],
             False)
    conferir("Estilo usa LoRA", estilo["ms"]["inputs"]["model"], ["lora", 0])


def teste_personagem_preserva_protocolo_de_tres_papeis():
    instrucao = W.instrucao_de_personagem({"roupa": True}, "sem chapeu")
    conferir_que("instrucao cita cena", "Figure 1" in instrucao)
    conferir_que("instrucao cita pessoa", "Figure 2" in instrucao)
    conferir_que("instrucao cita rosto", "Figure 3" in instrucao)
    conferir_que("instrucao inclui complemento", instrucao.endswith("sem chapeu"))

    g = W.trocar_personagem(instrucao, ["cena.png", "pessoa.png", "rosto.png"],
                            15, P.PERSONAGEM["unet_alternativo"], 20, 5.0)
    validar_grafo("Personagem", g)
    conferir("personagem usa tres referencias", g["guia"]["inputs"]["positive"],
             ["refp2", 0])
    conferir("personagem usa modelo escolhido", g["unet"]["inputs"]["unet_name"],
             W.win(P.PERSONAGEM["unet_alternativo"]))


def teste_quatro_mapas_de_controle_e_forca():
    for tipo, cfg in P.CONTROLE["tipos"].items():
        previa = W.previa_de_controle("base.png", tipo)
        validar_grafo(f"previa {tipo}", previa)
        conferir(f"preprocessador {tipo}", previa["pre"]["class_type"], cfg["no"])

        g = W.gerar_com_controle("uma casa", "base.png", tipo, 16, forca=0.65)
        validar_grafo(f"controle {tipo}", g)
        conferir(f"forca {tipo}", g["controle"]["inputs"]["strength"], 0.65)
        conferir(f"mapa normalizado {tipo}", g["controle"]["inputs"]["image"],
                 ["mapa", 0])


def teste_quatro_caminhos_de_ampliacao():
    seedvr = W.ampliar("foto.png", "seedvr", 2.0, seed=17)
    validar_grafo("SeedVR2", seedvr)
    conferir("SeedVR2 escala pedida", seedvr["escala"]["inputs"]["resize_type.multiplier"],
             2.0)

    classico = W.ampliar("foto.png", "classico", 2.0)
    validar_grafo("classico", classico)
    conferir("classico reduz o 4x para 2x",
             classico["ajusta"]["inputs"]["resize_type.multiplier"], 0.5)

    criativo = W.ampliar(
        "foto.png", "criativo", 3.0, seed=18,
        ajustes={"semelhanca": 0.4, "detalhe": 0.5,
                 "microcontraste": 0.2, "granulacao": 0.1})
    validar_grafo("criativo", criativo)
    conferir("criativo mede alvo pela original", criativo["alvo"]["inputs"]["scale_by"],
             3.0)
    conferir("criativo mistura no tamanho final",
             criativo["mistura"]["inputs"]["image1"], ["ao_tamanho", 0])
    conferir("acabamento termina no grao", criativo["salva"]["inputs"]["images"],
             ["fim_grao", 0])

    topaz = W.ampliar_topaz("foto.png", 2.0, largura=1200, altura=800)
    validar_grafo("Topaz", topaz)
    conferir("Topaz largura final", topaz["nuvem"]["inputs"]["output_width"], 2400)
    conferir("Topaz altura final", topaz["nuvem"]["inputs"]["output_height"], 1600)
    conferir_que("Topaz usa campos do combo dinamico",
                 "model.enhancement_strength" in topaz["nuvem"]["inputs"])


def teste_angulo_e_luz_mantem_instrucoes_especificas():
    camera = W.instrucao_de_angulo("perfil", "mantenha o sorriso", "camera")
    conferir_que("camera usa vocabulario da LoRA", camera.startswith("Turn the camera"))
    conferir_que("camera nao recebe clausula conflitante",
                 P.ANGULO["preservar"] not in camera)
    personagem = W.instrucao_de_angulo("perfil", metodo="personagem")
    conferir_que("giro preserva cena", P.ANGULO["preservar"] in personagem)

    luz = W.instrucao_de_luz("Light from the left.", com_mapa=True,
                             gatilho="GATILHO ")
    conferir_que("luz comeca pelo gatilho", luz.startswith("GATILHO "))
    conferir_que("mapa nao deve ser desenhado", "Do NOT draw the sphere" in luz)
    conferir_que("luz preserva sujeito", P.RELUZ["preservar"] in luz)


def teste_magnific_rosto_e_recorte():
    reluz = W.reluz_magnific("base.png", "luz lateral", forca=150,
                             referencia="luz.png", mudar_fundo=False)
    validar_grafo("Magnific", reluz)
    conferir("Magnific limita forca", reluz["nuvem"]["inputs"]["light_transfer_strength"],
             100)
    conferir("Magnific liga referencia", reluz["nuvem"]["inputs"]["reference_image"],
             ["luz", 0])
    conferir("Magnific preserva fundo", reluz["nuvem"]["inputs"]["change_background"],
             False)

    rosto = W.ajustar_rosto("rosto.png", {"rotate_yaw": 999, "smile": "invalido"})
    validar_grafo("rosto", rosto)
    conferir("rosto limita yaw", rosto["exp"]["inputs"]["rotate_yaw"], 20)
    conferir("rosto recupera valor invalido", rosto["exp"]["inputs"]["smile"], 0)

    recorte = W.recortar_fundo("pessoa.png")
    validar_grafo("recorte", recorte)
    conferir("recorte usa Recraft", recorte["nuvem"]["class_type"],
             "RecraftRemoveBackgroundNode")
    conferir("recorte salva imagem com alfa", recorte["salva"]["inputs"]["images"],
             ["nuvem", 0])


def teste_editores_de_nuvem_respeitam_autogrow():
    modelo_google = next(k for k, v in P.NUVEM.items() if v["familia"] == "gemini")
    google = W.gerar_nuvem(modelo_google, "edite", 19,
                           referencias=["a.png", "b.png", "c.png"])
    validar_grafo("Google", google)
    conferir("Google encadeia lote", google["nuvem"]["inputs"]["images"],
             ["lote2", 0])

    openai = W.gerar_openai("gpt-image-2.5", "edite", 20,
                            referencias=["a.png", "b.png"])
    validar_grafo("OpenAI", openai)
    conferir("OpenAI autogrow base um",
             openai["nuvem"]["inputs"]["model.images.image_2"], ["img2", 0])
    conferir_que("OpenAI usa prefixo do combo",
                 "model.size" in openai["nuvem"]["inputs"])

    seed_grande = 768871470262635  # valor recusado numa geracao real
    openai_seed = W.gerar_openai("gpt-image-2.5-sunburst", "edite", seed_grande)
    seed_enviada = openai_seed["nuvem"]["inputs"]["seed"]
    conferir("OpenAI reduz seed para int32 assinado",
             seed_enviada, seed_grande % (2**31))
    conferir_que("OpenAI respeita limite maximo da seed",
                 0 <= seed_enviada <= 2147483647)

    conferir("GPT 1K quadrado", P.tamanho_gpt("1K", "1:1"), "1024x1024")
    conferir("GPT 1K retrato", P.tamanho_gpt("1K", "9:16"), "1024x1536")
    conferir("GPT 2K paisagem", P.tamanho_gpt("2K", "16:9"), "2048x1152")
    conferir("GPT 4K retrato", P.tamanho_gpt("4K", "9:16"), "2160x3840")
    conferir("GPT 4K quadrado cai no 2K valido",
             P.tamanho_gpt("4K", "1:1"), "2048x2048")


def teste_personagem_abre_no_rapido():
    """O padrao e Rapido quando o destilado existe, e cai em Fiel quando nao.

    Fixado em 22/09/2026. O padrao antigo era Fiel e contradizia a nota que o
    proprio painel mostrava; este guarda existe para a contradicao nao voltar
    sem que alguem note. Tres coisas tem de andar juntas: a ORDEM em
    presets.PERSONAGEM (o painel abre na primeira que sobrevive ao filtro), o
    default do pedido em app.py, e a estimativa de segundos do catalogo.
    """
    pe = P.PERSONAGEM["prioridades"]
    conferir("Rapido e a primeira prioridade", next(iter(pe)), "rapido")
    conferir("pedido nasce em Rapido", A.PedidoGeracao.model_fields[
        "prioridade"].default, "rapido")

    original = A.comfy.unets_disponiveis

    async def com_destilado():
        return {P.PERSONAGEM["unet"]}

    async def sem_destilado():
        return set()

    try:
        # Com o destilado no disco: a chave aparece, abre no Rapido, e o
        # motor escolhe mesmo o destilado de 4 passos sem ninguem pedir.
        A.comfy.unets_disponiveis = com_destilado
        cat = asyncio.run(A.modelos())
        p = next(i for i in cat["edicao"] if i["id"] == "personagem")
        conferir_que("chave aparece com o destilado", p["tem_destilado"])
        conferir("painel abre no Rapido", p["prioridades"][0]["id"], "rapido")
        conferir("estimativa segue o padrao", p["segundos_estimados"],
                 pe["rapido"]["segundos"])
        unet, steps, cfg = asyncio.run(A.escolher_modelo_personagem())
        conferir("padrao usa o destilado", unet, P.PERSONAGEM["unet"])
        conferir("padrao usa 4 passos", steps, pe["rapido"]["steps"])

        # Sem ele: a chave some, e o padrao "rapido" nao pode quebrar — tem de
        # cair no Klein base sozinho, com os passos do Fiel.
        A.comfy.unets_disponiveis = sem_destilado
        cat = asyncio.run(A.modelos())
        p = next(i for i in cat["edicao"] if i["id"] == "personagem")
        conferir_que("chave some sem o destilado", not p["tem_destilado"])
        conferir("so sobra Fiel", [o["id"] for o in p["prioridades"]], ["fiel"])
        conferir("estimativa cai para o Fiel", p["segundos_estimados"],
                 pe["fiel"]["segundos"])
        unet, steps, cfg = asyncio.run(A.escolher_modelo_personagem())
        conferir("sem destilado cai no base", unet,
                 P.PERSONAGEM["unet_alternativo"])
        conferir("sem destilado usa 20 passos", steps, pe["fiel"]["steps"])
    finally:
        A.comfy.unets_disponiveis = original


def teste_folha_de_personagem():
    """A folha nasce vazia e DEITADA; a foto entra pelo remendo, nao no latente.

    As duas telas sao trocaveis sem dar erro — e uma folha com o enquadramento
    errado sai sem ninguem reclamar. Por isso o guarda prende as duas.
    """
    p = P.EDICAO["folha"]
    g = W.gerar_folha_personagem("foto.png", p["gatilho"], 9)
    validar_grafo("folha", g)

    conferir("folha sai deitada", 
             (g["latente"]["inputs"]["width"], g["latente"]["inputs"]["height"]),
             tuple(p["saida"]))
    conferir("foto entra em pe",
             (g["ajusta"]["inputs"]["width"], g["ajusta"]["inputs"]["height"]),
             tuple(p["entrada"]))
    conferir_que("saida e deitada", p["saida"][0] > p["saida"][1])
    conferir_que("entrada e em pe", p["entrada"][0] < p["entrada"][1])

    # O caminho da identidade: foto -> ajusta -> VAEEncode -> remendo. Se o
    # latente da foto virar o latent_image do sampler, a folha deixa de ser
    # uma tela nova e vira uma edicao por cima da foto.
    conferir("sampler parte da tela vazia",
             g["amostra"]["inputs"]["latent_image"], ["latente", 0])
    conferir("remendo recebe o latente da foto",
             g["remenda"]["inputs"]["source_latent"], ["lat_origem", 0])
    conferir("latente da foto vem da foto ajustada",
             g["lat_origem"]["inputs"]["pixels"], ["ajusta", 0])
    conferir("sampler usa o modelo remendado",
             g["amostra"]["inputs"]["model"], ["remenda", 0])
    conferir("remendo parte do LoRA, nao da UNET crua",
             g["remenda"]["inputs"]["model"], ["lora", 0])
    conferir("LoRA do QuadView", g["lora"]["inputs"]["lora_name"],
             P.win(p["lora"]))

    # O gatilho e a frase de treino do LoRA: o texto do usuario entra DEPOIS.
    conferir("positivo comeca pelo gatilho",
             g["pos"]["inputs"]["prompt"].startswith(p["gatilho"]), True)
    conferir("negativo fica vazio", g["neg"]["inputs"]["prompt"], "")
    conferir("grounding do positivo", g["pos"]["inputs"]["grounding_px"], 0)
    conferir("grounding do negativo", g["neg"]["inputs"]["grounding_px"], 768)

    # Uma referencia so: o remendo tem um unico latente de origem.
    conferir("aceita uma imagem", (p["min_referencias"], p["max_referencias"]),
             (1, 1))
    conferir_que("nao usa source_latent_b",
                 "source_latent_b" not in g["remenda"]["inputs"])


def teste_bfs_troca_cabeca():
    p = P.EDICAO["cabeca"]
    g = W.trocar_cabeca(["cena.png", "rosto.png"], p["gatilho"], 9)
    validar_grafo("cabeca", g)
    conferir("BFS usa duas imagens", (p["min_referencias"], p["max_referencias"]),
             (2, 2))
    conferir("BFS LoRA", g["lora"]["inputs"]["lora_name"], P.win(p["lora"]))
    conferir("cena no primeiro slot", g["img0"]["inputs"]["image"], "cena.png")
    conferir("cabeca no segundo slot", g["img1"]["inputs"]["image"], "rosto.png")
    conferir("segundo latente no remendo",
             g["remenda"]["inputs"]["source_latent_b"], ["lat1", 0])
    conferir("segunda imagem no positivo", g["pos"]["inputs"]["image_b"],
             ["ajusta1", 0])
    conferir("tamanho da cena", g["tam"]["inputs"]["image"], ["ajusta0", 0])
    conferir("gatilho BFS", g["pos"]["inputs"]["prompt"], p["gatilho"])
    conferir("grounding BFS", g["pos"]["inputs"]["grounding_px"], 512)
    conferir("CFG turbo", g["amostra"]["inputs"]["cfg"], 1.0)


def teste_magnific_upscale():
    for escala in (2, 4, 8, 16):
        W.validar_magnific(160, 160, escala)
        g = W.ampliar_magnific("base.png", escala, "pele natural", -2, 3, 8, 1)
        validar_grafo("Magnific Upscale", g)
        conferir("escala Magnific", g["nuvem"]["inputs"]["scale_factor"], f"{escala}x")
        conferir("prompt Magnific", g["nuvem"]["inputs"]["prompt"], "pele natural")
        conferir("sem redução silenciosa", g["nuvem"]["inputs"]["auto_downscale"], False)
    for dimensoes in ((1024, 1024, 8), (100, 100, 2), (160, 1000, 2), (512, 512, 3)):
        try:
            W.validar_magnific(*dimensoes)
        except ValueError:
            pass
        else:
            _falhas.append(f"Magnific deveria recusar {dimensoes}")
    conferir("motor Magnific Upscale", P.motor_do("ampliar", "magnific"), "nuvem")


def main():
    for nome, fn in sorted(globals().items()):
        if nome.startswith("teste_"):
            fn()
    if _falhas:
        print(f"{len(_falhas)} FALHA(S):")
        for falha in _falhas:
            print("  -", falha)
        return 1
    print("todos os contratos puros de edicao passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
