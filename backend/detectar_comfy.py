"""Acha o ComfyUI da pessoa e preenche o config.json (chamado pelo install.bat).

So biblioteca padrao: roda com o Python do sistema, antes do .venv existir.
Procura, nesta ordem:
  1. ComfyUI Desktop: %APPDATA%\\ComfyUI\\config.json traz "basePath" (a pasta de
     trabalho, com models, custom_nodes, input e output). O servidor dele usa a
     porta 8000.
  2. Comfy Desktop (o app novo): %APPDATA%\\Comfy Desktop\\installations.json lista as
     instalacoes e settings.json traz as pastas compartilhadas de modelos, input e
     output. A porta muda (8188, ou outra se estiver ocupada).
  3. Um ComfyUI aberto agora: ele mesmo diz as pastas dele (/internal/folder_paths).
  4. ComfyUI portatil (ComfyUI_windows_portable\\ComfyUI) e instalacoes manuais:
     uma pasta com main.py, a pasta comfy e a pasta models. Porta 8188.
Sem nenhum: oferece colar o caminho da pasta, baixar o ComfyUI portatil ou seguir
so com a Comfy Cloud (comfy_dir vazio). Recusando tudo, abre comfy.org/download e sai com codigo 2,
para o install.bat parar antes de instalar o resto com um caminho errado.

    python backend/detectar_comfy.py            # preenche o config.json
    python backend/detectar_comfy.py --listar   # so mostra o que achou
"""
import json
import os
import pathlib
import string
import sys
import urllib.request
import webbrowser

RAIZ = pathlib.Path(__file__).resolve().parent.parent
CONFIG = RAIZ / "config.json"
EXEMPLO = RAIZ / "config.example.json"
DOWNLOAD = "https://www.comfy.org/download"
# As mesmas de iniciar_comfy.PORTAS (este arquivo so usa a biblioteca padrao).
PORTAS = [8188, 8000, *range(8189, 8200), 8001, 8288]
# Quem ja tinha ComfyUI: o atalho acha a porta dele ou o abre (ver iniciar_comfy.py).
AVISO_DA_PESSOA = ("\nEasyComfee will use this ComfyUI. The shortcut finds it if it is already open,\n"
                   "or opens it for you (portable or Desktop). With a manual install, open it yourself first.")


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


def _ler_json(arquivo: pathlib.Path):
    try:
        return json.loads(arquivo.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return None


def _pasta_do_app() -> pathlib.Path:
    return pathlib.Path(os.environ.get("APPDATA", "")) / "Comfy Desktop"


def _instalacoes_do_app() -> list[dict]:
    lista = _ler_json(_pasta_do_app() / "installations.json")
    return [i for i in lista if isinstance(i, dict)] if isinstance(lista, list) else []


def _na_nuvem(inst: dict) -> bool:
    return inst.get("sourceId") == "cloud" or bool(inst.get("remoteUrl"))


def _porta_do_app(inst: dict) -> int:
    """A porta da ultima vez que o app ligou essa instalacao (comfy-procs); sem ela, a
    padrao. O atalho confere a porta de verdade (iniciar_comfy.porta_aberta)."""
    proc = _ler_json(_pasta_do_app() / "comfy-procs" / f"{inst.get('id')}.json")
    porta = proc.get("port") if isinstance(proc, dict) else None
    return porta if isinstance(porta, int) else 8188


def _comfy_desktop() -> list[dict]:
    """Instalacoes locais do Comfy Desktop. Conferido numa instalacao real (03/11/2026):
    sourceId "standalone", installPath, e o main.py em <installPath>\\ComfyUI."""
    ajustes = _ler_json(_pasta_do_app() / "settings.json")
    ajustes = ajustes if isinstance(ajustes, dict) else {}
    modelos = ajustes.get("modelsDirs")
    # O app liga o ComfyUI com essas pastas, nao com as de dentro da instalacao.
    pastas = {"modelos_dir": modelos[0] if isinstance(modelos, list) and modelos else None,
              "comfy_entrada": ajustes.get("inputDir"), "comfy_saida": ajustes.get("outputDir")}
    pastas = {k: pathlib.Path(v).as_posix() for k, v in pastas.items() if isinstance(v, str) and v}
    achados = []
    for inst in _instalacoes_do_app():
        if _na_nuvem(inst) or inst.get("status", "installed") != "installed":
            continue
        raiz = inst.get("installPath")
        if not raiz and ajustes.get("installDir") and inst.get("name"):
            raiz = pathlib.Path(str(ajustes["installDir"])) / str(inst["name"])
        if not raiz:
            continue
        for p in (pathlib.Path(raiz) / "ComfyUI", pathlib.Path(raiz)):
            if _e_comfy(p):
                achados.append({"tipo": "Comfy Desktop", "pasta": p, "desktop": True, "pastas": pastas,
                                "url": f"http://127.0.0.1:{_porta_do_app(inst)}"})
                break
    return achados


def so_comfy_cloud() -> bool:
    """O Comfy Desktop esta instalado, mas so com a Comfy Cloud (nao tem ComfyUI local)."""
    return any(_na_nuvem(i) for i in _instalacoes_do_app()) and not _comfy_desktop()


def _perguntar(url: str):
    try:
        with urllib.request.urlopen(url, timeout=1.5) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except (OSError, ValueError):
        return None


def _pasta_do_comfy(url: str) -> pathlib.Path | None:
    """A pasta do ComfyUI que responde em `url`. O sys.argv costuma trazer o main.py
    sem caminho completo (portatil e Desktop); por isso vem da pasta models dele."""
    pastas = _perguntar(url + "/internal/folder_paths")
    if not isinstance(pastas, dict):
        return None
    for lista in pastas.values():
        for caminho in lista if isinstance(lista, list) else []:
            p = pathlib.Path(str(caminho))
            for pai in p.parents:
                if pai.name.lower() == "models" and _e_comfy(pai.parent):
                    return pai.parent
    return None


def _comfy_aberto() -> list[dict]:
    achados = []
    for porta in PORTAS:
        url = f"http://127.0.0.1:{porta}"
        estado = _perguntar(url + "/system_stats")
        if isinstance(estado, dict) and "system" in estado:
            pasta = _pasta_do_comfy(url)
            if pasta:
                achados.append({"tipo": "ComfyUI (open now)", "pasta": pasta, "url": url})
    return achados


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


def _sem_repetir(achados: list[dict], novos: list[dict]) -> list[dict]:
    vistos = {str(a["pasta"]).lower() for a in achados}
    saida = []
    for n in novos:
        if str(n["pasta"]).lower() not in vistos:
            vistos.add(str(n["pasta"]).lower())
            saida.append(n)
    return saida


def candidatos() -> list[dict]:
    achados = []
    # O ComfyUI que o proprio install.bat baixou (instalar_comfy.py) vem primeiro.
    proprio = RAIZ / "ComfyUI" / "ComfyUI_windows_portable" / "ComfyUI"
    if _e_comfy(proprio):
        achados.append({"tipo": "ComfyUI (installed by EasyComfee)", "pasta": proprio,
                        "url": "http://127.0.0.1:8188", "proprio": True})
    # O Desktop vem antes do aberto: so ele sabe as pastas compartilhadas de input e output.
    achados += _sem_repetir(achados, _desktop())
    achados += _sem_repetir(achados, _comfy_desktop())
    achados += _sem_repetir(achados, _comfy_aberto())
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


def _sem_comfy() -> str:
    """O que fazer sem ComfyUI local: "pasta", "instalar", "nuvem" ou "parar"."""
    if so_comfy_cloud():
        print("\nComfy Desktop found, but only with Comfy Cloud (no local ComfyUI).")
    else:
        print("\nComfyUI was not found on this computer.")
    print("  1. Install ComfyUI now, inside the EasyComfee folder (about 2 GB download)\n"
          "  2. Continue without ComfyUI and generate only on Comfy Cloud (uses your credits)\n"
          "  3. I already have ComfyUI: type its folder\n"
          "  4. Stop here")
    while True:
        try:
            r = input("What should EasyComfee do? [1-4, Enter = 1]: ").strip() or "1"
        except EOFError:  # sem teclado (instalacao automatica): instala
            r = "1"
        if r in ("1", "2", "3", "4"):
            return {"1": "instalar", "2": "nuvem", "3": "pasta", "4": "parar"}[r]


def pasta_digitada(texto: str) -> pathlib.Path | None:
    """Aceita a pasta com main.py ou uma acima dela (a do portatil, a do Desktop)."""
    p = pathlib.Path(texto.strip().strip('"'))
    return next((c for c in (p, p / "ComfyUI") if _e_comfy(c)), None)


def _pedir_pasta() -> pathlib.Path | None:
    while True:
        try:
            r = input("ComfyUI folder (the one with main.py and models; Enter = cancel): ").strip()
        except EOFError:
            return None
        if not r:
            return None
        pasta = pasta_digitada(r)
        if pasta:
            return pasta
        print("No ComfyUI there: this folder needs main.py, comfy and models.")


def _ler_config() -> dict:
    dados = {}
    for origem in (EXEMPLO, CONFIG):
        lido = _ler_json(origem)
        if isinstance(lido, dict):
            dados.update(lido)
    return dados


def _gravar_config(dados: dict) -> None:
    CONFIG.write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _gravar_so_nuvem() -> None:
    """Sem ComfyUI local: comfy_dir vazio e sem comfy_iniciar (o atalho nao liga nada)."""
    dados = _ler_config()
    dados["comfy_dir"] = ""
    for chave in ("comfy_iniciar", "comfy_desktop", "comfy_saida", "comfy_entrada", "modelos_dir"):
        dados.pop(chave, None)
    _gravar_config(dados)
    print("EasyComfee will use Comfy Cloud only. Connect your Comfy Cloud key in Config Models.")


class _Tee:
    """Mostra na tela e grava em logs/install.log (o relatorio de suporte leva esse arquivo)."""
    def __init__(self, tela, arquivo):
        self.tela, self.arquivo = tela, arquivo
    def write(self, t):
        self.tela.write(t)
        try:
            self.arquivo.write(t); self.arquivo.flush()
        except OSError:
            pass
    def flush(self):
        self.tela.flush()


def main() -> int:
    try:
        (RAIZ / "logs").mkdir(exist_ok=True)
        sys.stdout = _Tee(sys.stdout, open(RAIZ / "logs" / "install.log", "a", encoding="utf-8"))
    except OSError:
        pass
    achados = candidatos()
    print("ComfyUI candidates: " + ("; ".join(f"{a['tipo']}: {a['pasta']}" for a in achados) or "none"))
    if "--listar" in sys.argv:
        for a in achados:
            print(f"{a['tipo']}: {a['pasta']} ({a['url']})")
        return 0 if achados else 2
    escolha = "" if achados else _sem_comfy()
    if escolha == "nuvem":
        _gravar_so_nuvem()
        return 0
    if escolha == "pasta":
        pasta = _pedir_pasta()
        if pasta:
            achados = [{"tipo": "ComfyUI", "pasta": pasta, "url": "http://127.0.0.1:8188"}]
    if escolha == "instalar":
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
    dados = _ler_config()
    atual = pathlib.Path(dados.get("comfy_dir") or "")
    if CONFIG.exists() and dados.get("comfy_dir") and (_e_comfy(atual) or (atual / "models").is_dir()):
        print(f"Using the ComfyUI already set in config.json: {atual}")
        if dados.get("comfy_iniciar") is False:
            print(AVISO_DA_PESSOA)
        return 0
    dados["comfy_dir"] = a["pasta"].as_posix()
    dados["comfy_url"] = a["url"]
    # So o ComfyUI que o EasyComfee instalou e ligado pelo atalho; os outros sao da pessoa.
    dados["comfy_iniciar"] = bool(a.get("proprio"))
    # O ComfyUI que o EasyComfee liga grava as geracoes em <EasyComfee>\output
    # (iniciar_comfy.py passa --output-directory). O da pessoa grava na pasta dele.
    for chave in ("comfy_saida", "comfy_entrada", "modelos_dir", "comfy_desktop"):
        dados.pop(chave, None)
    if a.get("proprio"):
        dados["comfy_saida"] = (RAIZ / "output").as_posix()
    if a.get("desktop"):
        dados["comfy_desktop"] = True
        dados.update(a.get("pastas", {}))
    _gravar_config(dados)
    print(f"Found {a['tipo']} at {a['pasta']}  (saved in config.json)")
    if not a.get("proprio"):
        print(AVISO_DA_PESSOA)
    return 0


if __name__ == "__main__":
    sys.exit(main())
