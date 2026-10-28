"""Telemetria em segundo plano. A API só lê o último retrato, sem subprocessos."""
import config
import asyncio
import ctypes
import subprocess
import sys
import time

import httpx

ESTADO = {"coletado_em": None, "motor_respondendo": None,
          "gpu": None, "ram": None, "cpu_pct": None, "executando": 0, "na_fila": 0}


_CPU_ANTES: tuple[int, int] | None = None


def _cpu_pct() -> float | None:
    """Uso da CPU desde a ultima leitura, pelo GetSystemTimes do Windows (sem psutil)."""
    global _CPU_ANTES
    ocioso, nucleo, usuario = (ctypes.c_ulonglong() for _ in range(3))
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(ocioso), ctypes.byref(nucleo), ctypes.byref(usuario)):
        return None
    total, livre = nucleo.value + usuario.value, ocioso.value  # o tempo de nucleo ja inclui o ocioso
    antes, _CPU_ANTES = _CPU_ANTES, (total, livre)
    if not antes or total == antes[0]:
        return None
    return round(100 * (1 - (livre - antes[1]) / (total - antes[0])), 1)


def recursos():
    resultado = {"gpu": None, "ram": None, "cpu_pct": None}
    if sys.platform == "win32":
        resultado["cpu_pct"] = _cpu_pct()
    if sys.platform == "win32":
        class Memoria(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (nome, ctypes.c_ulonglong) for nome in
                ("total_phys", "avail_phys", "total_page", "avail_page",
                 "total_virtual", "avail_virtual", "avail_extended")]
        memoria = Memoria()
        memoria.length = ctypes.sizeof(memoria)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memoria)):
            resultado["ram"] = {"usada_gib": round((memoria.total_phys - memoria.avail_phys) / 2**30, 2),
                                "total_gib": round(memoria.total_phys / 2**30, 2)}
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
             "--format=csv,noheader,nounits"], capture_output=True, text=True,
            timeout=3, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode == 0:
            usada, total, uso = map(float, r.stdout.splitlines()[0].split(","))
            resultado["gpu"] = {"vram_usada_gib": round(usada / 1024, 2),
                                "vram_total_gib": round(total / 1024, 2), "uso_pct": uso}
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        pass
    return resultado


async def vigiar(ao_fila):
    global ESTADO
    async with httpx.AsyncClient(timeout=3) as cliente:
        while True:
            medidas = await asyncio.to_thread(recursos)
            retrato = {**medidas, "coletado_em": time.time(), "motor_respondendo": False,
                       "executando": None, "na_fila": None}
            try:
                r = await cliente.get(f"{config.COMFY_URL}/queue")
                r.raise_for_status()
                fila = r.json()
                retrato.update(motor_respondendo=True,
                               executando=len(fila.get("queue_running", [])),
                               na_fila=len(fila.get("queue_pending", [])))
                await ao_fila(fila)
            except (httpx.HTTPError, ValueError):
                pass
            ESTADO = retrato
            # 2 s: o medidor de recursos da barra de cima le daqui.
            await asyncio.sleep(2)
