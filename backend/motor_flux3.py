"""Segundo motor: ComfyUI v0.41.1 na porta 8189, so para o Flux 3 Image Klein.

O motor do app (v0.37, porta 8188) nao conhece o Flux 3, e migrar o app
inteiro exigiria revalidar todos os nos personalizados. Os dois dividem a
mesma placa de 16 GB, entao:

- este motor so sobe quando a primeira geracao de Flux 3 chega;
- antes de cada geracao, o motor principal descarrega os modelos dele (o
  Flux 3 completo chega a 14,5 GiB);
- este roda com --cache-none, e devolve a VRAM ao fim de cada geracao.

As duas filas nunca rodam ao mesmo tempo: o operario do app executa uma
tarefa por vez, qualquer que seja o motor.
"""

import config
import asyncio
import pathlib
import subprocess
import time

import httpx

import comfy

RAIZ = pathlib.Path(__file__).parent.parent
LANCADOR = RAIZ / "_interno-subir-flux3.vbs"
INSTALACAO = config.COMFY_DIR_FLUX3
_subindo = asyncio.Lock()
# Sem comfy_url_flux3 no config, o "segundo motor" e o proprio ComfyUI de quem
# instalou (o caso comum, um ComfyUI recente so): nada a subir nem a liberar.
UNICO = config.COMFY_URL_FLUX3 == config.COMFY_URL


def instalado() -> bool:
    if UNICO:
        return True
    return (INSTALACAO / "main.py").exists() and LANCADOR.exists()


async def vivo() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            return (await c.get(f"{comfy.BASE_FLUX3}/system_stats")).status_code == 200
    except Exception:
        return False


async def garantir(limite: float = 180) -> None:
    """Deixa o segundo motor de pe e a placa livre para ele."""
    if UNICO:
        return
    if not instalado():
        raise RuntimeError("O motor do Flux 3 (ComfyUI v0.41) não está instalado.")
    # A VRAM do principal vai para o Flux 3. Se ele estiver fora do ar, nao
    # ha o que liberar.
    token = comfy.MOTOR.set(comfy.BASE_PRINCIPAL)
    try:
        await comfy.liberar_memoria()
    except Exception:
        pass
    finally:
        comfy.MOTOR.reset(token)
    async with _subindo:
        if await vivo():
            return
        await asyncio.to_thread(subprocess.run, ["wscript", str(LANCADOR)],
                                capture_output=True, timeout=30,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        fim = time.monotonic() + limite
        while time.monotonic() < fim:
            if await vivo():
                return
            await asyncio.sleep(2)
    raise RuntimeError("O motor do Flux 3 não subiu; veja logs/motor-flux3.log.")
