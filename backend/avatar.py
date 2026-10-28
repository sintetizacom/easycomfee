"""Avatar falante: uma foto e uma fala viram um video da pessoa falando.

Usa o LongCat-Video-Avatar 1.5 pelos nos do ComfyUI-WanVideoWrapper. A
configuracao saiu das rodadas de 02 e 03/10/2026
(analises/avatar-longcat-2026-10-02): cada valor foi medido contra o
anterior, um de cada vez.

Por que a 1.5 e nao a 1.0: na 1.0 destilada os dentes viravam uma faixa
granulada que mudava a cada quadro — o pisca visto no teste. Sem a
destilacao os dentes se formavam, mas levava 58 min para 5 s. A 1.5, com a
destilacao DMD dela, forma dentes estaveis em 8 passos.
"""
import asyncio
import io
import math
import pathlib
import uuid

import cv2
import httpx
import numpy as np
import soundfile as sf

import comfy
import config

FPS = 25                 # a 1.5 e treinada a 25 fps (a 1.0 era 16)
JANELA = 93              # quadros por segmento
SOBREPOSICAO = 13        # quadros que cada segmento herda do anterior
LARGURA, ALTURA = 832, 480
# Aos 30 s os labios ganham cor de batom e o rosto vira de frente, segmento a
# segmento. Aos 15 s nada disso aparece.
LIMITE_SEGUNDOS = 15.0

# GGUF ja convertido para o ComfyUI (vantagewithai). O LoRA DMD oficial usa
# nomes do codigo LongCat que o wrapper nao le; foi convertido por
# scripts/converter_lora_longcat15.py e conferido contra os pesos oficiais.
MODELO = "LongCat\\LongCat-Avatar-15_comfy-Q8_0.gguf"
LORA = "LongCat-Avatar15_dmd_lora_bf16.safetensors"
FORCA_LORA = 1.0         # o multiplicador do codigo oficial
WHISPER = "whisper-large-v3.safetensors"

# 8 passos e os dois cfg em 1: os valores oficiais com a destilacao.
PASSOS = 8
# audio_cfg acima de 1 faz uma passada extra por passo e exagera a boca.
AUDIO_CFG = 1
# 30 e nao 25: com 25 os segmentos de emenda estouravam a placa e o Windows
# passava a emprestar RAM sem erro — um passo de 29 s virava 500 s.
BLOCOS_NA_RAM = 30
# SageAttention 2.2 esta instalado SO no .venv da v0.36. Se os lancadores
# passarem a subir a v0.37, instalar la tambem ou trocar para "sdpa".
ATENCAO = "sageattn"
# 0 = todo quadro consulta a foto. O padrao (3) deixa uma faixa de cada
# segmento sem ela, e aos 30 s o rosto ja era de outra pessoa.
MASCARA_REFERENCIA = 0

# Sem isto a camera passeia: afasta, aproxima, a cabeca encosta no topo.
# Sem "tripod": no Cinema o LTX chegou a desenhar um tripe na cena (27/10/2026).
CAMERA_FIXA = ("Static shot with fixed framing: the view does not move, zoom or pan, "
               "and the framing does not change.")
CENA_PADRAO = "A person speaks naturally to the camera"
# Sem isto o LTX 2.3 quase nao mexia a boca (28/10/2026: retrato de labios fechados
# saiu mudo; com a frase, o movimento na regiao da boca foi de 2,1 para 5,5). Sem
# "showing teeth": com ela a pessoa sorria o tempo todo.
FALA_VISIVEL = ("The person is speaking out loud to the camera, with a neutral expression: "
                "the lips, mouth and jaw move naturally in sync with every word.")
NEGATIVO = (
    "Close-up, bright tones, overexposed, static, blurred details, subtitles, style, "
    "works, paintings, images, static, overall gray, worst quality, low quality, JPEG "
    "compression residue, ugly, incomplete, extra fingers, poorly drawn hands, poorly "
    "drawn faces, deformed, disfigured, misshapen limbs, fused fingers, still picture, "
    "messy background, three legs, many people in the background, walking backwards, "
    "camera movement, zoom, pan, shaky camera, reframing")

NOS = ("WanVideoLongCatAvatarExtendEmbeds", "WhisperModelLoader",
       "LongCatAvatarWhisperEmbeds", "WanVideoSamplerv2", "VHS_VideoCombine",
       "ImageBatchExtendWithOverlap", "GetImageRangeFromBatch")

DETECTOR = pathlib.Path(__file__).parent / "modelos" / "face_detection_yunet_2023mar.onnx"
# 0,80: o rosto de tres-quartos da foto de teste vem com 0,93; a foto do
# farol, sem ninguem, deu um "rosto" falso de 0,68.
CONFIANCA_ROSTO = 0.80


# ---- Segundo motor: LTX 2.3 imagem + audio -> video ----------------------
# Template oficial video_ltx2_3_ia2v com a foto presa tambem ao ULTIMO quadro
# (sem isso a camera se afastava a partir de ~6 s). Medido em 14/10/2026:
# 9 s em ~2,5 min, 14,5 s em 3,5 min, 28 s em 7,2 min, em 1280x704, rosto
# fiel e labios naturais ate o fim. Grafo testado em grafos/ltx23_ia2v.json.
# Exige paginacao fixa no Windows: a carga compromete ~80 GB de memoria, e com
# a paginacao automatica o motor caia em ~60% das vezes.
GRAFO_LTX23 = pathlib.Path(__file__).parent / "grafos" / "ltx23_ia2v.json"
LTX23 = {"limite": 30.0, "largura": 1280, "altura": 704, "fps": 24}
# 9:16, so no LTX 2.3 (o LongCat foi medido so na horizontal). Pede-se 720
# como na horizontal, e o modelo arredonda para 704: o video sai 704x1280.
LTX23_VERTICAL = (720, 1280)
CKPT_LTX23 = "LTX\\LTX_2.3\\ltx-2.3-22b-dev-fp8.safetensors"
NOS_LTX23 = ("LTXAVTextEncoderLoader", "LTXVAddGuide", "LTXVImgToVideoInplace",
             "LTXVAudioVAEEncode", "LTXVCropGuides", "LTXVLatentUpsampler")
# A guia no ultimo quadro acrescenta 8 quadros (~0,33 s) ao fim do video.
# NAO compensar pedindo menos: o template corta o AUDIO na mesma duracao, e o
# teste de 15/10 perdeu o fim da fala (14,56 -> 14,21 s). Melhor sobrar
# imagem muda no fim do que faltar fala.
SOBRA_GUIA_LTX23 = 0.0

MODELOS = {
    "longcat": {"rotulo": "LongCat 1.5", "limite": LIMITE_SEGUNDOS,
                "resolucao": f"{LARGURA}×{ALTURA}", "segundos_por_segundo": 70},
    "ltx23": {"rotulo": "LTX 2.3", "limite": LTX23["limite"],
              "resolucao": f"{LTX23['largura']}×{LTX23['altura']}", "segundos_por_segundo": 15},
}


# Lip sync por API (nos de parceiro da Comfy; cobram creditos da conta, por
# segundo de fala). Entradas lidas do /object_info da nuvem em 23/10/2026.
# Limites: HeyGen aceita 10 min e VEED 5 min (dito nos nos); os de Kling e
# sync.so nao estao no no, entao ficam num teto prudente de 60 s.
API = {
    "kling": {"rotulo": "Kling Avatar 2.0", "limite": 60.0},
    "heygen": {"rotulo": "HeyGen Avatar IV", "limite": 300.0},
    "sync": {"rotulo": "sync.so sync-3", "limite": 60.0},
    "veed": {"rotulo": "VEED Fabric 1.0", "limite": 300.0},
}


def limite(modelo: str) -> float:
    return (MODELOS.get(modelo) or API[modelo])["limite"]


def grafo_api(p, seed: int, prefixo: str):
    """Foto + fala num no de parceiro, e o video salvo como os outros."""
    foto, fala = ["foto", 0], ["fala", 0]
    if p.modelo_avatar == "kling":
        no = {"class_type": "KlingAvatarNode", "inputs": {
            "image": foto, "sound_file": fala, "mode": "std", "seed": seed % 2147483647, "prompt": p.prompt}}
    elif p.modelo_avatar == "heygen":
        no = {"class_type": "HeyGenTalkingPhotoNode", "inputs": {
            "image": foto, "speech": "audio", "speech.audio": fala, "resolution": "1080p",
            "aspect_ratio": "9:16" if p.vertical_avatar else "16:9", "expressiveness": "medium",
            "seed": seed % 2147483647}}
    elif p.modelo_avatar == "sync":
        no = {"class_type": "SyncTalkingImageNode", "inputs": {
            "image": foto, "audio": fala, "prompt": p.prompt, "seed": seed % 2147483647,
            "model": "sync-3", "model.speaker_selection": "default", "model.speaker_x": 0,
            "model.speaker_y": 0, "model.auto_downscale": True}}
    elif p.modelo_avatar == "veed":
        no = {"class_type": "VeedFabricNode", "inputs": {
            "model": "fabric-1.0", "model.image": foto, "model.audio": fala, "model.resolution": "720p"}}
    else:
        raise ValueError("modelo de lip sync desconhecido")
    return {
        "foto": {"class_type": "LoadImage", "inputs": {"image": p.referencias[0]}},
        "fala": {"class_type": "LoadAudio", "inputs": {"audio": p.referencia_avatar}},
        "gera": no,
        "salva": {"class_type": "SaveVideo", "inputs": {"video": ["gera", 0], "filename_prefix": prefixo,
                                                        "format": "auto", "codec": "auto"}},
    }


async def capacidades():
    try:
        info = await comfy.info_nos(comfy.BASE_PRINCIPAL)
    except Exception as e:
        return {"disponivel": False, "motivo": comfy.motivo_sem_info(e), "modelos": []}

    def estado(nos, checar):
        faltam = [n for n in nos if n not in info]
        if faltam:
            return "Nós ausentes: " + ", ".join(faltam)
        return checar()

    def checar_longcat():
        lista = info["WanVideoModelLoader"]["input"]["required"]["model"][0]
        return "" if MODELO in lista else "O modelo LongCat-Avatar não está instalado."

    def checar_ltx23():
        lista = info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        return "" if CKPT_LTX23 in lista else "O checkpoint do LTX 2.3 não está instalado."

    motivos = {"longcat": estado(NOS, checar_longcat), "ltx23": estado(NOS_LTX23, checar_ltx23)}
    modelos = [{"id": k, **v, "disponivel": not motivos[k], "motivo": motivos[k]}
               for k, v in MODELOS.items()]
    algum = any(m["disponivel"] for m in modelos)
    return {"disponivel": algum, "motivo": "" if algum else motivos["longcat"],
            "limite": LIMITE_SEGUNDOS, "modelos": modelos}


def grafo_ltx23(p, seed: int, duracao: float, prefixo: str, vertical: bool = False):
    """O grafo testado, so com as entradas trocadas."""
    import json
    g = json.loads(GRAFO_LTX23.read_text(encoding="utf-8"))
    cena = (p.prompt.strip().rstrip(".") or CENA_PADRAO)
    g["269"]["inputs"]["image"] = p.referencias[0]
    g["276"]["inputs"]["audio"] = p.referencia_avatar
    g["340:319"]["inputs"]["value"] = f"{cena}. {FALA_VISIVEL} {CAMERA_FIXA}"
    g["340:331"]["inputs"]["value"] = round(max(1.0, duracao - SOBRA_GUIA_LTX23), 3)
    g["340:285"]["inputs"]["noise_seed"] = seed
    g["340:286"]["inputs"]["noise_seed"] = seed + 1
    g["341"]["inputs"]["filename_prefix"] = prefixo
    if vertical:
        # 340:330 e a largura e 340:324 a altura da 2a etapa; a 1a usa a metade.
        g["340:330"]["inputs"]["value"], g["340:324"]["inputs"]["value"] = LTX23_VERTICAL
    return g


async def duracao_audio(nome: str) -> float:
    # O arquivo foi enviado para a pasta input DESTA maquina; na Comfy Cloud ele
    # so sobe na hora de gerar, entao perguntar ao motor da nuvem nao acharia.
    # So um nome simples da pasta input: "C:\...", "/..." ou ".." leriam fora dela.
    if not nome or pathlib.PurePath(nome).name != nome or "\\" in nome or "/" in nome or nome in (".", ".."):
        raise ValueError("nome de áudio inválido")
    local = config.COMFY_ENTRADA / nome
    dados = (await asyncio.to_thread(local.read_bytes) if local.is_file()
             else await comfy.imagem(nome, "", "input"))
    return (await asyncio.to_thread(sf.info, io.BytesIO(dados))).duration


def segmentos(duracao: float) -> int:
    quadros = math.ceil(duracao * FPS)
    passo = JANELA - SOBREPOSICAO
    return 1 + max(0, math.ceil((quadros - JANELA) / passo))


def _recortar(dados: bytes, vertical: bool = False):
    """Recorte 16:9 (ou 9:16) de cabeca e ombros em volta do maior rosto, ou None.

    Com a foto inteira, o rosto chegava ao video com ~180 px de altura e a
    boca nao tinha pixels para dentes. Recortada no rosto, a boca fica com
    o dobro.
    """
    img = cv2.imdecode(np.frombuffer(dados, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("imagem ilegível")
    h, w = img.shape[:2]
    detector = cv2.FaceDetectorYN.create(str(DETECTOR), "", (w, h), CONFIANCA_ROSTO)
    _, rostos = detector.detect(img)
    if rostos is None or not len(rostos):
        return None
    x, y, lr, ar = max(rostos, key=lambda r: r[2] * r[3])[:4]
    # Altura do recorte = 2,3x a do rosto: cabeca inteira e um pouco de ombro.
    # No 9:16 a largura sai de 9/16 da altura; com 2,3x a cabeca nao caberia
    # de lado a lado, entao a altura vai a 3,2x (cabeca, ombros e peito).
    prop = 9 / 16 if vertical else 16 / 9
    ch = min(h, round(ar * (3.2 if vertical else 2.3)))
    cw = min(w, round(ch * prop))
    ch = min(h, round(cw / prop))
    cw = round(ch * prop)
    x0 = int(min(max(x + lr / 2 - cw / 2, 0), w - cw))
    y0 = min(max(y - 0.45 * ar, 0), h - ch)
    # Retrato fechado (o rosto enche a foto): o recorte nao cabe a cabeca toda
    # e, preso no alto da cabeca, cortava a BOCA fora (medido em 28/10: video
    # so com testa, olhos e nariz, labios parados). A boca e o queixo vem antes.
    fundo_rosto = y + 1.08 * ar
    if fundo_rosto > y0 + ch:
        y0 = min(h - ch, fundo_rosto - ch)
    y0 = int(max(0, y0))
    ok, png = cv2.imencode(".png", img[y0:y0 + ch, x0:x0 + cw])
    return png.tobytes()


async def recortar_no_rosto(nome: str, vertical: bool = False):
    """Sobe o recorte como nova referencia. Devolve (nome, achou_rosto)."""
    # Sempre na pasta input DESTA maquina, inclusive no modo Comfy Cloud: a
    # nuvem recebe o recorte na hora de gerar (nuvem.preparar sobe o arquivo).
    local = config.COMFY_ENTRADA / nome
    dados = (await asyncio.to_thread(local.read_bytes) if local.is_file()
             else await comfy.imagem(nome, "", "input"))
    recorte = await asyncio.to_thread(_recortar, dados, vertical)
    if recorte is None:
        return nome, False
    novo = f"avatar_{uuid.uuid4().hex[:12]}.png"
    await asyncio.to_thread((config.COMFY_ENTRADA / novo).write_bytes, recorte)
    return novo, True


def _no(tipo, **entradas):
    return {"class_type": tipo, "inputs": entradas}


def _codifica(vae, imagem):
    return _no("WanVideoEncode", enable_vae_tiling=False, tile_x=272, tile_y=272,
               tile_stride_x=144, tile_stride_y=128, noise_aug_strength=0,
               latent_strength=1, vae=vae, image=imagem)


def _decodifica(vae, amostras):
    return _no("WanVideoDecode", enable_vae_tiling=False, tile_x=272, tile_y=272,
               tile_stride_x=144, tile_stride_y=128, normalization="default",
               vae=vae, samples=amostras)


def grafo(p, seed: int, duracao: float, prefixo: str):
    cena = (p.prompt.strip().rstrip(".") or CENA_PADRAO)
    g = {
        "foto": _no("LoadImage", image=p.referencias[0]),
        "foto_ajustada": _no("ImageResizeKJv2", width=LARGURA, height=ALTURA,
                             upscale_method="lanczos", keep_proportion="crop",
                             pad_color="0, 0, 0", crop_position="center",
                             divisible_by=16, device="cpu", image=["foto", 0]),
        "fala": _no("LoadAudio", audio=p.referencia_avatar),
        "fala_cortada": _no("TrimAudioDuration", start_index=0, duration=2048,
                            audio=["fala", 0]),
        "whisper": _no("WhisperModelLoader", model=WHISPER, base_precision="fp16",
                       load_device="main_device"),
        "audio_emb": _no("LongCatAvatarWhisperEmbeds", whisper_model=["whisper", 0],
                         audio_1=["fala_cortada", 0], normalize_loudness=True,
                         num_frames=math.ceil(duracao * FPS), fps=float(FPS),
                         audio_scale=1.0, audio_cfg_scale=float(AUDIO_CFG),
                         multi_audio_type="para"),
        "vae": _no("WanVideoVAELoader", model_name="Wan2_1_VAE_bf16.safetensors",
                   precision="bf16", use_cpu_cache=False, verbose=False),
        "lora": _no("WanVideoLoraSelect", lora=LORA, strength=FORCA_LORA,
                    low_mem_load=False, merge_loras=False),
        "blocos": _no("WanVideoBlockSwap", blocks_to_swap=BLOCOS_NA_RAM,
                      offload_img_emb=False, offload_txt_emb=False,
                      use_non_blocking=False, vace_blocks_to_swap=0,
                      prefetch_blocks=1, block_swap_debug=False),
        "modelo": _no("WanVideoModelLoader", model=MODELO, base_precision="bf16",
                      quantization="disabled", load_device="offload_device",
                      attention_mode=ATENCAO, rms_norm_function="default",
                      block_swap_args=["blocos", 0], lora=["lora", 0]),
        "texto": _no("WanVideoTextEncodeCached", model_name="umt5-xxl-enc-bf16.safetensors",
                     precision="bf16", positive_prompt=f"{cena}. {CAMERA_FIXA}",
                     negative_prompt=NEGATIVO, quantization="disabled",
                     use_disk_cache=True, device="gpu"),
        "agenda": _no("WanVideoSchedulerv2", scheduler="longcat_distill_euler",
                      steps=PASSOS, shift=12, start_step=0, end_step=-1, enhance_hf=False),
        "ref": _codifica(["vae", 0], ["foto_ajustada", 0]),
    }
    comum = {"num_frames": JANELA, "if_not_enough_audio": "pad_with_start",
             "ref_frame_index": 10, "ref_mask_frame_range": MASCARA_REFERENCIA,
             "audio_embeds": ["audio_emb", 0]}
    amostra = {"cfg": 1.0, "force_offload": True, "add_noise_to_samples": False,
               "model": ["modelo", 0], "scheduler": ["agenda", 0],
               "text_embeds": ["texto", 0]}

    g["emb_1"] = _no("WanVideoLongCatAvatarExtendEmbeds", overlap=1, frames_processed=0,
                     prev_latents=["ref", 0], **comum)
    g["amostra_1"] = _no("WanVideoSamplerv2", seed=seed, image_embeds=["emb_1", 0], **amostra)
    g["video_1"] = _decodifica(["vae", 0], ["amostra_1", 0])
    imagens, anterior = ["video_1", 0], "amostra_1"

    # Cada segmento continua dos ultimos 13 quadros do anterior e consulta a
    # foto original (ref_latent) para o rosto nao derivar.
    for n in range(2, segmentos(duracao) + 1):
        g[f"conta_{n}"] = _no("GetImageSizeAndCount", image=imagens)
        g[f"cauda_{n}"] = _no("GetImageRangeFromBatch", start_index=-1,
                              num_frames=SOBREPOSICAO, images=[f"conta_{n}", 0])
        g[f"cauda_lat_{n}"] = _codifica(["vae", 0], [f"cauda_{n}", 0])
        g[f"emb_{n}"] = _no("WanVideoLongCatAvatarExtendEmbeds", overlap=SOBREPOSICAO,
                            frames_processed=[f"conta_{n}", 3], prev_latents=[anterior, 0],
                            ref_latent=["ref", 0], **comum)
        g[f"amostra_{n}"] = _no("WanVideoSamplerv2", seed=seed + n - 1,
                                image_embeds=[f"emb_{n}", 0], **amostra)
        g[f"troca_{n}"] = _no("ReplaceVideoLatentFrames", index=0,
                              destination=[f"amostra_{n}", 0], source=[f"cauda_lat_{n}", 0])
        g[f"video_{n}"] = _decodifica(["vae", 0], [f"troca_{n}", 0])
        g[f"junta_{n}"] = _no("ImageBatchExtendWithOverlap", overlap=SOBREPOSICAO,
                              overlap_side="new_images", overlap_mode="cut",
                              source_images=[f"conta_{n}", 0], new_images=[f"video_{n}", 0])
        imagens, anterior = [f"junta_{n}", 2], f"amostra_{n}"

    g["salva"] = _no("VHS_VideoCombine", frame_rate=FPS, loop_count=0,
                     filename_prefix=prefixo, format="video/h264-mp4", pix_fmt="yuv420p",
                     crf=19, save_metadata=True, trim_to_audio=True, pingpong=False,
                     save_output=True, images=imagens, audio=["fala_cortada", 0])
    return g
