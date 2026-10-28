"""Geração local de música pelos nós nativos do ComfyUI."""
import config
import pathlib
import hashlib
import asyncio
import io
from nomes_audio import nome_audio
import soundfile as sf
import httpx
import finalizacao_musica
import comfy
import json

MODELOS = {
    "minimax-music3": {"rotulo": "MiniMax Music 3", "letra": True, "maximo": 300,
        "nos": ["UNETLoader", "CLIPLoader", "VAELoader", "MiniMaxMusic3TextEncode", "EmptyMiniMaxMusic3LatentAudio", "ConditioningZeroOut"],
        "pesos": {"unet": ("UNETLoader", "unet_name", "minimax_music3_dit_fp16.safetensors"), "clip": ("CLIPLoader", "clip_name", "minimax_music3_text_encoder_pruned_int8_convrot.safetensors"), "vae": ("VAELoader", "vae_name", "minimax_music3_dav.safetensors")}},
    "stable-audio3": {"rotulo": "Stable Audio 3", "letra": False, "maximo": 380,
        "nos": ["CheckpointLoaderSimple", "CLIPLoader", "CLIPTextEncode", "EmptyLatentAudio"],
        "pesos": {"checkpoint": ("CheckpointLoaderSimple", "ckpt_name", "stable_audio_3_medium_base.safetensors"), "clip": ("CLIPLoader", "clip_name", "t5gemma_b_b_ul2.safetensors")}},
    "ace-step15": {"rotulo": "ACE-Step 1.5 Turbo", "letra": True, "maximo": 600,
        "nos": ["UNETLoader", "DualCLIPLoader", "VAELoader", "TextEncodeAceStepAudio1.5", "EmptyAceStep1.5LatentAudio", "ModelSamplingAuraFlow", "ConditioningZeroOut"],
        "pesos": {"unet": ("UNETLoader", "unet_name", "acestep_v1.5_turbo.safetensors"), "clip1": ("DualCLIPLoader", "clip_name1", "qwen_0.6b_ace15.safetensors"), "clip2": ("DualCLIPLoader", "clip_name2", "qwen_1.7b_ace15.safetensors"), "vae": ("VAELoader", "vae_name", "ace_1.5_vae.safetensors")}},
    # YuE2 pelo modelo pronto "1 . YuE2 . Song" do Plenio (v1.0.2), no SEGUNDO
    # motor (v0.41, onde o Plenio esta instalado): o Gemma 4 escreve titulo,
    # estilo e letra, o YuE2 planeja a partitura e canta, o Plenio masteriza a
    # -14 LUFS e exporta (FLAC, PDF da partitura, registro .plenio.json).
    # MEDIDO em 20/10/2026: 1:27 de musica em 104 s. Licenca do YuE2: CC
    # BY-NC 4.0 (uso NAO comercial).
    "yue2": {"rotulo": "YuE2 (Plenio)", "letra": False, "maximo": 360, "plenio": True,
        "nos": ["YuE2GenerateMusic", "PlenioSongBrief", "PlenioLoudness", "PlenioExportRelease"],
        "pesos": {"checkpoint": ("CheckpointLoaderSimple", "ckpt_name", "yue2_3b_int8_convrot.safetensors")},
        # Modelo pronto, Song Sheets (letra, partitura), ordem das paradas e
        # a saida masterizada que vira SaveAudio.
        "grafo": "plenio_yue2_song.json", "folhas": {"letra": "7", "partitura": "13"},
        "ordem": ["letra", "partitura"], "saida": ("20", ["19:402", 0])},
    # Cover pelo modelo pronto "2 . YuE2 . Cover": o SheetSage2 transcreve a
    # melodia e os acordes da gravacao (folha 10), depois vem a letra (19):
    # a original transcrita pelo faster-whisper, uma nova, ou instrumental.
    # Licenca: YuE2, SheetSage2 e o adaptador sao CC BY-NC 4.0; e a composicao
    # original tem dono — publicar exige autorizacao dos titulares.
    "yue2-cover": {"rotulo": "YuE2 Cover (Plenio)", "letra": False, "maximo": 600, "plenio": True,
        "cover": True,
        "nos": ["YuE2GenerateMusic", "PlenioCoverBrief", "PlenioTranscribeScore", "PlenioLoudness"],
        "pesos": {"checkpoint": ("CheckpointLoaderSimple", "ckpt_name", "yue2_3b_int8_convrot.safetensors"),
                  "partitura": ("AudioEncoderLoader", "audio_encoder_name", "sheetsage2_bf16.safetensors"),
                  "adaptador": ("LoraLoader", "lora_name", "ar_lora_inst_v3abc_comfyui.safetensors")},
        "grafo": "plenio_yue2_cover.json", "folhas": {"letra": "19", "partitura": "10"},
        "ordem": ["partitura", "letra"], "saida": ("29", ["28:402", 0])},
}

GRAFOS = pathlib.Path(__file__).parent / "grafos"
# Duracoes que o pedido do Plenio aceita, em segundos aproximados.
DURACOES_YUE2 = [(60, "very short (about 1:00)"), (90, "short (about 1:30)"), (120, "about 2:00"),
                 (150, "about 2:30"), (180, "standard (about 3:00)"), (210, "about 3:30"),
                 (240, "about 4:00"), (270, "long (about 4:30)"), (300, "about 5:00"),
                 (360, "very long (about 6:00)")]
IDIOMAS_YUE2 = {"pt": "Portuguese", "en": "English", "es": "Spanish", "de": "German", "it": "Italian",
                "fr": "French", "ja": "Japanese", "zh": "Chinese", "ko": "Korean"}
VOZES_YUE2 = {"feminino": "female voice", "masculino": "male voice"}

TONALIDADES = {f"{nota} {modo}" for modo in ("major", "minor")
               for nota in ("C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B")}
GENEROS_VOCAIS = {"feminino": "Female lead vocal.", "masculino": "Male lead vocal."}

def nome_musica(p):
    return nome_audio((p.projeto_musica, p.titulo_musica), 'musica_' + p.modelo_musica)

def resolver(info, ident):
    cfg = MODELOS[ident]
    faltam = [n for n in cfg["nos"] + ["KSampler", "VAEDecodeAudio", "SaveAudio"] if n not in info]
    pesos = {}
    for chave, (no, campo, arquivo) in cfg["pesos"].items():
        entrada = info.get(no, {}).get("input", {}).get("required", {}).get(campo, [[]])
        nomes = entrada[0] if isinstance(entrada[0], list) else entrada[1].get("options", [])
        encontrado = next((n for n in nomes if n.replace("\\", "/").split("/")[-1] == arquivo), None)
        if encontrado: pesos[chave] = encontrado
        else: faltam.append(arquivo)
    return {"id": ident, "rotulo": cfg["rotulo"], "letra": cfg["letra"], "maximo": cfg["maximo"],
            "disponivel": not faltam, "motivo": "Missing: " + ", ".join(faltam) if faltam else "", "pesos": pesos}

async def catalogo():
    try:
        # Na Comfy Cloud confere contra a lista de la (os tres abertos estao la).
        info = await comfy.info_nos()
        lista = [resolver(info, ident) for ident in MODELOS if not MODELOS[ident].get("plenio")]
        if comfy.na_nuvem():
            return lista
    except Exception as e:
        lista = [{"id": k, "rotulo": v["rotulo"], "letra": v["letra"], "maximo": v["maximo"], "disponivel": False, "motivo": comfy.motivo_sem_info(e), "pesos": {}} for k,v in MODELOS.items() if not v.get("plenio")]
    lista = lista + [await _catalogo_plenio(k) for k, v in MODELOS.items() if v.get("plenio")]
    return lista


_INFO_NUVEM = {"em": 0.0, "info": None}


async def onde_roda() -> dict:
    """Para o menu da aba (grupos Local / Comfy Cloud): em que lado cada modelo
    existe, olhando os dois, seja qual for o motor escolhido agora."""
    import time
    import chaves
    import nuvem
    lados = {}
    try:
        local = await comfy.info_nos(comfy.BASE_PRINCIPAL)
    except Exception:
        local = None
    if chaves.chave() and (time.time() - _INFO_NUVEM["em"] > 3600 or _INFO_NUVEM["info"] is None):
        try:
            async with nuvem._cliente() as c:
                r = await c.get("/object_info"); r.raise_for_status()
            _INFO_NUVEM.update(em=time.time(), info=r.json())
        except Exception:
            pass
    na_nuvem = _INFO_NUVEM["info"] if chaves.chave() else None
    for ident, cfg in MODELOS.items():
        if cfg.get("plenio"):
            # O Plenio mora no segundo motor desta maquina; nao existe na nuvem.
            lados[ident] = {"local": (await _catalogo_plenio(ident))["disponivel"], "nuvem": False}
        else:
            lados[ident] = {"local": bool(local) and resolver(local, ident)["disponivel"],
                            "nuvem": bool(na_nuvem) and resolver(na_nuvem, ident)["disponivel"]}
    return lados


def _plenio_no_disco() -> bool | None:
    """Se a pasta dos nos do Plenio existe no custom_nodes do segundo motor
    (None: a pasta do ComfyUI nao esta no config, nao da para saber)."""
    import config
    pasta = config.COMFY_DIR_FLUX3 and config.COMFY_DIR_FLUX3 / "custom_nodes"
    if not pasta or not pasta.is_dir():
        return None
    return any("plenio" in d.name.lower() for d in pasta.iterdir() if d.is_dir())


async def _catalogo_plenio(ident):
    """O Plenio mora no segundo motor, que sobe sob demanda: desligado, o
    modelo segue disponivel (sobe na hora de gerar), sem a lista de estilos."""
    import motor_flux3
    cfg = MODELOS[ident]
    base = {"id": ident, "rotulo": cfg["rotulo"], "letra": cfg["letra"], "maximo": cfg["maximo"],
            "plenio": True, "estilos": [], "cover": bool(cfg.get("cover")), "ordem": cfg["ordem"]}
    if not motor_flux3.instalado():
        return base | {"disponivel": False, "motivo": "The second engine (ComfyUI v0.41) is not installed.", "pesos": {}}
    try:
        info = await comfy.info_nos(comfy.BASE_FLUX3)
    except Exception as e:
        # Motor desligado (sobe na hora de gerar) ou lento: sem a lista dele,
        # o disco diz se os nos do Plenio estao instalados. Antes era sempre
        # "disponivel", e o YuE2 aparecia como "Your GPU" sem o Plenio.
        no_disco = _plenio_no_disco()
        if no_disco:
            return base | {"disponivel": True, "motivo": "", "pesos": {}}
        return base | {"disponivel": False, "pesos": {},
                       "motivo": "The Plenio nodes are not installed." if no_disco is False
                       else comfy.motivo_sem_info(e)}
    res = resolver(info, ident)
    brief = info.get("PlenioSongBrief", {}).get("input", {}).get("required", {}).get("template", [None, {}])
    return base | res | {"estilos": brief[1].get("options", []) if len(brief) > 1 else []}


# Revisao em etapas. Cada modelo do Plenio tem duas Song Sheets (ver
# "folhas"): a de letra (titulo, estilo, letra) e a de partitura (ABC). Cada
# uma aceita review "stop for review" ou "continue", e documentos "manual"
# com o texto do usuario (a entrada de cima nem e avaliada). Rodadas do MESMO
# grafo, com a mesma seed, na ordem do modelo ("ordem"): a folha da etapa
# para e devolve os rascunhos; as anteriores seguem com o que foi aprovado;
# em "gerar" todas seguem e a musica sai. Musica: letra -> partitura; cover:
# partitura (transcrita) -> letra. O cache do ComfyUI evita refazer o resto.
DOCS = {"letra": ("title", "style", "lyrics"), "partitura": ("score",)}
VOZES_COVER = {"original": "original lyrics", "nova": "new lyrics", "instrumental": "instrumental"}


def _estado_folha(docs):
    manuais = {k: {"state": "manual", "text": v} for k, v in docs.items() if isinstance(v, str) and v.strip()}
    return json.dumps({"schema": "plenio.sheet_state/1", "docs": manuais}, ensure_ascii=False) if manuais else ""


def revisao_do_historico(outputs, etapa, modelo="yue2"):
    """Os rascunhos devolvidos pela Song Sheet que parou."""
    no = MODELOS[modelo]["folhas"][etapa]
    folhas = (outputs.get(no) or {}).get("plenio_sheet") or []
    if not folhas:
        raise RuntimeError("A Song Sheet não devolveu os rascunhos.")
    f = folhas[0]
    docs = {k: (d.get("text") or d.get("upstream") or "") for k, d in (f.get("docs") or {}).items()}
    erros = [x.get("message") or str(x) for x in f.get("findings") or [] if x.get("severity") == "error"]
    return {"etapa": etapa, "docs": docs, "erros": erros,
            "segundos": f.get("score_seconds"), "status": f.get("status"),
            # o payload inteiro, para o editor completo do Plenio abrir igual
            "folha": f}


def grafo_yue2(p, seed, estilo="none", etapa="direto", docs=None):
    """O modelo pronto do Plenio (musica ou cover), com o pedido da tela. Em
    "direto" as Song Sheets seguem o modo "...every run" e nao param."""
    docs = docs or {}
    cfg = MODELOS[p.modelo_musica]
    g = json.loads((GRAFOS / cfg["grafo"]).read_text(encoding="utf-8"))
    if etapa != "direto":
        ordem = cfg["ordem"]
        ate = len(ordem) if etapa == "gerar" else ordem.index(etapa)
        for i, nome in enumerate(ordem):
            folha = g[cfg["folhas"][nome]]["inputs"]
            if i < ate:
                folha.update(review="continue",
                             sheet_state=_estado_folha({k: docs.get(k) for k in DOCS[nome]}))
            else:
                folha.update(review="stop for review", sheet_state="")
    if cfg.get("cover"):
        _pedido_cover(g, p, estilo)
    else:
        _pedido_musica(g, p, estilo)
    for no in g.values():
        if no["class_type"] == "PlenioSeed":
            no["inputs"].update(seed=seed, keep_seed=True)
    # A previa vira o arquivo que o app registra na galeria (ja masterizado).
    no, origem = cfg["saida"]
    g[no] = {"class_type": "SaveAudio", "inputs": {"audio": origem,
             "filename_prefix": f"editor/{nome_musica(p)}"}}
    return g


def _pedido_musica(g, p, estilo):
    b = g["2"]["inputs"]
    tamanho = min(DURACOES_YUE2, key=lambda d: abs(d[0] - p.duracao_musica))[1]
    b.update({"mode": "new song every run", "template": estilo or "none", "description": p.prompt,
              "genre": "", "mood": "", "tempo": "", "length": tamanho, "key": "", "meter": ""})
    for k in [k for k in b if k.startswith("vocals.")]:
        del b[k]
    if p.vocal_musica:
        b.update({"vocals": "sung", "vocals.language": IDIOMAS_YUE2.get(p.idioma_musica, ""),
                  "vocals.voice": VOZES_YUE2.get(p.genero_vocal_musica, ""), "vocals.theme": ""})
    else:
        b.update({"vocals": "instrumental", "vocals.melody": "instrument plays the lead",
                  "vocals.lead_instrument": ""})


def _pedido_cover(g, p, estilo):
    g["2"]["inputs"]["audio"] = p.referencia_musica
    # A previa da conferencia de voz nao interessa ao app (so a musica final).
    g.pop("23", None)
    b = g["4"]["inputs"]
    b.update({"mode": "new cover every run", "template": estilo or "none", "description": p.prompt,
              "genre": "", "mood": "", "title": p.titulo_musica or "",
              "harmony": "keep original chords" if p.harmonia_cover == "manter" else "new accompaniment",
              "arrangement": "off"})
    for k in [k for k in b if k.startswith("vocals.")]:
        del b[k]
    voz = VOZES_YUE2.get(p.genero_vocal_musica, "")
    if p.voz_cover == "original":
        b.update({"vocals": "original lyrics", "vocals.language": "auto", "vocals.voice": voz})
    elif p.voz_cover == "nova":
        b.update({"vocals": "new lyrics", "vocals.language": IDIOMAS_YUE2.get(p.idioma_musica, "English"),
                  "vocals.voice": voz, "vocals.theme": p.tema_cover, "vocals.phrasing_reference": False})
    else:
        b.update({"vocals": "instrumental", "vocals.melody": "instrument plays the lead",
                  "vocals.lead_instrument": ""})


def configuracao_geracao(p):
    dur=p.duracao_musica
    descricao=p.prompt
    if p.modelo_musica == "ace-step15" and p.vocal_musica and p.genero_vocal_musica in GENEROS_VOCAIS:
        descricao += "\n" + GENEROS_VOCAIS[p.genero_vocal_musica]
    if p.encerramento_musica != "original" and not p.vocal_musica and not p.referencia_musica:
        dur=min(MODELOS[p.modelo_musica]["maximo"], dur+p.margem_musica)
        descricao += "\nFinish with a brief outro and a resolved ending, allowing the instruments to decay into silence."
    return descricao, dur


def grafo(p, seed, pesos):
    def node(tipo, **inputs): return {"class_type": tipo, "inputs": inputs}
    ident=p.modelo_musica
    descricao,dur=configuracao_geracao(p)
    g={}
    if ident == "stable-audio3":
        g["checkpoint_musica"]=node("CheckpointLoaderSimple", ckpt_name=pesos["checkpoint"])
        g["clip"]=node("CLIPLoader", clip_name=pesos["clip"], type="stable_audio", device="default")
        g["pos"]=node("CLIPTextEncode", clip=["clip",0], text=descricao)
        g["neg"]=node("CLIPTextEncode", clip=["clip",0], text="")
        g["latente"]=node("EmptyLatentAudio", seconds=dur, batch_size=1)
        model=["checkpoint_musica",0]; vae=["checkpoint_musica",2]; pos=["pos",0]
        steps,cfg,sampler=50,7.0,"lcm"
    else:
        g["unet"]=node("UNETLoader", unet_name=pesos["unet"], weight_dtype="default")
        g["vae"]=node("VAELoader", vae_name=pesos["vae"])
        vae=["vae",0];pos=["cond_musica",0]
        letra=p.letra_musica if p.vocal_musica else ""
        if ident == "minimax-music3":
            if not p.vocal_musica:
                # Instrumental ainda precisa de estrutura no canal lyrics.
                # As tags orientam a composição, sem palavras para cantar.
                letra="[Intro]\n[Instrumental]\n[Instrumental]\n[Solo]\n[Instrumental]\n[Bridge]\n[Instrumental]\n[Outro]"
            g["clip"]=node("CLIPLoader", clip_name=pesos["clip"], type="minimax", device="default")
            g["cond_musica"]=node("MiniMaxMusic3TextEncode", clip=["clip",0], caption=descricao, lyrics=letra, seed=seed, max_duration=dur, cfg_scale=1.7, top_k=50)
            # O encoder pode terminar antes do máximo. Não gerar uma cauda
            # sem condicionamento: seguir a duração real, como no template oficial.
            g["latente"]=node("EmptyMiniMaxMusic3LatentAudio", seconds=["cond_musica",1], batch_size=1)
            model=["unet",0];steps,cfg,sampler=30,1.7,"euler"
        elif ident == "ace-step15":
            g["clip"]=node("DualCLIPLoader", clip_name1=pesos["clip1"], clip_name2=pesos["clip2"], type="ace", device="default")
            g["cond_musica"]=node("TextEncodeAceStepAudio1.5", clip=["clip",0], tags=descricao, lyrics=letra, seed=seed, bpm=p.bpm_musica, duration=dur, timesignature="4", language=p.idioma_musica, keyscale=p.tonalidade_musica, generate_audio_codes=not bool(p.referencia_musica), cfg_scale=2.0, temperature=0.85, top_p=0.9, top_k=0, min_p=0.0)
            g["latente"]=node("EmptyAceStep1.5LatentAudio", seconds=dur, batch_size=1)
            g["modelo_musica"]=node("ModelSamplingAuraFlow", model=["unet",0], shift=3.0)
            model=["modelo_musica",0];steps,cfg,sampler=8,1.0,"euler"
            if p.referencia_musica:
                g["guia"]=node("LoadAudio", audio=p.referencia_musica)
                g["guia_latente"]=node("VAEEncodeAudio", audio=["guia",0], vae=vae)
                g["cond_guia"]=node("ReferenceTimbreAudio", conditioning=pos, latent=["guia_latente",0])
                pos=["cond_guia",0]
        else: raise ValueError("Modelo de música desconhecido")
        g["neg"]=node("ConditioningZeroOut", conditioning=pos)
    g["amostra_musica"]=node("KSampler", model=model, seed=seed, steps=steps, cfg=cfg, sampler_name=sampler, scheduler="simple", positive=pos, negative=["neg",0], latent_image=["latente",0], denoise=1.0)
    if ident == 'ace-step15' and p.referencia_musica:
        g["amostra_musica"]["inputs"].update(latent_image=["guia_latente",0], denoise=p.transformacao_musica)
    g["audio_musica"]=node("VAEDecodeAudio", samples=["amostra_musica",0], vae=vae)
    g["salva"]=node("SaveAudio", audio=["audio_musica",0], filename_prefix=f"editor/{nome_musica(p)}")
    return g


FINALIZACOES = pathlib.Path(__file__).parent / "finalizacoes_musica"

async def duracao_referencia(nome):
    # Do disco, sem depender de motor (em 21/10/2026 o principal ficou fora
    # do ar por instantes e o cover era recusado como "guia invalida").
    import os
    local = config.COMFY_ENTRADA / nome
    dados = local.read_bytes() if local.is_file() else await comfy.imagem(nome, "", "input")
    info=await asyncio.to_thread(sf.info, io.BytesIO(dados))
    return info.duration

async def finalizar_saida(p, saida):
    if MODELOS.get(p.modelo_musica, {}).get("plenio"):
        # O Plenio ja masterizou e encerrou a musica: nada a cortar.
        return [dict(saida, musica={"versao": "Original", "motivo": ""})], {"motivo": ""}
    dados = await comfy.imagem(saida["nome"], saida.get("subpasta", ""), saida.get("tipo", "output"))
    final, rel = await asyncio.to_thread(finalizacao_musica.finalizar, dados, p.duracao_musica, p.margem_musica, p.encerramento_musica, p.vocal_musica)
    original = dict(saida, musica=rel | {"versao": "Original"})
    if final is None: return [original], rel
    FINALIZACOES.mkdir(parents=True, exist_ok=True)
    nome = "musica_final_" + nome_musica(p) + "_" + hashlib.sha256(final).hexdigest()[:24] + ".flac"
    caminho = FINALIZACOES / nome
    if not caminho.exists():
        temporario = caminho.with_suffix(".tmp")
        temporario.write_bytes(final); temporario.replace(caminho)
    concluida = {"nome": nome, "subpasta": "finalizacoes_musica", "tipo": "output", "musica": rel | {"versao": "Finalizada", "original": saida}}
    return [original, concluida], rel
