"""Genjutsu: refazer um video com outro elenco, lugar ou estilo, mantendo o
movimento, a camera e o tempo.

Modelos (a tela mostra numa caixa suspensa):
- recast (aberto, padrao): dois passos. O Qwen Image Edit redesenha o primeiro
  quadro com as referencias; o LTX Union Control (efeito "trocar") leva o video
  inteiro para essa cara nova. Quem encadeia os dois e a tela (AbaGenjutsu);
  aqui so sai o primeiro quadro (primeiro_quadro).
- wan_animate2 (aberto): a foto do personagem faz o movimento do video.
  Grafo do template oficial video_wan_animate2_distilled (um trecho, 10 passos).
- higgsfield, kling_omni, aleph2: nos de parceiro da Comfy (creditos).
"""
import pathlib
import subprocess
import tempfile

import config
import miniaturas

# Wan Animate 2: o template gera 81 quadros por trecho; o app faz um trecho,
# a 16 fps (a cadencia do Wan), ou seja ~5 s.
WAN_FPS = 16
WAN_QUADROS = 81

MODELOS = {
    "recast": {"rotulo": "Recast", "aberto": True, "max_refs": 2, "max_segundos": 14.7},
    "wan_animate2": {"rotulo": "Wan Animate 2", "aberto": True, "max_refs": 1,
                     "max_segundos": WAN_QUADROS / WAN_FPS,
                     # Tempo de GPU na nuvem por trecho de 81 quadros (estimado, a medir).
                     "segundos_gpu": 120},
    # Template oficial do Wan 2.2 Animate (modo Mix), mascara pelo SAM 3. Nuvem, ou local com o pacote.
    "wan22_replace": {"rotulo": "Wan 2.2 Animate · Replace", "aberto": True, "max_refs": 1,
                      "max_segundos": WAN_QUADROS / WAN_FPS, "pacote": "wan22_animate", "segundos_gpu": 150},
    "higgsfield": {"rotulo": "Higgsfield Genjutsu", "aberto": False, "max_refs": 8, "max_segundos": 30},
    "kling_omni": {"rotulo": "Kling 3.0 Omni", "aberto": False, "max_refs": 4, "max_segundos": 10},
    "aleph2": {"rotulo": "Runway Aleph2", "aberto": False, "max_refs": 0, "max_segundos": 30},
    # Workflow do MDMZ (ver grafo_h3_swap). So na Comfy Cloud; tempo de GPU a medir.
    "h3_swap": {"rotulo": "MiniMax H3 Character Swap", "aberto": True, "max_refs": 1, "max_segundos": 8,
                "pacote": "h3_swap", "segundos_gpu": 240},
}

NEGATIVO_WAN = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，"
                "低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，"
                "毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True, capture_output=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def primeiro_quadro(caminho: str, nome: str) -> str:
    """O primeiro quadro do video como PNG na pasta de entrada do motor."""
    destino = config.COMFY_ENTRADA / nome
    _ffmpeg("-i", caminho, "-frames:v", "1", str(destino))
    return nome


def video_wan(caminho: str) -> bytes:
    """O trecho que o Wan Animate 2 usa: 16 fps, ate 81 quadros, com o som."""
    with tempfile.TemporaryDirectory() as pasta:
        saida = pathlib.Path(pasta) / "wan.mp4"
        _ffmpeg("-i", caminho, "-vf", f"fps={WAN_FPS}", "-frames:v", str(WAN_QUADROS),
                "-c:v", "libx264", "-crf", "14", "-c:a", "aac", str(saida))
        return saida.read_bytes()


# O Kling 3.0 Omni recusa video com menos de 720 px ("Video height must be at least
# 720px, got 704px"; teste de 29/10/2026), e os videos do proprio app (LTX, Lip Sync)
# saem com 704. Amplia so o que falta, mantendo a proporcao.
KLING_MINIMO = 720


def video_minimo(caminho: str, largura: int, altura: int, minimo: int = KLING_MINIMO) -> bytes | None:
    """O video com o lado menor em `minimo` px, ou None se ja tem isso."""
    menor = min(largura, altura)
    if not menor or menor >= minimo:
        return None
    escala = minimo / menor
    larg, alt = (max(minimo, -(-round(largura * escala) // 2) * 2), max(minimo, -(-round(altura * escala) // 2) * 2))
    with tempfile.TemporaryDirectory() as pasta:
        saida = pathlib.Path(pasta) / "kling.mp4"
        _ffmpeg("-i", caminho, "-vf", f"scale={larg}:{alt}:flags=lanczos",
                "-c:v", "libx264", "-crf", "14", "-c:a", "aac", str(saida))
        return saida.read_bytes()


def tamanho_wan(largura: int, altura: int) -> tuple[int, int]:
    """832x480 deitado, 480x832 em pe, 640x640 quadrado (multiplos de 16)."""
    r = largura / max(1, altura)
    return (832, 480) if r > 1.2 else (480, 832) if r < 0.83 else (640, 640)


def quadros_wan(dados: bytes) -> int:
    """Quadros do trecho, no formato 4n+1 que o Wan aceita."""
    d = miniaturas.dados_do_video(dados)
    n = min(WAN_QUADROS, int((d["duracao"] or 5) * WAN_FPS))
    return max(17, (n - 1) // 4 * 4 + 1)


def grafo_wan_animate2(video, foto, texto, quadros, largura, altura, seed, prefixo):
    def no(tipo, **e): return {"class_type": tipo, "inputs": e}
    g = {
        "unet": no("UNETLoader", unet_name="wan_animate_2_distill_int8_convrot.safetensors", weight_dtype="default"),
        "clip": no("CLIPLoader", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default"),
        "neg": no("CLIPTextEncode", clip=["clip", 0], text=NEGATIVO_WAN),
        "pos": no("CLIPTextEncode", clip=["clip", 0], text=texto),
        # O ramo da pose descreve o movimento, nao o personagem.
        "pos_pose": no("CLIPTextEncode", clip=["clip", 0], text="Reference video of a person moving"),
        "visao": no("CLIPVisionLoader", clip_name="clip_vision_h.safetensors"),
        "vae": no("VAELoader", vae_name="Wan2_1_VAE_bf16.safetensors"),
        "carga": no("LoadVideo", file=video),
        "partes": no("GetVideoComponents", video=["carga", 0]),
        "pose": no("ResizeImageMaskNode", input=["partes", 0], resize_type="scale dimensions",
                   **{"resize_type.width": largura, "resize_type.height": altura,
                      "resize_type.crop": "center"}, scale_method="area"),
        "pose1": no("ImageFromBatch", image=["pose", 0], batch_index=0, length=1),
        "visao_pose": no("CLIPVisionEncode", clip_vision=["visao", 0], image=["pose1", 0], crop="none"),
        "foto": no("LoadImage", image=foto),
        "ref": no("ResizeImageMaskNode", input=["foto", 0], resize_type="scale dimensions",
                  **{"resize_type.width": largura, "resize_type.height": altura,
                     "resize_type.crop": "center"}, scale_method="area"),
        "visao_ref": no("CLIPVisionEncode", clip_vision=["visao", 0], image=["ref", 0], crop="none"),
        "cache": no("WanAnimate2Cache", model=["unet", 0], device="gpu", dtype="int8"),
        "anima": no("WanAnimate2ToVideo", positive=["pos", 0], negative=["neg", 0], vae=["vae", 0],
                    width=largura, height=altura, length=quadros, batch_size=1, video_frame_offset=0,
                    pose_strength=1.0, pose_start_percent=0.0, pose_end_percent=1.0,
                    reference_image_strength=1.0, reference_image=["ref", 0], pose_video=["pose", 0],
                    clip_vision_output=["visao_ref", 0], positive_pose=["pos_pose", 0],
                    clip_vision_output_pose=["visao_pose", 0]),
        "amostragem": no("ModelSamplingSD3", model=["cache", 0], shift=5.0),
        "passos": no("BasicScheduler", model=["cache", 0], scheduler="simple", steps=10, denoise=1.0),
        "amostrador": no("KSamplerSelect", sampler_name="lcm"),
        "amostra": no("SamplerCustom", model=["amostragem", 0], add_noise=True, noise_seed=seed, cfg=1.0,
                      positive=["anima", 0], negative=["anima", 1], sampler=["amostrador", 0],
                      sigmas=["passos", 0], latent_image=["anima", 2]),
        "corta": no("TrimVideoLatent", samples=["amostra", 0], trim_amount=["anima", 3]),
        "decodifica": no("VAEDecode", samples=["corta", 0], vae=["vae", 0]),
        "video": no("CreateVideo", images=["decodifica", 0], audio=["partes", 1], fps=["partes", 2]),
        "salva": no("SaveVideo", video=["video", 0], filename_prefix=prefixo, format="auto", codec="auto"),
    }
    return g


def grafo_api(modelo, video, refs, prompt, seed, duracao, proporcao, prefixo):
    def no(tipo, **e): return {"class_type": tipo, "inputs": e}
    g = {"carga": no("LoadVideo", file=video)}
    for i, r in enumerate(refs):
        g[f"ref{i}"] = no("LoadImage", image=r)
    if modelo == "higgsfield":
        if not refs:
            raise ValueError("envie ao menos uma imagem de referência")
        ent = {"model": "genjutsu-v1.0", "model.video": ["carga", 0], "model.prompt": prompt,
               "model.resolution": "720p", "model.seed": seed % 2147483647}
        for i in range(len(refs)):
            ent[f"model.reference_images.image_{i + 1}"] = [f"ref{i}", 0]
        g["gera"] = no("HiggsfieldMotionTransferNode", **ent)
    elif modelo == "kling_omni":
        ent = {"model_name": "kling-v3-omni", "prompt": prompt, "aspect_ratio": proporcao,
               "duration": max(3, min(10, round(duracao))), "reference_video": ["carga", 0],
               "keep_original_sound": True, "resolution": "720p", "seed": seed % 2147483647}
        if refs:
            g["lote"] = no("BatchImagesNode", **{f"images.image{i}": [f"ref{i}", 0] for i in range(len(refs))})
            ent["reference_images"] = ["lote", 0]
        g["gera"] = no("KlingOmniProVideoToVideoNode", **ent)
    elif modelo == "aleph2":
        g["gera"] = no("RunwayAleph2VideoToVideoNode", prompt=prompt, video=["carga", 0],
                       seed=seed % 2147483647, public_figure_threshold="auto")
    else:
        raise ValueError("modelo de Genjutsu desconhecido")
    g["salva"] = no("SaveVideo", video=["gera", 0], filename_prefix=prefixo, format="auto", codec="auto")
    return g


# ---------------------------------------------------------------------------
# MiniMax H3 Character Swap (workflow H3_Character_Swap_MDMZ_v1, de MDMZ).
# O SAM 3 acha quem trocar; essa pessoa entra com as cores invertidas num video
# pequeno (0,15 MP) que guia so o movimento; o H3 Ref2VA desenha o personagem
# da foto com o movimento, a camera e o som do original.
#
# Os TEXTOS do workflow (instrucoes do Gemini, prompt padrao, regras de fundo,
# luz e enquadramento) sao autorais (post gratuito do MDMZ, https://www.patreon.com/MDMZ/posts/h3-character-172119619): NAO entram no
# codigo. Sao lidos do .json dele em backend/terceiros/ (fora do git). Sem o
# arquivo, o modelo nao aparece. Aqui fica so a ligacao dos nos.
# Roda na Comfy Cloud, ou local com o pacote "h3_swap" (Config Models; ~46 GB,
# placa de 24-32 GB). Os nomes locais tem subpasta; os da nuvem, nao.
H3_ARQUIVO = pathlib.Path(__file__).parent / "terceiros" / "H3_Character_Swap_MDMZ_v1.json"
H3_FPS = 24
H3_MAX_QUADROS = 192          # 8 s; o workflow vem com 107 (4,4 s)
# Ids dos nos de texto no workflow do MDMZ.
_H3_TEXTOS = {"instrucoes": 1002, "padrao": 910, "pedido": 1001,
              "regras": [1010, 1011, 1012, 961, 962]}


def h3_disponivel() -> bool:
    return H3_ARQUIVO.exists()


def _h3_textos() -> dict:
    import json
    w = json.loads(H3_ARQUIVO.read_text(encoding="utf-8"))
    nos = {n["id"]: n for n in w["nodes"]}
    val = lambda i: nos[i].get("widgets_values_named") or {}
    return {"instrucoes": val(_H3_TEXTOS["instrucoes"])["value"],
            "padrao": val(_H3_TEXTOS["padrao"])["value"],
            "pedido": val(_H3_TEXTOS["pedido"])["value"],
            "regras": [val(i) for i in _H3_TEXTOS["regras"]]}


def video_h3(caminho: str, segundos: float = H3_MAX_QUADROS / H3_FPS) -> tuple[bytes, int]:
    """O trecho a 24 fps, com o som, e quantos quadros o H3 usa (5 + 17k)."""
    with tempfile.TemporaryDirectory() as pasta:
        saida = pathlib.Path(pasta) / "h3.mp4"
        n = min(H3_MAX_QUADROS, max(22, int(segundos * H3_FPS)))
        _ffmpeg("-i", caminho, "-vf", f"fps={H3_FPS}", "-frames:v", str(n),
                "-c:v", "libx264", "-crf", "14", "-c:a", "aac", str(saida))
        dados = saida.read_bytes()
    d = miniaturas.dados_do_video(dados)
    total = max(22, int(round((d["duracao"] or n / H3_FPS) * H3_FPS)))
    total = min(total, n)
    return dados, total - ((total - 5) % 17)


def tamanho_h3(largura: int, altura: int, megapixels: float = 0.5) -> tuple[int, int]:
    """O tamanho de saida: a proporcao do video, com `megapixels`, multiplos de 32."""
    r = largura / max(1, altura)
    alt = (megapixels * 1e6 / r) ** 0.5
    return int(round(alt * r / 32) * 32), int(round(alt / 32) * 32)


_H3_LOCAL = {"minimax_h3_ref2va_pruned_int8_convrot.safetensors": "Minimax",
             "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors": "Qwen",
             "minimax_h3_video_vae_fp16.safetensors": "Minimax", "minimax_h3_audio_vae_fp32.safetensors": "Minimax",
             "sam3.1_multiplex_fp16.safetensors": "SAM3",
             "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors": "Minimax"}


def grafo_h3_swap(video, foto, quadros, largura, altura, seed, prefixo, alvo="person",
                  pedido="", gemini=True, turbo=False, com_som=True, local=False):
    t = _h3_textos()
    g = _grafo_h3(video, foto, quadros, largura, altura, seed, prefixo, alvo, pedido, gemini, turbo, com_som, t)
    if local:  # o instalador grava com subpasta (catalogo/pacotes.json)
        for n in g.values():
            for k, v in n["inputs"].items():
                if isinstance(v, str) and v in _H3_LOCAL:
                    n["inputs"][k] = _H3_LOCAL[v] + "\\" + v
    return g


def _grafo_h3(video, foto, quadros, largura, altura, seed, prefixo, alvo, pedido, gemini, turbo, com_som, t):
    g = {
        "video": {"class_type": "LoadVideo", "inputs": {"file": video}},
        "partes": {"class_type": "GetVideoComponents", "inputs": {"video": ["video", 0]}},
        "foto": {"class_type": "LoadImage", "inputs": {"image": foto}},
        # Mascara de quem sai, pelo texto (ex.: "person", "woman in red:1").
        "sam": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sam3.1_multiplex_fp16.safetensors"}},
        "alvo": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["sam", 1], "text": alvo or "person"}},
        "detecta": {"class_type": "SAM3_Detect", "inputs": {"model": ["sam", 0], "image": ["partes", 0], "conditioning": ["alvo", 0],
                                                            "threshold": 0.5, "refine_iterations": 2, "individual_masks": False}},
        # A pessoa invertida, o resto como esta, em 0,15 MP: guia o movimento sem copiar a cara.
        "inverte": {"class_type": "ImageInvert", "inputs": {"image": ["partes", 0]}},
        "guia": {"class_type": "ImageCompositeMasked", "inputs": {"destination": ["partes", 0], "source": ["inverte", 0],
                                                                  "mask": ["detecta", 0], "x": 0, "y": 0, "resize_source": False}},
        "guia_pequena": {"class_type": "ImageScaleToTotalPixels", "inputs": {"image": ["guia", 0], "upscale_method": "nearest-exact",
                                                                             "megapixels": 0.15, "resolution_steps": 1}},
        "unet": {"class_type": "UNETLoader", "inputs": {"unet_name": "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "weight_dtype": "default"}},
        "clip": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", "type": "minimax", "device": "default"}},
        "vae": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_video_vae_fp16.safetensors"}},
        "vae_som": {"class_type": "VAELoader", "inputs": {"vae_name": "minimax_h3_audio_vae_fp32.safetensors"}},
    }
    # O prompt no formato do H3: o Gemini assiste o trecho e escreve (pago, centavos),
    # ou vai o prompt padrao do workflow. Os dois passam pelas mesmas regras.
    if gemini:
        g["clipe"] = {"class_type": "CreateVideo", "inputs": {"images": ["partes", 0], "fps": H3_FPS,
                                                             **({"audio": ["partes", 1]} if com_som else {})}}
        g["gemini"] = {"class_type": "GeminiNodeV3", "inputs": {
            "model": "Gemini 3.7 Flash", "model.prompt": pedido.strip() or t["pedido"],
            "model.images.image_1": ["foto", 0], "model.video.video_1": ["clipe", 0],
            "model.system_prompt": t["instrucoes"], "model.thinking_level": "MEDIUM", "model.temperature": 1,
            "model.top_p": 0.95, "model.max_output_tokens": 32768, "model.seed": 42}}
        texto = ["gemini", 0]
    else:
        texto = t["padrao"]
    for i, r in enumerate(t["regras"]):
        g[f"regra{i}"] = {"class_type": "RegexReplace", "inputs": {
            "string": texto, "regex_pattern": r["regex_pattern"], "replace": r["replace"],
            "case_insensitive": r.get("case_insensitive", True), "multiline": r.get("multiline", True),
            "dotall": r.get("dotall", False), "count": r.get("count", 0)}}
        texto = [f"regra{i}", 0]
    g["h3"] = {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
        "clip": ["clip", 0], "vae": ["vae", 0], "audio_vae": ["vae_som", 0], "prompt": texto,
        "width": largura, "height": altura, "length": quadros, "ref_image_size": "match",
        "ref_images.ref_image_0": ["foto", 0], "ref_videos.ref_video_0": ["guia_pequena", 0],
        **({"ref_audios.ref_audio_0": ["partes", 1]} if com_som else {})}}
    g["ruido"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": seed % 2**50}}
    if turbo:
        # LightX2V Ref2V Turbo: 8 passos no modelo podado (4 no completo), euler, shift 12/3.
        g["lora"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["unet", 0], "lora_name": "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", "strength_model": 1}}
        g["shift"] = {"class_type": "MiniMaxH3SigmaShift", "inputs": {"model": ["lora", 0], "shift_video": 12, "shift_audio": 3}}
        modelo, amostrador, passos = ["shift", 0], "euler", 8
        g["passos"] = {"class_type": "BasicScheduler", "inputs": {"model": ["lora", 0], "scheduler": "simple", "steps": passos, "denoise": 1}}
    else:
        modelo, amostrador = ["unet", 0], "res_multistep"
        g["passos"] = {"class_type": "BasicScheduler", "inputs": {"model": ["unet", 0], "scheduler": "simple", "steps": 20, "denoise": 1}}
    g["amostrador"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": amostrador}}
    g["guiador"] = {"class_type": "BasicGuider", "inputs": {"model": modelo, "conditioning": ["h3", 0]}}
    g["amostra"] = {"class_type": "SamplerCustomAdvanced", "inputs": {
        "noise": ["ruido", 0], "guider": ["guiador", 0], "sampler": ["amostrador", 0],
        "sigmas": ["passos", 0], "latent_image": ["h3", 1]}}
    g["decodifica"] = {"class_type": "VAEDecode", "inputs": {"samples": ["amostra", 0], "vae": ["vae", 0]}}
    # O som e o do video original, como no workflow.
    g["junta"] = {"class_type": "CreateVideo", "inputs": {"images": ["decodifica", 0], "fps": H3_FPS,
                                                         **({"audio": ["partes", 1]} if com_som else {})}}
    g["salva"] = {"class_type": "SaveVideo", "inputs": {"video": ["junta", 0], "filename_prefix": prefixo,
                                                       "format": "auto", "codec": "auto"}}
    return g


# ---------------------------------------------------------------------------
# Wan 2.2 Animate · Replace: troca a pessoa DENTRO do video, mantendo o lugar.
# Base: template oficial video_wan2_2_14B_animate (modo "Mix"), com uma troca:
# a mascara vem do SAM 3 por texto ("person"), e nao do SAM 2 com cliques num
# editor de pontos, que nao existe fora do ComfyUI. DWPose extrai o rosto e o
# corpo; o fundo e o video com a pessoa apagada em blocos; o LoRA de relight
# acende o personagem com a luz da cena. Um trecho de 81 quadros a 16 fps (~5 s).
def grafo_wan22_replace(video, foto, texto, quadros, largura, altura, seed, prefixo, alvo="person"):
    def no(tipo, **e): return {"class_type": tipo, "inputs": e}
    dw = dict(resolution=["resolucao", 0], bbox_detector="yolox_l.onnx",
              pose_estimator="dw-ll_ucoco_384_bs5.torchscript.pt", scale_stick_for_xinsr_cn="disable")
    return {
        "carga": no("LoadVideo", file=video),
        "partes": no("GetVideoComponents", video=["carga", 0]),
        "escala": no("ImageScale", image=["partes", 0], upscale_method="lanczos", width=largura, height=altura, crop="center"),
        "resolucao": no("PixelPerfectResolution", original_image=["partes", 0], image_gen_width=largura,
                        image_gen_height=altura, resize_mode="Just Resize"),
        "rosto": no("DWPreprocessor", image=["escala", 0], detect_hand="disable", detect_body="disable", detect_face="enable", **dw),
        "corpo": no("DWPreprocessor", image=["escala", 0], detect_hand="enable", detect_body="enable", detect_face="disable", **dw),
        "sam": no("CheckpointLoaderSimple", ckpt_name="sam3.1_multiplex_fp16.safetensors"),
        "alvo": no("CLIPTextEncode", clip=["sam", 1], text=alvo or "person"),
        "detecta": no("SAM3_Detect", model=["sam", 0], image=["escala", 0], conditioning=["alvo", 0],
                      threshold=0.5, refine_iterations=2, individual_masks=False),
        "cresce": no("GrowMask", mask=["detecta", 0], expand=10, tapered_corners=True),
        "blocos": no("BlockifyMask", masks=["cresce", 0], block_size=32),
        "fundo": no("DrawMaskOnImage", image=["escala", 0], mask=["blocos", 0], color="0, 0, 0"),
        "unet": no("UNETLoader", unet_name="Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors", weight_dtype="default"),
        "rapido": no("LoraLoaderModelOnly", model=["unet", 0], strength_model=1.0,
                     lora_name="lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors"),
        "reluz": no("LoraLoaderModelOnly", model=["rapido", 0], lora_name="WanAnimate_relight_lora_fp16.safetensors", strength_model=1.0),
        "amostragem": no("ModelSamplingSD3", model=["reluz", 0], shift=8.0),
        "clip": no("CLIPLoader", clip_name="umt5_xxl_fp8_e4m3fn_scaled.safetensors", type="wan", device="default"),
        "pos": no("CLIPTextEncode", clip=["clip", 0], text=texto or "The person moves naturally"),
        "neg": no("CLIPTextEncode", clip=["clip", 0], text=NEGATIVO_WAN),
        "vae": no("VAELoader", vae_name="Wan2_1_VAE_bf16.safetensors"),
        "foto": no("LoadImage", image=foto),
        "visao": no("CLIPVisionLoader", clip_name="clip_vision_h.safetensors"),
        "visao_ref": no("CLIPVisionEncode", clip_vision=["visao", 0], image=["foto", 0], crop="none"),
        "anima": no("WanAnimateToVideo", positive=["pos", 0], negative=["neg", 0], vae=["vae", 0],
                    width=largura, height=altura, length=quadros, batch_size=1, continue_motion_max_frames=5,
                    video_frame_offset=0, clip_vision_output=["visao_ref", 0], reference_image=["foto", 0],
                    face_video=["rosto", 0], pose_video=["corpo", 0], background_video=["fundo", 0],
                    character_mask=["blocos", 0]),
        "amostra": no("KSampler", model=["amostragem", 0], seed=seed % 2**50, steps=6, cfg=1.0, sampler_name="euler",
                      scheduler="simple", positive=["anima", 0], negative=["anima", 1], latent_image=["anima", 2], denoise=1.0),
        "corta": no("TrimVideoLatent", samples=["amostra", 0], trim_amount=["anima", 3]),
        "decodifica": no("VAEDecode", samples=["corta", 0], vae=["vae", 0]),
        "quadros": no("ImageFromBatch", image=["decodifica", 0], batch_index=["anima", 4], length=4096),
        "video": no("CreateVideo", images=["quadros", 0], audio=["partes", 1], fps=WAN_FPS),
        "salva": no("SaveVideo", video=["video", 0], filename_prefix=prefixo, format="auto", codec="auto"),
    }
