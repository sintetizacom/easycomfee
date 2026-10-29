"""Acha o ComfyUI da pessoa e preenche o config.json (chamado pelo install.bat).

So biblioteca padrao: roda com o Python do sistema, antes do .venv existir.
Procura, nesta ordem:
  1. ComfyUI Desktop: %APPDATA%\\ComfyUI\\config.json traz "basePath" (a pasta de
     trabalho, com models, custom_nodes, input e output). O servidor dele usa a
     porta 8000.
  2. ComfyUI portatil (ComfyUI_windows_portable\\ComfyUI) e instalacoes manuais:
     uma pasta com main.py, a pasta comfy e a pasta models. Porta 8188.
Sem nenhum: explica, abre comfy.org/download e sai com codigo 2, para o
install.bat parar antes de instalar o resto com um caminho errado.

    python backend/detectar_comfy.py            # preenche o config.json
    python backend/detectar_comfy.py --listar   # so mostra o que achou
"""
import json
import os
import pathlib
import string
import sys
import webbrowser

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config.json"
EXEMPLO = RAIZ / "config.example.json"
DOWNLOAD = "https://www.comfy.org/download"


def _e_comfy(p: pathlib.Path) -> bool:
    return (p / "main.py").is_file() and (p / "comfy").is_dir() and (p / "models").is_dir()


def _desktop() -> list[dict]:
    cfg = pathlib.Path(os.environ.get("APPDATA", "")) / "ComfyUI" / "config.json"
    try:
        base = pathlib.Path(json.loads(cfg.read_text(encoding="utf-8"))["basePath"])
    except (OSError, ValueError, KeyError, TypeError):
        return []
    if not (base / "models").is_dir():
        return []
    return [{"tipo": "ComfyUI Desktop", "pasta": base, "url": "http://127.0.0.1:8000"}]


def _procurar(raiz: pathlib.Path, fundo: int) -> list[pathlib.Path]:
    """Pastas com ComfyUI ate `fundo` niveis abaixo de `raiz` (sem entrar em lixo)."""
    achados, fila = [], [(raiz, 0)]
    pular = {"windows", "program files", "program files (x86)", "programdata", "$recycle.bin",
             "appdata", "node_modules", ".git", ".venv", "venv", "site-packages", "models", "custom_nodes"}
    while fila:
        pasta, n = fila.pop()
        try:
            if _e_comfy(pasta):
                achados.append(pasta)
                continue
            if n >= fundo:
                continue
            for sub in pasta.iterdir():
                if sub.is_dir() and sub.name.lower() not in pular and not sub.name.startswith("."):
                    fila.append((sub, n + 1))
        except OSError:
            continue
    return achados


def candidatos() -> list[dict]:
    achados = []
    # O ComfyUI que o proprio install.bat baixou (instalar_comfy.py) vem primeiro.
    proprio = RAIZ / "ComfyUI" / "ComfyUI_windows_portable" / "ComfyUI"
    if _e_comfy(proprio):
        achados.append({"tipo": "ComfyUI (installed by EasyComfee)", "pasta": proprio,
                        "url": "http://127.0.0.1:8188", "proprio": True})
    achados += _desktop()
    casa = pathlib.Path.home()
    raizes = [(casa, 3), (casa / "Desktop", 3), (casa / "Documents", 3), (casa / "Downloads", 3)]
    raizes += [(pathlib.Path(f"{d}:\\"), 3) for d in string.ascii_uppercase if pathlib.Path(f"{d}:\\").exists()]
    vistos = {str(a["pasta"]).lower() for a in achados}
    for raiz, fundo in raizes:
        for p in _procurar(raiz, fundo):
            if str(p).lower() in vistos:
                continue
            vistos.add(str(p).lower())
            tipo = "ComfyUI portable" if "portable" in str(p).lower() else "ComfyUI"
            achados.append({"tipo": tipo, "pasta": p, "url": "http://127.0.0.1:8188"})
    return achados


def _escolher(achados: list[dict]) -> dict:
    if len(achados) == 1 or not sys.stdin.isatty():
        return achados[0]
    print("\nFound more than one ComfyUI:")
    for i, a in enumerate(achados, 1):
        print(f"  {i}. {a['tipo']}: {a['pasta']}")
    while True:
        try:
            r = input(f"Which one should EasyComfee use? [1-{len(achados)}, Enter = 1]: ").strip() or "1"
        except EOFError:  # janela sem teclado (instalacao automatica): fica a primeira
            r = "1"
        if r.isdigit() and 1 <= int(r) <= len(achados):
            return achados[int(r) - 1]


def _quer_instalar() -> bool:
    print("\nComfyUI was not found on this computer. EasyComfee runs on top of it.")
    try:
        r = input("Install ComfyUI now, inside the EasyComfee folder? (about 2 GB download) [Y/n]: ").strip().lower()
    except EOFError:  # sem teclado (instalacao automatica): instala
        r = "y"
    return r in ("", "y", "yes", "s", "sim")


def main() -> int:
    achados = candidatos()
    if "--listar" in sys.argv:
        for a in achados:
            print(f"{a['tipo']}: {a['pasta']} ({a['url']})")
        return 0 if achados else 2
    if not achados and _quer_instalar():
        import instalar_comfy
        try:
            pasta = instalar_comfy.instalar()
        except Exception as e:  # rede caiu, disco cheio, pacote corrompido
            print(f"\nComfyUI could not be installed: {e}")
            pasta = None
        if pasta:
            achados = [{"tipo": "ComfyUI (installed by EasyComfee)", "pasta": pasta,
                        "url": "http://127.0.0.1:8188", "proprio": True}]
    if not achados:
        print("\nComfyUI was not found on this computer.\n"
              "EasyComfee runs on top of ComfyUI, so install it first:\n"
              f"  {DOWNLOAD}\n"
              "Then run install.bat again. (Already have it in an unusual folder? Set \"comfy_dir\"\n"
              "in config.json to the folder that has main.py and models, and run install.bat again.)")
        try:
            webbrowser.open(DOWNLOAD)
        except Exception:
            pass
        return 2
    a = _escolher(achados)
    dados = {}
    for origem in (EXEMPLO, CONFIG):
        try:
            dados.update(json.loads(origem.read_text(encoding="utf-8-sig")))
        except (OSError, ValueError):
            pass
    atual = pathlib.Path(dados.get("comfy_dir") or "")
    if CONFIG.exists() and dados.get("comfy_dir") and (_e_comfy(atual) or (atual / "models").is_dir()):
        print(f"Using the ComfyUI already set in config.json: {atual}")
        return 0
    dados["comfy_dir"] = a["pasta"].as_posix()
    dados["comfy_url"] = a["url"]
    # So o ComfyUI que o EasyComfee instalou e ligado pelo atalho; os outros sao da pessoa.
    dados["comfy_iniciar"] = bool(a.get("proprio"))
    CONFIG.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Found {a['tipo']} at {a['pasta']}  (saved in config.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
