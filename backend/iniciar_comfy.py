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


def main() -> None:
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
               f'--listen 127.0.0.1 --port {porta} --disable-auto-launch --enable-cors-header {app}')
    subprocess.Popen(f'start "ComfyUI" /min cmd /c "{comando}"', shell=True, cwd=pasta)
    print("Starting ComfyUI (minimized window \"ComfyUI\")...")


if __name__ == "__main__":
    main()
