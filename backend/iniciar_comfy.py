"""Liga o ComfyUI que o proprio EasyComfee instalou (chamado pelo start.bat).

So quando o config.json diz "comfy_iniciar": true (ComfyUI baixado pelo
install.bat, ver instalar_comfy.py) e ele ainda nao responde. O ComfyUI de quem
ja tinha um continua sendo dessa pessoa: o app nunca o liga nem desliga.
Abre numa janela minimizada "ComfyUI" (fechar a janela desliga o ComfyUI).
"""
import json
import pathlib
import subprocess
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent.parent

AVISO_CONTROLE = """
WARNING: Windows Smart App Control is ON on this PC.
It blocks the PyTorch/CUDA files that ComfyUI needs ("An Application Control policy
has blocked this file"), and it has no exceptions, so ComfyUI cannot start locally.
To turn it off: Windows Security > App & browser control > Smart App Control settings > Off.
(Windows does not let you turn it back on without reinstalling. Microsoft Defender keeps working.)
"""


def controle_inteligente_ligado() -> bool:
    """Smart App Control do Windows 11 ligado (1 = ligado; 0 = desligado; 2 = so avaliando)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as chave:
            return winreg.QueryValueEx(chave, "VerifiedAndReputablePolicyState")[0] == 1
    except (ImportError, OSError):
        return False


def main() -> None:
    # Vale para qualquer ComfyUI local, nao so o que o EasyComfee instalou.
    if controle_inteligente_ligado():
        print(AVISO_CONTROLE)
    try:
        cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return
    if not cfg.get("comfy_iniciar"):
        return
    url = (cfg.get("comfy_url") or "http://127.0.0.1:8188").rstrip("/")
    try:
        urllib.request.urlopen(url + "/system_stats", timeout=2)
        return  # ja esta no ar
    except OSError:
        pass
    pasta = pathlib.Path(cfg["comfy_dir"]).parent          # ...\ComfyUI_windows_portable
    porta = url.rsplit(":", 1)[-1]
    app = f"http://127.0.0.1:{cfg.get('app_porta', 8600)}"
    comando = (f'cd /d "{pasta}" && .\\python_embeded\\python.exe -s ComfyUI\\main.py --windows-standalone-build '
               f'--listen 127.0.0.1 --port {porta} --disable-auto-launch --enable-cors-header {app}'
               # Se o ComfyUI cair (ex.: "WinError 126 ... c10.dll" sem o Visual C++), a janela
               # fica aberta com o erro em vez de sumir.
               ' || (echo. & echo ComfyUI stopped with an error: read the message above. '
               '& echo If it mentions c10.dll or WinError 126, install https://aka.ms/vs/17/release/vc_redist.x64.exe '
               # Sem ">" nem "&" no texto: dentro do cmd /c eles redirecionariam ou cortariam a linha.
               '& echo If it says an Application Control policy blocked a file, turn off Smart App Control: '
               '& echo Windows Security, App and browser control, Smart App Control settings, Off. '
               '& pause)')
    subprocess.Popen(f'start "ComfyUI" /min cmd /c "{comando}"', shell=True, cwd=pasta)
    print("Starting ComfyUI (minimized window \"ComfyUI\")...")


if __name__ == "__main__":
    main()
