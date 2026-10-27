"""A maquina de quem usa o app: placa, VRAM, RAM e disco livre.

Detecta sozinho e guarda o que a pessoa confirmou (ou corrigiu) em
maquina.json. E com esse perfil que a tela de modelos diz, para cada pacote,
se ele roda bem, roda limitado ou nao roda aqui, antes de baixar dezenas de GB.
"""
import ctypes
import json
import shutil
import subprocess
import sys

import httpx

import config

ARQUIVO = config.RAIZ / "backend" / "maquina.json"
GB = 1024 ** 3


def _ram_do_sistema() -> float | None:
    if sys.platform != "win32":
        try:
            import os
            return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / GB
        except (ValueError, OSError, AttributeError):
            return None

    class Estado(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    e = Estado()
    e.dwLength = ctypes.sizeof(Estado)
    return e.ullTotalPhys / GB if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(e)) else None


def _nvidia_smi() -> tuple[str, float] | None:
    try:
        saida = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=10).stdout
        nome, mib = saida.strip().splitlines()[0].rsplit(",", 1)
        return nome.strip(), float(mib) / 1024
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


def _disco_livre() -> float | None:
    pasta = config.MODELOS_DIR
    while not pasta.exists() and pasta != pasta.parent:
        pasta = pasta.parent
    try:
        return shutil.disk_usage(pasta).free / GB
    except OSError:
        return None


async def detectar() -> dict:
    """O que da para saber sem perguntar. Fonte principal: o proprio ComfyUI
    local, que ja mede a placa; sem ele, o nvidia-smi."""
    d = {"gpu": None, "vram_gb": None, "ram_gb": _ram_do_sistema(), "disco_livre_gb": _disco_livre(),
         "fonte": None}
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"{config.COMFY_URL}/system_stats")
            r.raise_for_status()
            s = r.json()
        dev = (s.get("devices") or [{}])[0]
        if dev.get("vram_total"):
            d.update(gpu=dev.get("name", "").split(" : ")[0].replace("cuda:0 ", ""),
                     vram_gb=dev["vram_total"] / GB, fonte="comfyui")
        d["ram_gb"] = s.get("system", {}).get("ram_total", 0) / GB or d["ram_gb"]
    except Exception:
        pass
    if d["vram_gb"] is None and (smi := _nvidia_smi()):
        d.update(gpu=smi[0], vram_gb=smi[1], fonte="nvidia-smi")
    for k in ("vram_gb", "ram_gb", "disco_livre_gb"):
        if d[k] is not None:
            d[k] = round(d[k], 1)
    return d


def salvo() -> dict | None:
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def salvar(perfil: dict) -> dict:
    """Perfil confirmado: {gpu, vram_gb, ram_gb, so_nuvem}."""
    limpo = {"gpu": str(perfil.get("gpu") or "")[:80],
             "vram_gb": float(perfil.get("vram_gb") or 0),
             "ram_gb": float(perfil.get("ram_gb") or 0),
             "so_nuvem": bool(perfil.get("so_nuvem"))}
    ARQUIVO.write_text(json.dumps(limpo), encoding="utf-8")
    return limpo


def eh_amd(gpu: str) -> bool:
    g = gpu.lower()
    return "amd" in g or "radeon" in g


def avaliar(req: dict, perfil: dict | None, disco_livre: float | None, faltando_gb: float) -> dict:
    """Selo de um pacote para esta maquina.

    bem: acima do recomendado. limitado: cabe, mas so com menos qualidade ou
    muito mais devagar (o motivo vem do catalogo). nao_roda: abaixo do minimo.
    sem_perfil: a pessoa ainda nao confirmou a maquina.
    """
    if not perfil:
        return {"selo": "sem_perfil"}
    if perfil.get("so_nuvem"):
        return {"selo": "nuvem"}
    # +1 GB: uma placa "de 16 GB" se apresenta como 15,9.
    vram, ram = perfil.get("vram_gb", 0) + 1, perfil.get("ram_gb", 0) + 1
    if vram < req["vram_min"] or (req.get("ram_min") and ram < req["ram_min"]):
        selo, motivo = "nao_roda", f"Needs {req['vram_min']} GB VRAM" + (
            f" and {req['ram_min']} GB RAM" if req.get("ram_min") else "") + "."
    elif vram < req["vram_rec"]:
        selo, motivo = "limitado", req.get("nota_limitado") or f"Recommended: {req['vram_rec']} GB VRAM."
    else:
        selo, motivo = "bem", ""
    # Os pacotes foram testados so em NVIDIA (fp8/nvfp4/int8 sao formatos de NVIDIA):
    # numa AMD, "cabe na VRAM" nao quer dizer que roda.
    if selo != "nao_roda" and eh_amd(perfil.get("gpu", "")):
        selo, motivo = "nao_testado", "Tested on NVIDIA only; Comfy Cloud is the safe option."
    sem_espaco = disco_livre is not None and faltando_gb > disco_livre
    return {"selo": selo, "motivo": motivo, "sem_espaco": sem_espaco, "medido": req.get("medido", "")}
