"""A familia de modelo de cada LoRA, para o menu mostrar so as que servem.

Le so o cabecalho do .safetensors (8 bytes + JSON com nomes e formatos das camadas),
nunca os pesos. Primeiro o que o autor gravou nos metadados; se nao ha, a estrutura:
os nomes das camadas e a largura do modelo (a entrada das matrizes lora_A/lora_down).
Feito em 16/11/2026 a partir das LoRAs reais de um PC de teste (Krea 2, Flux 2 Klein,
Z-Image, Qwen, MOSS, LTX 2.3/2.5, MiniMax H3, Wan 2.2) e dos formatos kohya/diffusers
comuns de SD 1.5, SDXL e FLUX.1. Familia None = nao reconhecida (a tela mostra a parte).
"""
import json
import pathlib
import re
import struct

import config

# Familia que cada modelo local do app aceita. Chave: id do modelo de imagem
# (presets.SIMPLE) ou "video:<modelo_video>".
FAMILIAS_DO_MODELO = {
    "krea": {"krea2"}, "kroma": {"krea2"}, "kroma_foto": {"krea2"},
    "qwen21": {"qwen21"}, "klein": {"flux2_klein9"}, "flux3": {"flux3"},
    "moss": {"moss"}, "fibo2": {"fibo"}, "zimage": {"zimage"}, "mage": {"mage"},
    "flux1s": {"flux1"}, "flux1dev": {"flux1"}, "flux1krea": {"flux1"},
    "flux2dev": {"flux2dev"}, "hidream": {"hidream"}, "chroma": {"chroma", "flux1"},
    "sd35m": {"sd35m"}, "sd35l": {"sd35l"}, "sdxl": {"sdxl"}, "sd15": {"sd15"},
    "kandinsky5i": {"kandinsky5"},
    "video:ltx": {"ltx22b"}, "video:ltx23": {"ltx22b"}, "video:minimax": {"minimax_h3"},
    "video:ltxv2b": {"ltx2b"}, "video:wan22_5b": {"wan5b"}, "video:wan21_13b": {"wan13b"},
    "video:wan22_14b": {"wan14b"}, "video:hunyuan15": {"hunyuan15"}, "video:kandinsky5": {"kandinsky5v"},
}

# Metadados gravados pelos treinadores (ss_base_model_version, modelspec.architecture,
# base_model). Ordem importa: o mais especifico primeiro.
_META = [
    (r"flux.?2.?klein.?9|klein.?9b", "flux2_klein9"), (r"flux.?3", "flux3"),
    (r"flux.?2.?dev|flux2(?!.?klein)", "flux2dev"), (r"krea.?2|kroma", "krea2"),
    (r"z.?image|zimage", "zimage"), (r"qwen.?image.?2\.1", "qwen21"), (r"moss", "moss"),
    (r"minimax.?h3", "minimax_h3"), (r"chroma", "chroma"), (r"hidream", "hidream"),
    (r"sd.?3\.?5.?large|sd3.?large", "sd35l"), (r"sd.?3\.?5.?medium|sd3.?medium", "sd35m"),
    (r"sdxl|stable-diffusion-xl|sd_xl", "sdxl"), (r"sd.?v?1[._-]?5|sd_v1|stable-diffusion-v1", "sd15"),
    (r"flux.?1|flux\.1|flux-dev|flux-schnell", "flux1"), (r"yue", "texto"),
]


def _cabecalho(arquivo: pathlib.Path) -> dict | None:
    try:
        with open(arquivo, "rb") as h:
            n = struct.unpack("<Q", h.read(8))[0]
            if not 0 < n < 64 * 1024 * 1024:  # cabecalho absurdo: nao e safetensors
                return None
            return json.loads(h.read(n))
    except (OSError, ValueError, struct.error):
        return None


def _largura(cab: dict, trecho: str, sem: str = "") -> int:
    """Entrada (largura do modelo) da primeira matriz lora_A/lora_down cujo nome tem `trecho`
    (e nao tem `sem`)."""
    for k, v in cab.items():
        if trecho in k and not (sem and sem in k) and ("lora_A" in k or "lora_down" in k) and isinstance(v, dict):
            forma = v.get("shape") or []
            if len(forma) >= 2:
                return int(forma[1])
    return 0


def familia(cab: dict) -> str | None:
    meta = cab.get("__metadata__") or {}
    pista = " ".join(str(meta.get(c, "")) for c in
                     ("ss_base_model_version", "modelspec.architecture", "base_model")).lower()
    for padrao, fam in _META:
        if pista.strip() and re.search(padrao, pista):
            return fam
    chaves = [k for k in cab if k != "__metadata__"]
    if not chaves or not any("lora" in k for k in chaves):
        # Sem matrizes de LoRA (um embedding solto, por exemplo) nao entra no modelo.
        return "nenhuma" if chaves and not any(".alpha" in k or "lora" in k for k in chaves) else None
    tudo = "\n".join(chaves)
    if re.search(r"^text_encoders?\.", tudo, re.M):
        return "texto"
    # Formato kohya (lora_unet_...): SD 1.5, SDXL e FLUX.1.
    if "lora_unet_" in tudo:
        if "lora_unet_double_blocks" in tudo or "lora_unet_single_blocks" in tudo:
            return "flux1"
        if "lora_te2_" in tudo:
            return "sdxl"
        texto = _largura(cab, "attn2_to_k")
        return {768: "sd15", 2048: "sdxl"}.get(texto)
    if "attn2.to_k" in tudo and ("down_blocks" in tudo or "input_blocks" in tudo):
        return {768: "sd15", 2048: "sdxl"}.get(_largura(cab, "attn2.to_k"))
    if "joint_blocks" in tudo:
        return {1536: "sd35m", 2432: "sd35l"}.get(_largura(cab, "attn.qkv"))
    if "double_stream_blocks" in tudo:
        return "hidream"
    if "double_blocks" in tudo and "img_attn_" in tudo:
        return "hunyuan15"
    if "double_blocks" in tudo:
        d = _largura(cab, "img_attn.qkv")
        if d == 4096:
            return "flux2_klein9"
        if d == 6144:
            return "flux2dev"
        return "flux1" if d == 3072 else None
    if "single_transformer_blocks" in tudo and "add_k_proj" in tudo:
        return "flux1"  # FLUX.1 no formato diffusers
    if "transformer_blocks" in tudo and ("attn1." in tudo or "audio_attn" in tudo or "adaln_single" in tudo):
        # A largura do VIDEO: as LoRAs de som do LTX 2.3 22B tem audio_attn1 com 2048.
        d = _largura(cab, "attn1.to_q", sem="audio") or _largura(cab, "attn1.to_k", sem="audio")
        return {4096: "ltx22b", 2048: "ltx2b"}.get(d, "ltx22b" if not d else None)
    if "add_k_proj" in tudo:
        return "qwen_edit"  # Qwen Image Edit 2509/2511 (o app nao tem esse modelo local)
    if "transformer_blocks" in tudo and "modulation" in tudo:
        return "qwen21"
    if re.search(r"layers\.\d+\.attention\.", tudo):
        return "zimage" if _largura(cab, "attention.to_q") in (3840, 0) else None
    if re.search(r"blocks\.\d+\.attn\.wq", tudo):
        return "krea2"
    if re.search(r"blocks\.\d+\.attn\.qkv_proj", tudo):
        return "minimax_h3"
    if re.search(r"layers\.\d+\.proj\.ffn", tudo):
        return "moss"
    if "cross_attn" in tudo and "blocks." in tudo:
        return {5120: "wan14b", 3072: "wan5b", 1536: "wan13b"}.get(_largura(cab, "self_attn.q"))
    return None


# Campos onde os treinadores e sites gravam a palavra de ativacao (CivitAI, kohya, ai-toolkit...).
_CAMPOS_GATILHO = ("modelspec.trigger_phrase", "trigger_phrase", "trigger_words", "trigger_word",
                   "trigger", "activation_text", "ss_trigger_words")


def gatilhos(cab: dict, maximo: int = 3) -> list[str]:
    """Palavras de ativacao da LoRA, pelos metadados. Primeiro um campo explicito; se nao ha,
    as legendas de treino mais frequentes (ss_tag_frequency do kohya/ai-toolkit), onde a
    palavra de ativacao costuma ser a mais repetida. Vazio quando nada foi gravado."""
    meta = cab.get("__metadata__") or {}
    achadas: list[str] = []

    def por(t: str) -> None:
        t = " ".join(str(t).split()).strip(" ,.")
        if t and len(t) <= 60 and t.lower() not in (x.lower() for x in achadas):
            achadas.append(t)

    for campo in _CAMPOS_GATILHO:
        valor = meta.get(campo)
        if not valor:
            continue
        try:  # alguns gravam uma lista em JSON
            lido = json.loads(valor)
        except ValueError:
            lido = valor
        for t in (lido if isinstance(lido, list) else re.split(r"[,;\n]", str(lido))):
            por(t)
    if not achadas and meta.get("ss_tag_frequency"):
        try:
            freq = json.loads(meta["ss_tag_frequency"])
        except ValueError:
            freq = {}
        contagem: dict[str, int] = {}
        for grupo in freq.values() if isinstance(freq, dict) else []:
            for tag, n in (grupo.items() if isinstance(grupo, dict) else []):
                contagem[tag] = contagem.get(tag, 0) + int(n or 0)
        for tag, _ in sorted(contagem.items(), key=lambda x: -x[1])[:maximo]:
            por(tag)
    return achadas[:maximo]


_CACHE: dict[str, tuple[float, str | None, list[str]]] = {}


def _ler(nome_comfy: str) -> tuple[str | None, list[str]]:
    """Familia e palavras de ativacao da LoRA `nome_comfy` (como o ComfyUI lista). Familia
    None se o arquivo nao esta na pasta de modelos que conhecemos (pastas extras do
    extra_model_paths.yaml) ou nao foi reconhecido. Guarda enquanto o arquivo nao muda."""
    arquivo = config.MODELOS_DIR / "loras" / nome_comfy.replace("\\", "/")
    try:
        quando = arquivo.stat().st_mtime
    except OSError:
        return None, []
    guardado = _CACHE.get(nome_comfy)
    if guardado and guardado[0] == quando:
        return guardado[1], guardado[2]
    cab = _cabecalho(arquivo)
    fam, gat = (familia(cab), gatilhos(cab)) if cab else (None, [])
    _CACHE[nome_comfy] = (quando, fam, gat)
    return fam, gat


def familia_do_arquivo(nome_comfy: str) -> str | None:
    return _ler(nome_comfy)[0]


def gatilhos_do_arquivo(nome_comfy: str) -> list[str]:
    return _ler(nome_comfy)[1]
