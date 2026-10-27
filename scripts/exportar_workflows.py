"""Exporta os workflows principais do app em JSON (formato API do ComfyUI).

O app monta cada grafo em Python (backend/workflows.py e vizinhos). Este script
chama os MESMOS construtores com entradas de exemplo e grava o resultado em
comfy_workflows/, para quem quiser abrir o fluxo no proprio ComfyUI (arrastar o
.json para a tela) ou estudar como cada modo foi feito. Rodar de novo sempre
que um construtor mudar:

    backend/.venv/Scripts/python.exe scripts/exportar_workflows.py
"""

import json
import pathlib
import sys
from types import SimpleNamespace

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "backend"))

import avatar  # noqa: E402
import genjutsu  # noqa: E402
import ltx23  # noqa: E402
import presets  # noqa: E402
import videos_leves  # noqa: E402
import workflows as W  # noqa: E402

SAIDA = RAIZ / "comfy_workflows"
TEXTO = "A detective in a soaked neon alley at night, slow push-in, rain, distant traffic"
FX = presets.VIDEO_TRANSFORMAR


def efeito(id):
    e = FX["efeitos"][id]
    if e.get("formatos"):
        return W.expandir_enquadramento("input_video.mp4", e["lora_completo"], e["texto"], 121,
                                        (1080, 1920), e["formatos"]["16:9"])
    if e.get("controles"):
        return W.trocar_personagem_video("input_video.mp4", e["lora_completo"], "", 121, 1024, 576,
                                         "first_frame.png", controle="profundidade" if id == "profundidade" else "pose")
    if e.get("imagem_estilo"):
        return W.maquete_ltx("input_video.mp4", FX["lora_pasta"] + e["lora"], "", 121, 1024, 576,
                             "look.png", [("keyframe_2.png", 65)])
    return W.transformar_video("input_video.mp4", FX["lora_pasta"] + e["lora"], e["texto"], 121, 960, 544)


# (arquivo, descricao, construtor)
FLUXOS = [
    ("image_krea2", "Image: text to image with Krea 2 Turbo", lambda: W.gerar_simples("krea", TEXTO, "", 1, 1344, 768)),
    ("image_zimage", "Image: Z-Image Turbo", lambda: W.gerar_simples("zimage", TEXTO, "", 1, 1344, 768)),
    ("image_flux3_klein", "Image: FLUX 3 Klein", lambda: W.gerar_simples("flux3", TEXTO, "", 1, 1344, 768)),
    ("image_flux1_dev", "Image: FLUX.1 dev", lambda: W.gerar_simples("flux1dev", TEXTO, "", 1, 1344, 768)),
    ("image_flux1_krea_dev", "Image: FLUX.1 Krea dev", lambda: W.gerar_simples("flux1krea", TEXTO, "", 1, 1344, 768)),
    ("image_flux2_dev", "Image: FLUX.2 dev (32B)", lambda: W.gerar_simples("flux2dev", TEXTO, "", 1, 1344, 768)),
    ("image_hidream_i1_fast", "Image: HiDream I1 Fast", lambda: W.gerar_simples("hidream", TEXTO, "", 1, 1344, 768)),
    ("image_chroma1_hd", "Image: Chroma1 HD", lambda: W.gerar_simples("chroma", TEXTO, "", 1, 1344, 768)),
    ("image_sd35_large", "Image: SD 3.5 Large", lambda: W.gerar_simples("sd35l", TEXTO, "", 1, 1344, 768)),
    ("image_kandinsky5", "Image: Kandinsky 5 Image", lambda: W.gerar_simples("kandinsky5i", TEXTO, "", 1, 1344, 768)),
    ("image_sdxl_light", "Image (light): SDXL, for 6-8 GB cards", lambda: W.gerar_simples("sdxl", TEXTO, "", 1, 1344, 768)),
    ("video_ltx25_text_or_image", "Video: LTX 2.5 text/image to video with sound (two-stage)",
     lambda: W.gerar_video_ltx(TEXTO, 1, 1280, 704, 5, imagem="start_image.png")),
    ("video_ltx25_first_last", "Video: LTX 2.5 first & last frame",
     lambda: W.gerar_video_ltx_flf(TEXTO, 1, "first.png", "last.png", 1280, 704, 5)),
    ("video_ltx25_references", "Video: LTX 2.5 references (MSR), up to 4 people/objects + background",
     lambda: W.gerar_video_ltx_msr("@image1 and @image2 walk together. " + TEXTO, 1, ["ref1.png", "ref2.png"], fundo="background.png")),
    ("video_ltx25_keyframes", "Video: LTX 2.5 keyframes, images pinned to chosen frames",
     lambda: W.chaves_ltx(TEXTO, [("key1.png", 1), ("key2.png", 97), ("key3.png", 193)], 193, 1280, 704)),
    ("video_ltx25_ingredients", "Video: LTX 2.5 ingredients (reference sheet)",
     lambda: W.ingredientes_ltx("reference_sheet.png", "the man from the left of the reference sheet walks along the street on the right of the sheet", 121, 1024, 576)),
    ("video_ltx23_image", "Video: LTX 2.3 image / first & last frame",
     lambda: ltx23.grafo(TEXTO, 1, 1280, 704, 5, "first.png", ultimo="last.png")),
    ("video_light_ltxv2b", "Video (light): LTX-Video 2B distilled, 6-8 GB cards",
     lambda: videos_leves.grafo("ltxv2b", TEXTO, 1, 768, 512, 5, imagem="start_image.png")),
    ("video_light_wan22_5b", "Video (light): Wan 2.2 TI2V 5B",
     lambda: videos_leves.grafo("wan22_5b", TEXTO, 1, 1280, 704, 5)),
    ("video_wan22_14b_text_or_image", "Video: Wan 2.2 14B, 4 steps (lightx2v), text or image to video",
     lambda: videos_leves.grafo("wan22_14b", TEXTO, 1, 832, 480, 5, imagem="start_image.png")),
    ("video_wan22_14b_first_last", "Video: Wan 2.2 14B first & last frame",
     lambda: videos_leves.grafo("wan22_14b", TEXTO, 1, 832, 480, 5, imagem="first.png", imagem_final="last.png")),
    ("video_hunyuan15", "Video: HunyuanVideo 1.5 720p, text or image to video",
     lambda: videos_leves.grafo("hunyuan15", TEXTO, 1, 1280, 720, 5, imagem="start_image.png")),
    ("video_kandinsky5", "Video: Kandinsky 5 Lite, text to video",
     lambda: videos_leves.grafo("kandinsky5", TEXTO, 1, 768, 512, 5)),
    ("video_fasth3", "Video: FastH3 (MiniMax H3 distilled, 8 steps)",
     lambda: W.gerar_video_fasth3(TEXTO, 1, 1280, 704, 5, imagem="start_image.png")),
    ("lipsync_ltx23", "Lip Sync: a portrait and a voice track become a talking video (LTX 2.3)",
     lambda: avatar.grafo_ltx23(SimpleNamespace(prompt="", referencias=["portrait.png"], referencia_avatar="voice.wav",
                                                audio_avatar="voice.wav", prompt_avatar=""), 1, 8.0, "lipsync")),
    ("genjutsu_wan_animate2", "Genjutsu: Wan Animate 2, the photo performs the video's motion",
     lambda: genjutsu.grafo_wan_animate2("input_video.mp4", "photo.png", "", 81, 832, 480, 1, "genjutsu")),
    ("tool_depth_map", "Apps: video to depth map (Video Depth Anything), optional EXR frames",
     lambda: W.mapa_profundidade("input_video.mp4", 121, exr_pasta="depth_exr")),
] + [(f"vfx_{nome}", f"VFX app: {titulo} (LTX IC-LoRA)", (lambda id=id: efeito(id)))
     for id, (nome, titulo) in {
         "noite": ("day_to_night", "Day to Night"), "limpar": ("remove_people", "Remove people"),
         "agua": ("add_water", "Add water"), "trocar": ("swap_character", "Swap character"),
         "expandir": ("expand_frame", "Expand frame"), "cor": ("colorize", "Colorize"),
         "nitidez": ("unblur", "Unblur"), "compressao": ("remove_compression", "Remove compression"),
         "detalhe": ("refine_details", "Refine details"), "restaurar": ("restore", "Restore"),
         "profundidade": ("follow_depth", "Follow depth"), "maquete": ("render_to_video", "3D render to video"),
     }.items() if id in FX["efeitos"]]


def main():
    SAIDA.mkdir(exist_ok=True)
    linhas, falhas = [], []
    for nome, descricao, construir in FLUXOS:
        try:
            grafo = construir()
        except Exception as e:  # um construtor quebrado nao impede os outros
            falhas.append(f"{nome}: {e!r}")
            continue
        (SAIDA / f"{nome}.json").write_text(json.dumps(grafo, indent=2, ensure_ascii=False), encoding="utf-8")
        linhas.append(f"| `{nome}.json` | {descricao} |")
    (SAIDA / "README.md").write_text(
        "# ComfyUI workflows\n\n"
        "The graphs EasyComfee sends to ComfyUI, exported in ComfyUI's API format by\n"
        "`scripts/exportar_workflows.py` from the same Python builders the app uses\n"
        "(`backend/workflows.py`, `videos_leves.py`, `ltx23.py`, `avatar.py`, `genjutsu.py`).\n\n"
        "Drag a file onto the ComfyUI canvas to open it. Input file names (`input_video.mp4`,\n"
        "`start_image.png`…) are placeholders: put your own files in ComfyUI's `input` folder\n"
        "and pick them in the loader nodes. Models: install the matching package in the app's\n"
        "Config Models, or see the main README for the download links.\n\n"
        "| File | What it does |\n|---|---|\n" + "\n".join(linhas) + "\n",
        encoding="utf-8")
    print(f"{len(linhas)} workflows em {SAIDA}")
    for f in falhas:
        print("FALHOU", f)


if __name__ == "__main__":
    main()
