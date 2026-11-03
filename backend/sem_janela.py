"""Sem janelas piscando: quando o servidor roda sem console (pythonw, pelo atalho escondido),
cada ffmpeg, nvidia-smi ou git que ele chama abria uma janela preta que fechava logo em
seguida (03/11/2026). Aqui todo processo filho ganha CREATE_NO_WINDOW, a menos que o
chamador ja tenha escolhido as flags. Com console (start.bat), nada muda: os filhos usam
o console que ja existe e nao abrem janela."""

import subprocess
import sys


def ligar() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        if ctypes.windll.kernel32.GetConsoleWindow():
            return  # ha console: os filhos herdam e nao piscam
    except Exception:
        return
    original = subprocess.Popen.__init__

    def __init__(self, *args, **kwargs):
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        original(self, *args, **kwargs)

    subprocess.Popen.__init__ = __init__
