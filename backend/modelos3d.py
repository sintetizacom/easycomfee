"""Modelos 3D por API (Comfy Cloud, creditos): imagem ou texto -> arquivo GLB.

Nos lidos da nuvem em 13/11/2026. O preco vem do price_badge de cada no (precos.py).
Cada ficha diz qual no usar, em qual saida do no esta o GLB, os modos que aceita e os
ajustes que a tela mostra (a tela le tudo de catalogo(): nada fica repetido no frontend).

Um ajuste: {"id", "rotulo", "tipo": "select" | "toggle", "padrao", "opcoes": [(valor, rotulo)], "dica"}.
"""


def _sel(id, rotulo, opcoes, padrao, dica="", grupo=""):
    return {"id": id, "rotulo": rotulo, "tipo": "select", "opcoes": [(v, r) for v, r in opcoes], "padrao": padrao, "dica": dica, "grupo": grupo}


def _chave(id, rotulo, padrao=False, dica="", grupo=""):
    return {"id": id, "rotulo": rotulo, "tipo": "toggle", "padrao": padrao, "dica": dica, "grupo": grupo}


# Rig e animacao do Tripo ("0" = nenhum; "rig" = so o esqueleto, sem animar).
ANIMACOES = [("0", "None"), ("rig", "Rig only (skeleton)"), ("preset:idle", "Idle"), ("preset:walk", "Walk"), ("preset:run", "Run"),
             ("preset:jump", "Jump"), ("preset:climb", "Climb"), ("preset:slash", "Slash"), ("preset:shoot", "Shoot"), ("preset:hurt", "Hurt"),
             ("preset:fall", "Fall"), ("preset:turn", "Turn"), ("preset:biped:dance_01", "Dance"), ("preset:biped:cheer", "Cheer"),
             ("preset:biped:wave_goodbye_01", "Wave"), ("preset:biped:clap", "Clap"), ("preset:biped:sit", "Sit"),
             ("preset:biped:victory_celebration", "Victory"), ("preset:quadruped:walk", "Walk (four legs)")]

_TRIPO_AJUSTES = [
    _sel("versao", "Version", [("v3.1-20260211", "3.1 (newest)"), ("v3.0-20250812", "3.0"), ("v2.5-20250123", "2.5")], "v3.1-20260211"),
    _sel("geometria", "Geometry", [("standard", "Standard"), ("detailed", "Detailed")], "standard", "Detailed costs more."),
    _sel("textura_qualidade", "Texture quality", [("standard", "Standard"), ("detailed", "HD"), ("extreme", "8K")], "standard"),
    _sel("faces", "Face limit", [("-1", "Automatic"), ("10000", "10K"), ("50000", "50K"), ("200000", "200K"), ("500000", "500K")], "-1",
         "Fewer faces = lighter file for games and real-time."),
    _chave("pbr", "PBR materials", True, "Metallic, roughness and normal maps along with the color."),
    _chave("low_poly", "Low-poly style", False, "A clean hand-made look with 500 to 20,000 faces."),
    # Depois de construir (so o Tripo): tudo no mesmo pedido, encadeado na nuvem.
    _sel("retopologia", "Clean low-poly mesh", [("0", "Off"), ("2000", "2K faces"), ("5000", "5K faces"), ("10000", "10K faces"), ("20000", "20K faces")], "0",
         "Rebuilds the mesh with clean, light topology and keeps the textures.", grupo="depois"),
    _sel("animacao", "Rig and animate", [(k, r) for k, r in ANIMACOES], "0",
         "Adds a skeleton so the model can move. Works best on characters and animals.", grupo="depois"),
    _sel("esqueleto", "Skeleton for", [("biped", "A person (biped)"), ("creature", "An animal or creature")], "biped",
         "Pick the one that matches the model. Used by Rig and animate.", grupo="depois"),
    _sel("formato_extra", "Also save as", [("0", "Only GLB"), ("FBX", "FBX"), ("OBJ", "OBJ"), ("STL", "STL (3D print)"), ("USDZ", "USDZ (Apple)"), ("3MF", "3MF")], "0",
         "An extra file to use in other programs.", grupo="depois"),
]

MODELOS = {
    "tripo": {"rotulo": "Tripo 3.1", "no": "TripoImageToModelNodeV2", "saida_glb": 1, "modos": ["imagem", "vistas"], "no_vistas": "TripoMultiviewToModelNode", "saida_vistas": 2,
              "resumo": "Fast all-rounder with PBR textures.", "pontos": ["Fastest", "Cheapest", "Low-poly option"],
              "ajustes": _TRIPO_AJUSTES},
    # Texto -> 3D (sem imagem): o mesmo Tripo, com o no de texto.
    "tripo_texto": {"rotulo": "Tripo 3.1", "no": "TripoTextToModelNodeV2", "saida_glb": 1, "modos": ["texto"], "texto": True,
                    "resumo": "Describe the object and Tripo builds it. No image needed.", "pontos": ["No image", "Fast"],
                    "ajustes": _TRIPO_AJUSTES},
    # Hunyuan 3D (Tencent): imagem -> GLB; "Normal" (com textura) ou "Geometry" (so a forma).
    "tencent": {"rotulo": "Hunyuan 3D", "no": "TencentImageToModelNode", "saida_glb": 1, "modos": ["imagem", "vistas"], "saida_vistas": 1,
                "resumo": "Tencent's model: detailed geometry, optional PBR.", "pontos": ["Detailed shape", "Up to 1.5M faces"],
                "ajustes": [
                    _sel("versao", "Version", [("3.1", "3.1"), ("3.0", "3.0")], "3.1"),
                    _sel("faces", "Face count", [("100000", "100K"), ("300000", "300K"), ("500000", "500K"), ("1000000", "1M"), ("1500000", "1.5M")], "500000"),
                    _chave("pbr", "PBR materials", False),
                ]},
    # Rodin Gen-2.5 (Hyper3D): imagem -> GLB.
    "rodin": {"rotulo": "Rodin Gen-2.5", "no": "Rodin3D_Gen25_Image", "saida_glb": 0, "modos": ["imagem", "vistas"], "saida_vistas": 0,
              "resumo": "Hyper3D: high-fidelity geometry.", "pontos": ["Highest fidelity", "Quad or raw mesh"],
              "ajustes": [
                  _sel("modo", "Mode", [("Regular", "Regular"), ("Fast", "Fast (20K faces)"), ("Extreme-High", "Extreme (up to 2M faces)")], "Regular"),
                  _sel("nivel", "Quality tier", [("Low", "Low"), ("Medium", "Medium"), ("High", "High")], "High"),
                  _sel("material", "Material", [("PBR", "PBR"), ("Shaded", "Shaded"), ("All", "All")], "PBR"),
                  _chave("criativo", "Creative mode", False, "More inventive; Regular and Extreme modes only."),
                  _chave("hd", "HD texture", False),
                  _chave("pose_t", "T/A pose", False, "For people and characters."),
                  _chave("sem_luz", "Remove baked light", False, "Texture without painted-in shadows."),
              ]},
    "meshy": {"rotulo": "Meshy 7.1", "no": "MeshyImageToModelNode", "saida_glb": 2, "modos": ["imagem", "vistas"], "no_vistas": "MeshyMultiImageToModelNode", "saida_vistas": 2,
              "resumo": "Clean topology, textures up to 8K, character poses.", "pontos": ["Clean topology", "8K textures", "A/T pose"],
              "ajustes": [
                  _sel("versao", "Version", [("meshy-7.1", "7.1"), ("meshy-7", "7"), ("meshy-6", "6"), ("latest", "Latest")], "meshy-7.1"),
                  _sel("topologia", "Topology", [("triangle", "Triangles"), ("quad", "Quads")], "triangle"),
                  _sel("faces", "Face target", [("10000", "10K"), ("30000", "30K"), ("100000", "100K"), ("300000", "300K")], "100000"),
                  _sel("simetria", "Symmetry", [("auto", "Auto"), ("on", "On"), ("off", "Off")], "auto"),
                  _sel("pose", "Pose", [("", "Any"), ("A-pose", "A-pose"), ("T-pose", "T-pose")], "", "For people and characters."),
                  _sel("textura_resolucao", "Texture size", [("2k", "2K"), ("4k", "4K"), ("8k", "8K")], "2k"),
                  _chave("pbr", "PBR materials", True),
                  _chave("ultra", "Ultra detail pass", False, "Extra refinement of the surface. Costs more."),
              ]},
}


def catalogo():
    """O que a tela precisa para montar os cartoes de modelo e os ajustes."""
    return [{"id": k, **{c: v[c] for c in ("rotulo", "modos", "resumo", "pontos")},
             "ajustes": [{**a, "opcoes": [list(o) for o in a.get("opcoes", [])]} for a in v["ajustes"]]}
            for k, v in MODELOS.items()]


def limpar_ajustes(modelo, ajustes):
    """Ajustes validados: so os ids do modelo, valores dentro das opcoes; o resto vira o padrao."""
    cfg = MODELOS[modelo]
    entrada = ajustes if isinstance(ajustes, dict) else {}
    saida = {}
    for a in cfg["ajustes"]:
        v = entrada.get(a["id"], a["padrao"])
        if a["tipo"] == "toggle":
            v = bool(v) if isinstance(v, (bool, int)) else a["padrao"]
        else:
            validos = [str(o[0]) for o in a["opcoes"]]
            v = str(v) if str(v) in validos else a["padrao"]
        saida[a["id"]] = v
    return saida


def _modo_rodin(aj):
    modo = aj["modo"]
    ent = {"mode": modo}
    if modo == "Regular":
        ent.update({"mode.tier": f"Gen-2.5-{aj['nivel']}", "mode.polygon_count": "Default", "mode.creative": aj["criativo"]})
    elif modo == "Fast":
        ent.update({"mode.tier": f"Gen-2.5-{aj['nivel']}", "mode.mesh_faces": 20000})
    else:
        ent.update({"mode.mesh_mode": "Raw", "mode.mesh_faces": 1000000, "mode.is_micro": False, "mode.creative": aj["criativo"]})
    return ent


def _depois(g, aj, cfg, saida_tarefa, saida_glb, prefixo):
    """O que o Tripo faz depois de construir, encadeado no mesmo pedido: limpar a malha (retopologia),
    rig e animacao, e salvar tambem em outro formato. O GLB final e o "salva"; o outro formato, "salva_extra"."""
    tarefa, glb = ["gera", saida_tarefa], ["gera", saida_glb]
    if aj["retopologia"] != "0":
        g["retopo"] = {"class_type": "TripoRetopologyNode", "inputs": {
            "model_task_id": tarefa, "face_limit": int(aj["retopologia"]), "quad": False, "bake": True}}
        tarefa, glb = ["retopo", 1], ["retopo", 2]
    if aj["animacao"] != "0":
        criatura = aj["esqueleto"] == "creature"
        anim = aj["animacao"]
        # O esqueleto de pessoa (v1.0) so aceita bipedes; o de criatura (v2.5) nao tem as animacoes "biped".
        if anim.startswith("preset:biped:") and criatura:
            raise ValueError("That animation is for people: pick Skeleton for: a person, or a general animation like Walk or Run.")
        if anim.startswith(("preset:quadruped", "preset:hexapod", "preset:octopod", "preset:serpentine", "preset:aquatic")) and not criatura:
            raise ValueError("That animation is for animals: pick Skeleton for: an animal or creature.")
        g["rig"] = {"class_type": "TripoRigNode", "inputs": {
            "original_model_task_id": tarefa, "model_version": "v2.5-20260210" if criatura else "v1.0-20240301",
            "rig_type": "auto" if criatura else "biped", "spec": "tripo", "out_format": "glb"}}
        tarefa, glb = ["rig", 1], ["rig", 2]
        if aj["animacao"] != "rig":
            g["animacao"] = {"class_type": "TripoRetargetNode", "inputs": {
                "original_model_task_id": tarefa, "animation": aj["animacao"], "out_format": "glb",
                "export_with_geometry": True, "animate_in_place": False}}
            tarefa, glb = ["animacao", 1], ["animacao", 2]
    if aj["formato_extra"] != "0":
        # A nuvem marca estes como opcionais mas o no exige todos ("missing 17 required positional arguments").
        g["converte"] = {"class_type": "TripoConversionNode", "inputs": {
            "original_model_task_id": tarefa, "format": aj["formato_extra"], "quad": False, "face_limit": -1, "texture_size": 4096,
            "texture_format": "JPEG", "force_symmetry": False, "flatten_bottom": False, "flatten_bottom_threshold": 0.01,
            "pivot_to_center_bottom": False, "scale_factor": 1.0, "with_animation": True, "pack_uv": False, "bake": True,
            "part_names": "", "fbx_preset": "blender", "export_vertex_colors": False, "export_orientation": "default",
            "animate_in_place": False}}
        g["salva_extra"] = {"class_type": "SaveGLB", "inputs": {"mesh": ["converte", 0], "filename_prefix": prefixo + "_" + aj["formato_extra"].lower()}}
    # O SaveGLB precisa se chamar "salva": e dele que comfy.py le o resultado.
    g["salva"] = {"class_type": "SaveGLB", "inputs": {"mesh": glb, "filename_prefix": prefixo}}


def _entrada_tripo(aj, texturizar, seed32):
    return {"model_version": aj["versao"], "texture": bool(texturizar), "pbr": bool(texturizar and aj["pbr"]),
            "texture_quality": aj["textura_qualidade"], "geometry_quality": aj["geometria"],
            "face_limit": int(aj["faces"]), "smart_low_poly": aj["low_poly"], "model_seed": seed32}


VISTAS = ("esquerda", "costas", "direita")  # alem da frente, que e a imagem principal


def grafo(modelo, imagem, texturizar=True, seed=42, prefixo="editor/modelo3d", prompt="", ajustes=None, vistas=None):
    """LoadImage -> no do provedor -> SaveGLB. `imagem` e o nome do arquivo na pasta de entrada."""
    if modelo not in MODELOS:
        raise ValueError("modelo 3D desconhecido")
    cfg = MODELOS[modelo]
    aj = limpar_ajustes(modelo, ajustes)
    imagens = [i for i in (imagem if isinstance(imagem, (list, tuple)) else [imagem]) if i]
    g = {}
    seed32 = seed % 2147483647
    if cfg.get("texto"):
        if not prompt.strip():
            raise ValueError("describe the object to turn into 3D")
        g["gera"] = {"class_type": cfg["no"], "inputs": {"prompt": prompt.strip(), **_entrada_tripo(aj, texturizar, seed32)}}
        _depois(g, aj, cfg, 0, cfg["saida_glb"], prefixo)
        return g
    if not imagens:
        raise ValueError("send the image to turn into 3D")
    g["imagem"] = {"class_type": "LoadImage", "inputs": {"image": imagens[0]}}
    # Varias vistas: so entram as que existem; sem nenhuma extra, e o modo de uma imagem so.
    extras = {k: v for k, v in (vistas or {}).items() if k in VISTAS and v}
    for k, nome in extras.items():
        g[f"imagem_{k}"] = {"class_type": "LoadImage", "inputs": {"image": nome}}
    ref = lambda k: [f"imagem_{k}", 0]
    saida = cfg["saida_vistas"] if extras else cfg["saida_glb"]
    if modelo == "tripo":
        if extras:
            # Este no e das versoes antigas: manda tambem os campos "opcionais" (como o Rodin e a conversao, a nuvem os exige).
            no = {"class_type": cfg["no_vistas"], "inputs": {
                "image": ["imagem", 0], **_entrada_tripo(aj, texturizar, seed32), "orientation": "default", "quad": False,
                "texture_alignment": "original_image", "texture_seed": seed32, "auto_size": False}}
            for k, ent in (("esquerda", "image_left"), ("costas", "image_back"), ("direita", "image_right")):
                if k in extras:
                    no["inputs"][ent] = ref(k)
            g["gera"] = no
        else:
            g["gera"] = {"class_type": cfg["no"], "inputs": {"image": ["imagem", 0], **_entrada_tripo(aj, texturizar, seed32)}}
    elif modelo == "rodin":
        fotos = {f"images.image{i}": r for i, r in enumerate([["imagem", 0]] + [ref(k) for k in VISTAS if k in extras])}
        g["gera"] = {"class_type": cfg["no"], "inputs": {
            **fotos, **_modo_rodin(aj),
            "material": aj["material"] if texturizar else "None", "geometry_file_format": "glb", "seed": seed % 65535,
            # A nuvem marca estes como opcionais mas o no exige todos (erro "missing 10 required arguments").
            "texture_mode": "Default", "TAPose": aj["pose_t"], "hd_texture": aj["hd"], "texture_delight": aj["sem_luz"],
            "use_original_alpha": False, "addon_highpack": False, "bbox_width": 0, "bbox_height": 0,
            "bbox_length": 0, "height_cm": 0}}
    elif modelo == "tencent":
        entrada = {"model": aj["versao"], "image": ["imagem", 0], "face_count": int(aj["faces"]), "seed": seed32}
        if texturizar:
            entrada.update({"generate_type": "Normal", "generate_type.pbr": aj["pbr"]})
        else:
            entrada["generate_type"] = "Geometry"
        for k, ent in (("esquerda", "image_left"), ("direita", "image_right"), ("costas", "image_back")):
            if k in extras:
                entrada[ent] = ref(k)
        g["gera"] = {"class_type": cfg["no"], "inputs": entrada}
    else:
        textura = ({"should_texture": "true", "should_texture.enable_pbr": aj["pbr"],
                    "should_texture.texture_prompt": "", "should_texture.texture_resolution": aj["textura_resolucao"]}
                   if texturizar else {"should_texture": "false"})
        ultra = {"ultra_resolution": "2k"} if aj["ultra"] else {}
        comuns = {"model": aj["versao"], "should_remesh": "true",
                  "should_remesh.topology": aj["topologia"], "should_remesh.target_polycount": int(aj["faces"]),
                  "symmetry_mode": aj["simetria"], "pose_mode": aj["pose"], "seed": seed32, "ultra_mode": aj["ultra"],
                  **textura}
        if extras:
            fotos = {f"images.image{i}": r for i, r in enumerate([["imagem", 0]] + [ref(k) for k in VISTAS if k in extras])}
            g["gera"] = {"class_type": cfg["no_vistas"], "inputs": {**fotos, **comuns}}
        else:
            # "ultra_resolution" so existe no no de uma imagem.
            g["gera"] = {"class_type": cfg["no"], "inputs": {"image": ["imagem", 0], **comuns, **ultra}}
    if modelo == "tripo":
        _depois(g, aj, cfg, 1 if extras else 0, saida, prefixo)
        return g
    # O SaveGLB precisa se chamar "salva": e dele que comfy.py le o resultado.
    g["salva"] = {"class_type": "SaveGLB", "inputs": {"mesh": ["gera", saida], "filename_prefix": prefixo}}
    return g
