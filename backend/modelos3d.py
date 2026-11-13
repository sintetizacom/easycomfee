"""Modelos 3D por API (Comfy Cloud, creditos): imagem -> arquivo GLB.

Nos lidos da nuvem em 13/11/2026. O preco vem do price_badge de cada no (precos.py).
Cada ficha diz qual no usar e em qual saida do no esta o GLB.
"""

MODELOS = {
    "tripo": {"rotulo": "Tripo 3.1", "no": "TripoImageToModelNodeV2", "saida_glb": 1,
              "dica": "Textured model with PBR materials. Good all-rounder."},
    # Texto -> 3D (sem imagem): o mesmo Tripo, com o no de texto.
    "tripo_texto": {"rotulo": "Tripo 3.1 (text)", "no": "TripoTextToModelNodeV2", "saida_glb": 1, "texto": True,
                    "dica": "Describe the object; no image needed."},
    # Hunyuan 3D (Tencent): imagem -> GLB; "Normal" com PBR opcional.
    "tencent": {"rotulo": "Hunyuan 3D 3.1", "no": "TencentImageToModelNode", "saida_glb": 1,
                "dica": "Tencent's Hunyuan 3D: detailed geometry, optional PBR."},
    "meshy": {"rotulo": "Meshy 7.1", "no": "MeshyImageToModelNode", "saida_glb": 2,
              "dica": "Clean topology, textures up to 8K."},
}


def grafo(modelo, imagem, texturizar=True, seed=42, prefixo="editor/modelo3d", prompt=""):
    """LoadImage -> no do provedor -> SaveGLB. `imagem` e o nome do arquivo na pasta de entrada."""
    if modelo not in MODELOS:
        raise ValueError("modelo 3D desconhecido")
    cfg = MODELOS[modelo]
    g = {}
    if cfg.get("texto"):
        if not prompt.strip():
            raise ValueError("describe the object to turn into 3D")
        g["gera"] = {"class_type": cfg["no"], "inputs": {
            "prompt": prompt.strip(), "model_version": "v3.1-20260211", "texture": bool(texturizar),
            "pbr": bool(texturizar), "model_seed": seed % 2147483647, "face_limit": -1}}
        g["salva"] = {"class_type": "SaveGLB", "inputs": {"mesh": ["gera", cfg["saida_glb"]], "filename_prefix": prefixo}}
        return g
    g["imagem"] = {"class_type": "LoadImage", "inputs": {"image": imagem}}
    if modelo == "tripo":
        g["gera"] = {"class_type": cfg["no"], "inputs": {
            "image": ["imagem", 0], "model_version": "v3.1-20260211", "texture": bool(texturizar),
            "pbr": bool(texturizar), "model_seed": seed % 2147483647, "face_limit": -1}}
    elif modelo == "tencent":
        g["gera"] = {"class_type": cfg["no"], "inputs": {
            "model": "3.1", "image": ["imagem", 0], "face_count": 500000, "generate_type": "Normal",
            "generate_type.pbr": bool(texturizar), "seed": seed % 2147483647}}
    else:
        textura = {"should_texture": "true", "should_texture.enable_pbr": True,
                   "should_texture.texture_prompt": "", "should_texture.texture_resolution": "2k"} \
            if texturizar else {"should_texture": "false"}
        g["gera"] = {"class_type": cfg["no"], "inputs": {
            "model": "meshy-7.1", "image": ["imagem", 0], "should_remesh": "true",
            "should_remesh.topology": "triangle", "should_remesh.target_polycount": 100000,
            "symmetry_mode": "auto", "pose_mode": "", "seed": seed % 2147483647, "ultra_mode": False, **textura}}
    # O SaveGLB precisa se chamar "salva": e dele que comfy.py le o resultado.
    g["salva"] = {"class_type": "SaveGLB", "inputs": {"mesh": ["gera", cfg["saida_glb"]], "filename_prefix": prefixo}}
    return g
