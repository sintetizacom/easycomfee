"""LTX 2.3 na aba Video: primeiro quadro, ultimo quadro opcional e audio opcional.

Parte do mesmo grafo do avatar (grafos/ltx23_ia2v.json, medido em 14/10/2026)
e muda so o que o modo pede:

- ultimo quadro: o no `guia_fim` (LTXVAddGuide, frame_idx -1) recebe uma
  imagem propria, em vez da mesma foto do primeiro quadro. Sem ultimo
  quadro, a guia sai do grafo e o modelo decide o fim livremente.
- audio: com arquivo, o audio entra com mascara zero (fica intacto e o video
  se ajusta a ele, como no avatar). Sem arquivo, o latente de audio nasce
  vazio e o modelo compoe o som junto do video.
"""

import copy
import json
import pathlib

GRAFO = pathlib.Path(__file__).parent / "grafos" / "ltx23_ia2v.json"
# O no 340:318 (codificador de texto) le "ltx-2.3-22b-dev-fp8_so_texto", e nao
# o checkpoint de 27 GB: so os 262 tensores que ele usa (projecao e conectores
# de texto, 6,3 GB), extraidos do original com os metadados. Ler o checkpoint
# inteiro ali derrubava o motor de forma intermitente (access violation em
# torch_cpu.dll). MEDIDO em 17/10/2026: saida identica quadro a quadro, e cinco
# geracoes seguidas no mesmo processo sem queda; antes, caia ja na 2a.
_base = None


def _modelo():
    global _base
    if _base is None:
        _base = json.loads(GRAFO.read_text(encoding="utf-8"))
    return copy.deepcopy(_base)


def grafo(prompt, seed, largura, altura, duracao, primeiro, ultimo=None,
          audio=None, prefixo="editor/ltx23"):
    g = _modelo()
    g["269"]["inputs"]["image"] = primeiro
    g["340:319"]["inputs"]["value"] = prompt.strip()
    g["340:330"]["inputs"]["value"] = largura
    g["340:324"]["inputs"]["value"] = altura
    g["340:331"]["inputs"]["value"] = round(float(duracao), 3)
    g["340:285"]["inputs"]["noise_seed"] = seed
    g["340:286"]["inputs"]["noise_seed"] = seed + 1
    g["341"]["inputs"]["filename_prefix"] = prefixo

    if ultimo:
        # Mesma cadeia de preparo do primeiro quadro (corte central no
        # tamanho do video, lado maior 1536, compressao do LTXVPreprocess).
        g["ult_carga"] = {"class_type": "LoadImage", "inputs": {"image": ultimo}}
        g["ult_corte"] = copy.deepcopy(g["340:297"])
        g["ult_corte"]["inputs"]["input"] = ["ult_carga", 0]
        g["ult_lado"] = copy.deepcopy(g["340:350"])
        g["ult_lado"]["inputs"]["input"] = ["ult_corte", 0]
        g["ult_prep"] = copy.deepcopy(g["340:334"])
        g["ult_prep"]["inputs"]["image"] = ["ult_lado", 0]
        g["guia_fim"]["inputs"]["image"] = ["ult_prep", 0]
    else:
        # Sem guia no fim: tudo que lia dela volta a ler o que ela lia.
        del g["guia_fim"]
        g["340:326"]["inputs"]["video_latent"] = ["340:325", 0]
        for no in ("340:315", "340:292"):
            g[no]["inputs"]["positive"] = ["340:307", 0]
            g[no]["inputs"]["negative"] = ["340:307", 1]

    if audio:
        g["276"]["inputs"]["audio"] = audio
    else:
        for no in ("276", "340:332", "340:328", "340:327", "340:333"):
            del g[no]
        g["som_vazio"] = {"class_type": "LTXVEmptyLatentAudio", "inputs": {
            "frames_number": ["340:329", 1], "frame_rate": ["340:304", 0],
            "batch_size": 1, "audio_vae": ["340:335", 0]}}
        g["340:326"]["inputs"]["audio_latent"] = ["som_vazio", 0]
    return g
