"""Ligar o ComfyUI junto com o Windows (botao em Config Models).

Um atalho na pasta Inicializar do usuario (shell:startup). Ligar cria o
atalho; desligar o apaga. Aparece tambem no Gerenciador de Tarefas >
Aplicativos de inicializacao, onde pode ser desabilitado. Com o ComfyUI ja
carregado quando a pessoa abre o app, a espera depois de ligar o PC some.

So vale quando o app sabe ligar o ComfyUI:
- aqui (motor gerenciado): o _interno-subir-motor.vbs;
- instalacao publica com "comfy_iniciar": o backend/iniciar_comfy.py.
O ComfyUI que a pessoa ja tinha continua sendo dela: o app nao o liga.
"""
import os
import pathlib
import subprocess
import sys

import config
import motores

PASTA = pathlib.Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs/Startup"
ATALHO = PASTA / "EasyComfee - ComfyUI.lnk"


def _alvo() -> tuple[str, str] | None:
    """(programa, argumentos) que liga o ComfyUI, ou None se o app nao sabe ligar."""
    if motores.RELANCADOR.exists():
        return "wscript.exe", f'//nologo "{motores.RELANCADOR}"'
    if config._valor("comfy_iniciar") in (True, "true", "True", "1"):
        pythonw = pathlib.Path(sys.executable).with_name("pythonw.exe")
        return str(pythonw), f'"{config.RAIZ / "backend" / "iniciar_comfy.py"}"'
    return None


def estado() -> dict:
    alvo = _alvo()
    return {"disponivel": alvo is not None and bool(os.environ.get("APPDATA")),
            "ativo": ATALHO.exists(),
            "motivo": "" if alvo else "Only for the ComfyUI that EasyComfee starts itself."}


def mudar(ativo: bool) -> dict:
    if not ativo:
        ATALHO.unlink(missing_ok=True)
        return estado()
    alvo = _alvo()
    if alvo is None:
        raise RuntimeError("EasyComfee does not start this ComfyUI, so it cannot start it with Windows.")
    programa, argumentos = alvo
    PASTA.mkdir(parents=True, exist_ok=True)
    # O WScript.Shell do proprio Windows cria o .lnk (sem biblioteca extra). Os
    # valores vao por variavel de ambiente: nada de aspas montadas no comando.
    script = ("$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:EC_LNK); "
              "$s.TargetPath = $env:EC_ALVO; $s.Arguments = $env:EC_ARGS; "
              "$s.WorkingDirectory = $env:EC_PASTA; $s.WindowStyle = 7; "
              "$s.Description = 'EasyComfee: start ComfyUI with Windows'; $s.Save()")
    env = {**os.environ, "EC_LNK": str(ATALHO), "EC_ALVO": programa, "EC_ARGS": argumentos,
           "EC_PASTA": str(config.RAIZ)}
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                   env=env, capture_output=True, text=True, timeout=30,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if not ATALHO.exists():
        raise RuntimeError("Windows did not create the startup shortcut.")
    return estado()
