# -*- coding: utf-8 -*-
"""Regressoes puras dos fluxos de video e da medicao de creditos.

Nao usa GPU, ComfyUI, arquivos de modelo nem creditos de nuvem. Os testes
inspecionam os grafos que seriam enviados ao motor, justamente onde nomes de
entrada errados e ramos de audio ausentes costumam passar em silencio.

Rodar com:

    backend\\.venv\\Scripts\\python.exe backend\\testes\\test_video.py
"""
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent))

import app as A          # noqa: E402
import presets as P      # noqa: E402
import workflows as W    # noqa: E402

_falhas = []


def teste_seedvr2_reduz_seed_ao_limite_do_no():
    seed = 4416133791498845  # valor recusado pelo ComfyUI em uma tarefa real
    grafo = W.limpar_video("C:/video.mp4", seed)
    conferir("seed SeedVR2 em unsigned 32-bit",
             grafo["limpa"]["inputs"]["seed"], seed % (2**32))
    conferir_que("seed SeedVR2 abaixo do máximo",
                 0 <= grafo["limpa"]["inputs"]["seed"] <= 4294967295)


def conferir(nome, obtido, esperado):
    if obtido != esperado:
        _falhas.append(f"{nome}: esperado {esperado!r}, obtido {obtido!r}")


def conferir_que(nome, condicao, detalhe=""):
    if not condicao:
        _falhas.append(f"{nome}: falso{(' — ' + detalhe) if detalhe else ''}")


def pedido(**campos):
    return A.PedidoGeracao(prompt="teste", **campos)


# Um gerador pago esquecido aqui grava US$ 0,00 na galeria sem dar erro; foi
# exatamente o que aconteceu com o primeiro MultiRef.
def teste_todo_video_pago_dispara_medidor():
    for gerador in P.GERADORES_VIDEO_PAGOS:
        conferir(f"video pago {gerador}",
                 A._custa_credito(pedido(modelo="video", modelo_video=gerador)),
                 True)


def teste_video_local_nao_consulta_saldo():
    for gerador in ("ltx", "ltx23"):
        conferir(f"video local {gerador}",
                 A._custa_credito(pedido(modelo="video", modelo_video=gerador)),
                 False)


def teste_outros_caminhos_pagos_continuam_cobertos():
    modelo_nuvem = next(iter(P.NUVEM))
    conferir("imagem de nuvem", A._custa_credito(pedido(modelo=modelo_nuvem)), True)
    conferir("recorte", A._custa_credito(pedido(modelo="recorte")), True)
    conferir("imagem local", A._custa_credito(pedido(modelo="krea")), False)


def teste_preco_multiref_padrao_e_linear():
    minimo, maximo = P.estimar_custo_minimax_ref(
        "MiniMax H3", "768P", 5, 1)
    conferir("padrao 5 s medido", round(minimo, 4), 0.6435)
    conferir("padrao nao e faixa", maximo, minimo)

    minimo, maximo = P.estimar_custo_minimax_ref(
        "MiniMax H3", "768P", 10, 1)
    conferir("padrao 10 s medido", round(minimo, 4), 1.2870)
    conferir("padrao 10 s nao e faixa", maximo, minimo)

    minimo, _ = P.estimar_custo_minimax_ref(
        "MiniMax H3", "768P", 5, 9)
    conferir("quatro imagens extras", round(minimo, 4), 0.8723)

    minimo, maximo = P.estimar_custo_minimax_ref(
        "MiniMax H3", "2K", 5, 1)
    conferir("2K medido", round(minimo, 4), 0.9295)
    conferir("2K nao e faixa", maximo, minimo)


def teste_preco_multiref_max_e_faixa_por_tokens():
    minimo, maximo = P.estimar_custo_minimax_ref(
        "MiniMax H3 Max", "480P", 5, 5, "standard")
    conferir("max 5 refs minimo", round(minimo, 4), 0.3575)
    conferir("max 5 refs maximo", round(maximo, 4), 0.6064)
    conferir_que("custo real ficou dentro da faixa",
                 minimo <= 0.4363 <= maximo)

    minimo, maximo = P.estimar_custo_minimax_ref(
        "MiniMax H3 Max", "768P", 5, 5, "standard")
    conferir("max 768p minimo", round(minimo, 4), 0.5720)
    conferir("max 768p maximo", round(maximo, 4), 0.8209)
    conferir_que("custo real 768p ficou dentro da faixa",
                 minimo <= 0.6745 <= maximo)


def teste_pedido_transporta_identidade_vocal_ltx():
    p = pedido(modelo="video", modelo_video="ltx",
               referencias_audio=["voz.wav"], forca_audio_referencia=2.5)
    conferir("voz no pedido LTX", p.referencias_audio, ["voz.wav"])
    conferir("forca da voz", p.forca_audio_referencia, 2.5)
    conferir("uma identidade vocal", P.VIDEO_LTX["max_audios_identidade"], 1)


def teste_ltx_liga_identidade_vocal_no_grafo():
    caminho = r"C:\midia\voz.wav"
    g = W.gerar_video_ltx(
        "uma pessoa fala", 1, duracao=2, com_audio=True,
        audio_referencia=caminho, forca_audio_referencia=2.5)
    conferir("arquivo de voz", g["carrega_audio_identidade"]["inputs"]["audio_file"],
             caminho)
    conferir("recorte recomendado", g["carrega_audio_identidade"]["inputs"]["duration"],
             5.0)
    conferir("forca encaminhada",
             g["audio_identidade"]["inputs"]["identity_guidance_scale"], 2.5)
    conferir("guia usa modelo vocal", g["guia"]["inputs"]["model"],
             ["audio_identidade", 0])
    conferir("positivo leva a voz", g["guia"]["inputs"]["positive"],
             ["audio_identidade", 1])
    conferir("negativo leva a voz", g["guia"]["inputs"]["negative"],
             ["audio_identidade", 2])


def teste_identidade_vocal_combina_com_guias_visuais_ltx():
    caminho = r"C:\midia\voz.wav"
    msr = W.gerar_video_ltx_msr(
        "teste", 1, ["pessoa.png"], com_audio=True,
        audio_referencia=caminho)
    conferir("MSR recebe positivo vocal", msr["msr1"]["inputs"]["positive"],
             ["audio_identidade", 1])
    conferir("MSR amostra com modelo vocal", msr["guia1"]["inputs"]["model"],
             ["audio_identidade", 0])

    flf = W.gerar_video_ltx_flf(
        "teste", 1, "inicio.png", "fim.png", com_audio=True,
        audio_referencia=caminho)
    conferir("FLF recebe positivo vocal", flf["guia_ini"]["inputs"]["positive"],
             ["audio_identidade", 1])
    conferir("FLF amostra com modelo vocal", flf["guia"]["inputs"]["model"],
             ["audio_identidade", 0])


# O fundo precisa chegar aos dois estagios do LTX MSR.
def teste_ltx_msr_liga_fundo_nos_dois_estagios():
    g = W.gerar_video_ltx_msr(
        "teste", 1, ["pessoa.png"], fundo="rua.png", com_audio=False)
    conferir("fundo no primeiro estagio", g["msr1"]["inputs"]["background"],
             ["fundo", 0])
    conferir("fundo no segundo estagio", g["msr2"]["inputs"]["background"],
             ["fundo", 0])
    conferir_que("LoRA MSR presente", "msr_lora" in g)
    conferir_que("guias sao cortados nos dois estagios",
                 "corta1" in g and "corta2" in g)


def teste_contagem_temporal_do_ltx():
    for entrada, saida in ((0, 0), (1, 1), (121, 121), (124, 121), (192, 185)):
        conferir(f"quadros {entrada}", P.quadros_que_sobrevivem(entrada), saida)


def teste_ltx_oferece_faixa_medida():
    conferir("duracao minima LTX", P.VIDEO_LTX["duracao_min"], 2)
    conferir("duracao maxima LTX", P.VIDEO_LTX["duracao_max"], 15)


def teste_ltx_1080p_usa_caminho_de_memoria():
    largura, altura = P.tamanho_de_video("1080p", "16:9",
                                         P.VIDEO_LTX["alinhamento"])
    conferir("1080p LTX alinhado", (largura, altura), (1920, 1088))
    conferir_que("1080p cabe no teto proprio",
                 largura * altura <= P.VIDEO_LTX["max_pixels"])

    grande = W.gerar_video_ltx("teste", 1, largura=largura, altura=altura,
                                duracao=2, com_audio=False)
    conferir_que("contexto completo no 1080p", "mem_contexto" not in grande)
    conferir_que("feed-forward dividido no 1080p", "mem_ff" in grande)
    conferir("guia usa modelo economico",
             grande["guia"]["inputs"]["model"], ["mem_ff", 0])

    flf = W.gerar_video_ltx_flf(
        "teste", 1, "inicio.png", "fim.png", largura=largura, altura=altura,
        duracao=2, com_audio=False)
    conferir_que("FLF 1080p preserva contexto completo", "mem_contexto" not in flf)
    conferir("FLF divide feed-forward sem janela intermediaria",
             flf["mem_ff"]["inputs"]["model"], ["unet", 0])
    conferir_que("FLF 1080p divide feed-forward", "mem_ff" in flf)
    conferir("FLF amostra com modelo economico",
             flf["guia"]["inputs"]["model"], ["mem_ff", 0])

    msr = W.gerar_video_ltx_msr(
        "teste", 1, ["pessoa-a.png", "pessoa-b.png"], largura=largura,
        altura=altura, duracao=2, com_audio=False)
    conferir_que("MSR 1080p preserva contexto", "mem_contexto" not in msr)
    conferir_que("MSR 1080p divide feed-forward", "mem_ff" in msr)
    conferir("MSR amostra com modelo economico",
             msr["guia1"]["inputs"]["model"], ["mem_ff", 0])

    longo = W.gerar_video_ltx("teste", 1, largura=largura, altura=altura,
                               duracao=15, com_audio=False)
    conferir("15 s em 1080p conserva 361 quadros",
             longo["vazio"]["inputs"]["length"], 361)
    conferir_que("15 s em 1080p conserva contexto completo",
                 "mem_contexto" not in longo and "mem_ff" in longo)

    comum = W.gerar_video_ltx("teste", 1, largura=1280, altura=704,
                               duracao=2, com_audio=False)
    conferir_que("720p preserva grafo antigo",
                 "mem_contexto" not in comum and "mem_ff" not in comum)


def teste_ltx_todos_os_modos_preservam_contexto_longo():
    for largura, altura in ((1920, 1088), (1088, 1920), (1280, 704)):
        for audio in (False, True):
            args = dict(largura=largura, altura=altura, duracao=15, com_audio=audio)
            grafos = [
                W.gerar_video_ltx("teste", 1, **args),
                W.gerar_video_ltx("teste", 1, imagem="inicio.png", **args),
                W.gerar_video_ltx_msr("teste", 1, ["a.png", "b.png"], **args),
            ]
            for g in grafos:
                conferir_que("nenhum modo recorta o contexto temporal",
                             all(n["class_type"] != "LTXVContextWindows"
                                 for n in g.values()))
                conferir("duracao integral", g["vazio"]["inputs"]["length"], 361)
                if largura * altura > P.VIDEO_LTX["otimiza_memoria_acima"]:
                    origem = ["msr_lora", 0] if "msr_lora" in g else ["unet", 0]
                    conferir("economia sem remendo temporal",
                             g["mem_ff"]["inputs"]["model"], origem)
                    for chave in ("guia", "guia1", "guia2"):
                        if chave in g:
                            conferir("estagios usam contexto completo",
                                     g[chave]["inputs"]["model"], ["mem_ff", 0])


def teste_ltx_flf_longo_preserva_as_duas_referencias():
    for largura, altura in ((1920, 1088), (1088, 1920), (1280, 704)):
        for audio in (False, True):
            g = W.gerar_video_ltx_flf(
                "transicao", 1, "inicio.png", "fim.png", largura=largura,
                altura=altura, duracao=15, com_audio=audio)
            conferir_que("FLF longo sem recorte temporal do contexto",
                         all(n["class_type"] != "LTXVContextWindows"
                             for n in g.values()))
            conferir("FLF 15 s conserva 361 quadros",
                     g["vazio"]["inputs"]["length"], 361)
            conferir("primeira referencia no inicio",
                     g["guia_ini"]["inputs"]["frame_idx"], 0)
            conferir("ultima referencia no fim",
                     g["guia_fim"]["inputs"]["frame_idx"], -1)
            conferir("guias encadeados no latente",
                     g["guia_fim"]["inputs"]["latent"], ["guia_ini", 2])
            conferir("amostragem usa ambos os guias",
                     g["guia"]["inputs"]["positive"], ["guia_fim", 0])
            if audio:
                conferir("audio recebe video com ambos os guias",
                         g["junta"]["inputs"]["video_latent"], ["guia_fim", 2])
            else:
                conferir("amostrador recebe video com ambos os guias",
                         g["passo"]["inputs"]["latent_image"], ["guia_fim", 2])


def teste_alinhamento_espacial_do_ltx():
    conferir("dobro alinhado para cima", P.alvo_de_ampliacao(1280, 728),
             (2560, 1472))
    conferir("origem no teto nao amplia", P.alvo_de_ampliacao(2560, 1440),
             (2560, 1440))


def teste_chaves_720p_com_recorte_e_decode_estavel():
    for proporcao, alvo in (((16, 9), (1280, 720)), ((9, 16), (720, 1280)),
                            ((1, 1), (720, 720)), ((4, 3), (960, 720))):
        saida = P.tamanho_chaves(*proporcao)
        conferir("saida das chaves", saida, alvo)
        for audio in (True, False):
            g = W.chaves_ltx("carro", [("a.png", 0), ("b.png", 304)],
                             361, *saida, com_audio=audio)
            base = g["vazio"]["inputs"]
            conferir("duracao das chaves", base["length"], 361)
            conferir_que("base alinhada", base["width"] % 32 == base["height"] % 32 == 0)
            if proporcao == (16, 9):
                conferir("base 720p", (base["width"], base["height"]), (640, 384))
            corte = g["recorte_saida"]["inputs"]
            conferir("recorte final", (corte["width"], corte["height"]), alvo)
            conferir("video usa recorte", g["video"]["inputs"]["images"], ["recorte_saida", 0])
            conferir("audio opcional", "audio" in g["video"]["inputs"], audio)
            conferir("decode temporal", (g["dec"]["inputs"]["temporal_size"],
                                          g["dec"]["inputs"]["temporal_overlap"]), (192, 48))
            for etapa in (1, 2):
                conferir("referencia preservada", g[f"guia1_{etapa}"]["inputs"]["frame_idx"], 304)


def main():
    for nome, fn in sorted(globals().items()):
        if nome.startswith("teste_"):
            fn()
    if _falhas:
        print(f"{len(_falhas)} FALHA(S):")
        for falha in _falhas:
            print("  -", falha)
        return 1
    print("todos os contratos puros de video passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def test_seed_dos_videos_de_api_cabe_no_limite_dos_nos():
    # Kling/Seedance aceitam ate 2^31-1; a seed do app vai ate 2^52.
    import workflows as W
    for prov in ("kling", "veo", "seedance"):
        g = W.gerar_video_api(prov, "a fox", 2**52 - 1, "texto", "16:9", "720p", 5)
        for no in g.values():
            if "seed" in no["inputs"]:
                assert 0 <= no["inputs"]["seed"] <= 2147483647, prov
