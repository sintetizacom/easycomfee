# coding: utf-8
r"""Converte o LoRA de destilacao (DMD) do LongCat-Video-Avatar 1.5 para o
formato que o ComfyUI-WanVideoWrapper le.

O arquivo oficial (lora/dmd_lora.safetensors) usa os nomes do codigo do
LongCat — "lora___lorahyphen___blocks___lorahyphen___0___...attn.qkv" — e o
wrapper nao os reconhece. Ninguem tinha publicado a versao convertida.

Mapeamento (o mesmo que o LoRA v1.0 convertido pelo Kijai usa):
  attn.qkv              -> self_attn.q / .k / .v   (lora_down em 3 fatias de 128,
                                                    lora_up ja vem em 3 blocos)
  attn.proj             -> self_attn.o
  cross_attn.q_linear   -> cross_attn.q
  cross_attn.kv_linear  -> cross_attn.k / .v       (2 fatias)
  ffn.w1 / w2 / w3      -> ffn.w1 / w2 / w3
A escala oficial e alpha_scale (0,5) com posto 128; no wrapper a escala e
alpha/posto, entao alpha = alpha_scale * posto = 64.

Uso:  python converter_lora_longcat15.py ENTRADA SAIDA
"""
import json
import struct
import sys

import numpy as np


def ler(caminho):
    f = open(caminho, "rb")
    n = struct.unpack("<Q", f.read(8))[0]
    cab = json.loads(f.read(n))
    cab.pop("__metadata__", None)
    base = 8 + n
    tipos = {"F32": np.float32, "F16": np.float16}

    def tensor(nome):
        t = cab[nome]
        a, b = t["data_offsets"]
        f.seek(base + a)
        bruto = f.read(b - a)
        if t["dtype"] == "BF16":
            x = (np.frombuffer(bruto, np.uint16).astype(np.uint32) << 16).view(np.float32)
        else:
            x = np.frombuffer(bruto, tipos[t["dtype"]]).astype(np.float32)
        return x.reshape(t["shape"])
    return cab, tensor


def para_bf16(x):
    # arredondamento ao par mais proximo, como o torch faz
    u = np.ascontiguousarray(x, np.float32).view(np.uint32)
    u = u + 0x7FFF + ((u >> 16) & 1)
    return (u >> 16).astype(np.uint16)


def gravar(caminho, tensores, meta):
    cab, pos, partes = {"__metadata__": meta}, 0, []
    for nome, x in tensores.items():
        dados = para_bf16(x).tobytes()
        cab[nome] = {"dtype": "BF16", "shape": list(x.shape), "data_offsets": [pos, pos + len(dados)]}
        partes.append(dados)
        pos += len(dados)
    j = json.dumps(cab, separators=(",", ":")).encode()
    j += b" " * (-len(j) % 8)
    with open(caminho, "wb") as f:
        f.write(struct.pack("<Q", len(j)))
        f.write(j)
        for p in partes:
            f.write(p)


def converter(entrada):
    cab, tensor = ler(entrada)
    nativo = lambda bloco, mod: f"lora___lorahyphen___blocks___lorahyphen___{bloco}___lorahyphen___" + \
        mod.replace(".", "___lorahyphen___")
    blocos = sorted({int(k.split("___lorahyphen___")[2]) for k in cab})
    saida = {}

    def poe(bloco, destino, down, up, alpha_scale):
        posto = down.shape[0]
        p = f"diffusion_model.blocks.{bloco}.{destino}"
        saida[p + ".lora_down.weight"] = down
        saida[p + ".lora_up.weight"] = up
        saida[p + ".alpha"] = np.array(alpha_scale * posto, np.float32)

    for b in blocos:
        for origem, destinos in (("attn.qkv", ("self_attn.q", "self_attn.k", "self_attn.v")),
                                 ("cross_attn.kv_linear", ("cross_attn.k", "cross_attn.v"))):
            n = nativo(b, origem)
            down = tensor(n + ".lora_down.weight")
            esc = float(tensor(n + ".alpha_scale"))
            fatia = down.shape[0] // len(destinos)
            for i, d in enumerate(destinos):
                poe(b, d, down[i * fatia:(i + 1) * fatia], tensor(f"{n}.lora_up.blocks.{i}.weight"), esc)
        for origem, destino in (("attn.proj", "self_attn.o"), ("cross_attn.q_linear", "cross_attn.q"),
                                ("ffn.w1", "ffn.w1"), ("ffn.w2", "ffn.w2"), ("ffn.w3", "ffn.w3")):
            n = nativo(b, origem)
            poe(b, destino, tensor(n + ".lora_down.weight"), tensor(n + ".lora_up.weight"),
                float(tensor(n + ".alpha_scale")))
    return saida, len(blocos), len(cab)


if __name__ == "__main__":
    saida, nblocos, n_orig = converter(sys.argv[1])
    print(f"{nblocos} blocos, {len(saida)} tensores gerados a partir de {n_orig} originais")
    gravar(sys.argv[2], saida, {"format": "pt", "model_type": "LongCat_Avatar15_dmd_lora",
                                "fonte": "meituan-longcat/LongCat-Video-Avatar-1.5 lora/dmd_lora.safetensors"})
    print("gravado:", sys.argv[2])
