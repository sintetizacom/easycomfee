# -*- coding: utf-8 -*-
r"""Executa dois smoke tests locais no ComfyUI.

O primeiro percorre fila, histórico e gravação sem carregar modelo. O segundo
faz uma inferência mínima com o Krea local. Nenhum nó de nuvem é permitido.

    backend\.venv\Scripts\python.exe backend\testes\smoke_comfy.py
"""
import argparse
import asyncio
import pathlib
import sys
import time

import httpx

RAIZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent))

import comfy             # noqa: E402
import presets as P      # noqa: E402
import workflows as W    # noqa: E402


def grafo_local(grafo):
    proibidos = ("ComfyCloud", "OpenAI", "Gemini", "TopazImageEnhance")
    classes = [no.get("class_type", "") for no in grafo.values()]
    encontrados = [classe for classe in classes
                   if any(nome in classe for nome in proibidos)]
    if encontrados:
        raise RuntimeError("smoke test recusou nós externos: "
                           + ", ".join(sorted(set(encontrados))))


async def fila_vazia():
    async with httpx.AsyncClient(timeout=10) as cliente:
        resposta = await cliente.get(f"{comfy.BASE_PRINCIPAL}/queue")
        resposta.raise_for_status()
        fila = resposta.json()
    return not fila.get("queue_running") and not fila.get("queue_pending")


async def executar_e_conferir(nome, grafo, dimensoes, timeout):
    grafo_local(grafo)
    inicio = time.perf_counter()
    saidas = await comfy.executar(grafo, timeout=timeout)
    arquivos = comfy.imagens_salvas(saidas)
    if len(arquivos) != 1:
        raise RuntimeError(f"{nome}: esperado um arquivo, obtidos {arquivos!r}")
    arquivo = arquivos[0]
    tamanho = await comfy.tamanho_imagem(
        arquivo["nome"], arquivo["subpasta"], arquivo["tipo"])
    largura_altura = await comfy.dimensoes_imagem(
        arquivo["nome"], arquivo["subpasta"], arquivo["tipo"])
    if tamanho <= 0:
        raise RuntimeError(f"{nome}: arquivo vazio ou inacessível")
    if largura_altura != dimensoes:
        raise RuntimeError(
            f"{nome}: esperado {dimensoes}, obtido {largura_altura}")
    tempo = time.perf_counter() - inicio
    print(f"{nome}: OK — {largura_altura[0]}x{largura_altura[1]}, "
          f"{tamanho} bytes, {tempo:.2f} s, {arquivo['nome']}")


async def main_async(casos):
    if not await comfy.esta_vivo():
        raise RuntimeError(f"ComfyUI não respondeu em {comfy.BASE_PRINCIPAL}")
    if not await fila_vazia():
        raise RuntimeError("fila do ComfyUI ocupada; smoke test não iniciado")

    if "infra" in casos:
        grafo = {
            "imagem": {"class_type": "EmptyImage",
                       "inputs": {"width": 64, "height": 64,
                                  "batch_size": 1, "color": 0x204060}},
            "salva": {"class_type": "SaveImage",
                      "inputs": {"images": ["imagem", 0],
                                 "filename_prefix": "testes/smoke_infra"}},
        }
        await executar_e_conferir("infraestrutura", grafo, (64, 64), 60)

    if "imagem" in casos:
        modelo = "krea"
        if modelo not in P.SIMPLE:
            raise RuntimeError("preset local Krea não está disponível")
        grafo = W.gerar_simples(
            modelo,
            "a single red wooden cube on a plain gray studio background",
            "", 20260921, 256, 256, steps=1,
            prefixo="testes/smoke_krea")
        await executar_e_conferir("modelo local Krea", grafo, (256, 256), 600)

    if "folha" in casos:
        # A folha precisa de uma foto DENTRO da pasta input do motor — o nó
        # LoadImage só enxerga de lá. Copiamos a fixture para um nome próprio
        # em vez de usar algo que já esteja na pasta: assim o teste não depende
        # do que sobrou de outra sessão.
        import app as A          # noqa: E402  (traz ENTRADA_DO_MOTOR já resolvida)
        origem = RAIZ / "fixtures" / "rosto.jpg"
        if not origem.exists():
            raise RuntimeError(f"fixture ausente: {origem}")
        destino = A.ENTRADA_DO_MOTOR / "smoke_folha.jpg"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(origem.read_bytes())

        p_folha = P.EDICAO["folha"]
        grafo = W.gerar_folha_personagem(
            destino.name, p_folha["gatilho"], 20260922,
            prefixo="testes/smoke_folha")
        # O que se prova aqui é que o grafo EXECUTA e devolve a folha no
        # tamanho certo. A qualidade não se julga: a fixture é um rosto, e a
        # ferramenta pede corpo inteiro. Ver NOTAS-MOTOR.md.
        await executar_e_conferir("folha de personagem", grafo,
                                  tuple(p_folha["saida"]), 900)

    if not await fila_vazia():
        raise RuntimeError("o smoke test terminou, mas a fila não ficou vazia")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--caso", choices=("infra", "imagem", "folha", "todos"),
                        default="todos")
    args = parser.parse_args()
    casos = ({"infra", "imagem", "folha"} if args.caso == "todos"
             else {args.caso})
    try:
        asyncio.run(main_async(casos))
    except Exception as erro:
        print(f"FALHA: {erro}")
        return 1
    print(f"{len(casos)} smoke test(s) local(is) passaram; nenhuma nuvem usada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
