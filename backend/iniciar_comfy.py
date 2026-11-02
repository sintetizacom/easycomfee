"""Liga o ComfyUI que o proprio EasyComfee instalou (chamado pelo start.bat).

So quando o config.json diz "comfy_iniciar": true (ComfyUI baixado pelo
install.bat, ver instalar_comfy.py) e ele ainda nao responde. O de quem ja tinha
um ("comfy_iniciar": false): acha a porta em que esta aberto, ou o abre do jeito
dele (comfy_da_pessoa); o app nunca o desliga.
Abre numa janela minimizada "ComfyUI" (fechar a janela desliga o ComfyUI).
"""
import json
import os
import re
import pathlib
import subprocess
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent.parent

# Ligado nem sempre bloqueia: num PC de teste (29/10/2026) bloqueou logo apos instalar e,
# horas depois, com ele ainda ligado, o ComfyUI abriu (a Microsoft passou a reconhecer os arquivos).
AVISO_CONTROLE = """
Note: Windows Smart App Control is on. It may block ComfyUI's files ("An Application
Control policy has blocked this file"). This often clears up by itself after a while or
a restart. If ComfyUI keeps failing, see "Smart App Control" in the README.
"""


def controle_inteligente_ligado() -> bool:
    """Smart App Control do Windows 11 ligado (1 = ligado; 0 = desligado; 2 = so avaliando)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\CI\Policy") as chave:
            return winreg.QueryValueEx(chave, "VerifiedAndReputablePolicyState")[0] == 1
    except (ImportError, OSError):
        return False


# ---- ComfyUI de quem ja tinha um (o instalador gravou "comfy_iniciar": false) ----
# 1. Ja aberto em alguma porta comum: grava essa porta no config.json e pronto.
# 2. Fechado: abre o dele do jeito dele (o .bat do portatil, com as opcoes dele, ou o
#    aplicativo Desktop) e grava a porta que ele vai usar. Instalacao manual: so o aviso.
PORTAS = [8188, 8000, *range(8189, 8200), 8001, 8288]


def responde(url: str) -> bool:
    """E um ComfyUI no ar? (/system_stats e do ComfyUI; outro programa na porta nao serve.)"""
    try:
        with urllib.request.urlopen(url + "/system_stats", timeout=1.5) as r:
            return "system" in json.loads(r.read().decode("utf-8", "replace"))
    except (OSError, ValueError):
        return False


def porta_aberta(preferida: str) -> str | None:
    for url in [preferida] + [f"http://127.0.0.1:{p}" for p in PORTAS]:
        if responde(url):
            return url
    return None


def porta_do_bat(bat: pathlib.Path) -> int:
    m = re.search(r"--port[ =](\d+)", bat.read_text(encoding="utf-8", errors="replace"))
    return int(m.group(1)) if m else 8188


def desktop_exe() -> pathlib.Path | None:
    local = pathlib.Path(os.environ.get("LOCALAPPDATA", ""))
    for exe in (local / "Programs" / "ComfyUI" / "ComfyUI.exe",
                local / "Programs" / "@comfyorgcomfyui-electron" / "ComfyUI.exe"):
        if exe.is_file():
            return exe
    return None


def gravar_url(cfg: dict, url: str) -> None:
    antiga = (cfg.get("comfy_url") or "").rstrip("/")
    if antiga == url:
        return
    cfg["comfy_url"] = url
    # O segundo motor so acompanha quando era o mesmo (instalacao publica: um ComfyUI so).
    if not cfg.get("comfy_url_flux3") or cfg["comfy_url_flux3"].rstrip("/") == antiga:
        cfg.pop("comfy_url_flux3", None)
    (RAIZ / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Your ComfyUI is at {url} (saved in config.json).")


def comfy_da_pessoa(cfg: dict) -> None:
    preferida = (cfg.get("comfy_url") or "http://127.0.0.1:8188").rstrip("/")
    achada = porta_aberta(preferida)
    if achada:
        gravar_url(cfg, achada)
        return
    pasta = pathlib.Path(cfg.get("comfy_dir") or ".")
    bats = [pasta.parent / n for n in ("run_nvidia_gpu.bat", "run_nvidia_gpu_fast_fp16_accumulation.bat", "run_cpu.bat")]
    bat = next((b for b in bats if b.is_file()), None)
    if bat:
        gravar_url(cfg, f"http://127.0.0.1:{porta_do_bat(bat)}")
        subprocess.Popen(f'start "ComfyUI" /min cmd /c "{bat.name}"', shell=True, cwd=bat.parent)
        print(f"Starting your ComfyUI ({bat.name}, minimized window \"ComfyUI\")...")
        return
    exe = desktop_exe()
    if exe and cfg.get("comfy_url", "").rstrip("/").endswith(":8000"):
        subprocess.Popen([str(exe)], cwd=exe.parent)
        print("Starting ComfyUI Desktop...")
        return
    print("Open your ComfyUI: EasyComfee connects by itself when it is up.")


def main() -> None:
    # Vale para qualquer ComfyUI local, nao so o que o EasyComfee instalou.
    if controle_inteligente_ligado():
        print(AVISO_CONTROLE)
    try:
        cfg = json.loads((RAIZ / "config.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return
    if cfg.get("comfy_iniciar") is False:
        comfy_da_pessoa(cfg)
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
               '& echo If it says an Application Control policy blocked a file, that is Windows Smart App Control: '
               '& echo try again after a while or a restart, or see Smart App Control in the README. '
               '& pause)')
    subprocess.Popen(f'start "ComfyUI" /min cmd /c "{comando}"', shell=True, cwd=pasta)
    print("Starting ComfyUI (minimized window \"ComfyUI\")...")


if __name__ == "__main__":
    main()
