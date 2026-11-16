"""Botao Update: confere se o repositorio publicado tem commits novos e aplica.

So funciona numa instalacao feita com `git clone` do GitHub (o README manda
instalar assim). Em qualquer outra pasta (copia sem .git, ou origin apontando
para outro lugar, como a pasta de desenvolvimento) o botao nem aparece: puxar
de uma origem desconhecida poderia trocar o app por outro codigo.

Aplicar NAO roda dentro do servidor: grava e abre `atualizar.bat` numa janela
propria e o servidor sai. O .bat espera o servidor fechar, faz `git pull
--ff-only`, reinstala as dependencias, recompila a interface e chama start.bat.
A chave, a galeria, o config.json e os modelos ficam fora do git e nao mudam.
"""
import os
import pathlib
import subprocess
import sys
import time

import httpx

import config

RAIZ = config.RAIZ
# Origem aceita alem do GitHub (so para testar o fluxo com um repositorio local).
ORIGEM_EXTRA = config._valor("atualizar_de")
_CACHE: dict = {"quando": 0.0, "dados": None}
# Sem internet a resposta vale pouco: assim que a conexao volta, a novidade aparece.
VALIDADE, VALIDADE_SEM_INTERNET = 3600, 120  # 1 h (decidido em 03/11/2026, depois do teste com 5 min)
SEM_INTERNET = ("No internet connection. Connect to the internet and press Update again. "
                "Nothing was changed.")


class SemInternet(RuntimeError):
    pass


def _eh_falta_de_rede(texto: str) -> bool:
    """O git diz de varios jeitos que nao chegou ao GitHub."""
    t = texto.lower()
    return any(s in t for s in ("could not resolve host", "unable to access", "failed to connect",
                                "timed out", "connection was reset", "connection reset", "network is unreachable",
                                "could not connect", "unable to connect", "no route to host"))


def _git(*args: str, timeout: float = 60) -> str:
    r = subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, timeout=timeout,
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip()[:300])
    return r.stdout.strip()


def _origem_valida(url: str) -> bool:
    url = url.strip().rstrip("/")
    if ORIGEM_EXTRA and url == ORIGEM_EXTRA.strip().rstrip("/"):
        return True
    return url.startswith(("https://github.com/", "git@github.com:"))


# ---- Instalacao pelo .zip (Code > Download ZIP), sem .git (16/11/2026) -------------
# O zip do GitHub troca "$Format:%H$" de versao_publicada.txt pelo commit (export-subst,
# no .gitattributes). Com isso o app sabe a versao e pergunta a API do GitHub quantos
# commits novos ha. Para aplicar, o .bat baixa o zip novo e o copia por cima da pasta:
# a chave, a galeria, o config.json e os modelos nao vem no zip e ficam como estao.
REPO = "sintetizacom/easycomfee"
RAMO = "main"
ARQ_VERSAO = RAIZ / "backend" / "versao_publicada.txt"


def versao_do_zip() -> str:
    """O commit gravado pelo zip do GitHub; vazio fora de um zip (o texto fica "$Format:%H$")."""
    try:
        t = ARQ_VERSAO.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return ""
    return t if len(t) == 40 and all(c in "0123456789abcdef" for c in t) else ""


def _novos_no_github(sha: str) -> int:
    """Commits do ramo publicado que esta versao nao tem (API publica do GitHub)."""
    r = httpx.get(f"https://api.github.com/repos/{REPO}/compare/{sha}...{RAMO}", timeout=30,
                  headers={"Accept": "application/vnd.github+json", "User-Agent": "EasyComfee-update"})
    r.raise_for_status()
    return int(r.json().get("ahead_by") or 0)


def estado(forcar: bool = False) -> dict:
    """{"disponivel": bool, "novos": n, "versao": sha curto, "motivo": texto}.
    Consulta o GitHub no maximo a cada 1 h (git fetch), salvo forcar."""
    validade = VALIDADE_SEM_INTERNET if (_CACHE["dados"] or {}).get("sem_internet") else VALIDADE
    if not forcar and _CACHE["dados"] and time.time() - _CACHE["quando"] < validade:
        return _CACHE["dados"]
    dados = {"disponivel": False, "novos": 0, "versao": "", "motivo": "", "sem_internet": False}
    try:
        if not (RAIZ / ".git").exists():
            sha = versao_do_zip()
            if not sha:
                dados["motivo"] = "not a git install"
            else:
                dados.update(versao=sha[:7], zip=True)
                dados["novos"] = _novos_no_github(sha)
                dados["disponivel"] = dados["novos"] > 0
        elif not _origem_valida(_git("remote", "get-url", "origin")):
            dados["motivo"] = "origin is not the published repository"
        else:
            dados["versao"] = _git("rev-parse", "--short", "HEAD")
            _git("fetch", "--quiet", "origin", timeout=120)
            dados["novos"] = int(_git("rev-list", "--count", "HEAD..@{u}") or 0)
            dados["disponivel"] = dados["novos"] > 0
    except (subprocess.TimeoutExpired, httpx.TransportError):
        dados.update(motivo=SEM_INTERNET, sem_internet=True)
    except Exception as e:  # sem git, sem rede, sem upstream: so nao oferece
        dados["motivo"] = str(e)[:200]
        if _eh_falta_de_rede(str(e)):
            dados.update(motivo=SEM_INTERNET, sem_internet=True)
    _CACHE.update(quando=time.time(), dados=dados)
    return dados


BAT = r"""@echo off
REM Gerado pelo botao Update do EasyComfee. Pode fechar esta janela quando o app abrir.
cd /d "%~dp0"
title EasyComfee update
echo Waiting for the studio to close...
REM ping espera ~4 s em qualquer janela (timeout falha quando a entrada nao e um teclado).
ping -n 5 127.0.0.1 >nul
echo.
echo Checking the internet connection...
git ls-remote --heads origin >nul 2>nul || goto sem_internet
echo.
echo Downloading the new version...
REM Rede instavel (WinError 10054, "connection reset"): tenta de novo antes de desistir.
REM Sem nada novo, o git pull so diz "Already up to date": rodar este .bat de novo termina o que faltou.
REM Arquivos do app editados a mao (ou por outro programa) travam o git pull. Eles ficam
REM guardados no "git stash" (nada se perde: "git stash pop" traz de volta) e a versao nova entra.
git diff --quiet HEAD -- || (echo Saving your local edits to the app files with "git stash"... & git stash push -q -m "EasyComfee: local edits before update" || goto erro)
set N=0
:pull
git pull --ff-only && goto pip
set /a N+=1
if %N% geq 3 goto erro
echo Connection problem. Trying again...
ping -n 6 127.0.0.1 >nul
goto pull
:pip
echo.
echo Updating Python packages...
set N=0
:pip_de_novo
backend\.venv\Scripts\python.exe -m pip install -q --retries 10 --timeout 60 -r backend\requirements.txt && goto interface
set /a N+=1
if %N% geq 3 goto erro
echo Connection problem. Trying again...
ping -n 6 127.0.0.1 >nul
goto pip_de_novo
:interface
echo.
echo Building the interface...
pushd frontend
call npm ci --no-audit --no-fund || call npm ci --no-audit --no-fund || (popd & goto erro)
call npm run build || (popd & goto erro)
popd
echo.
REM Atalho com o icone da marca (cria ou atualiza; quem instalou antes dele ganha agora).
call "%~dp0criar-atalho.bat" >nul 2>nul
echo Update done. EasyComfee is starting in a new window; this one closes by itself.
echo (If it stays open, you can close it.)
REM O app volta numa janela minimizada (fechar ela desliga o estudio) e esta
REM janela se fecha (exit sem /b: a janela foi aberta com cmd /c, sugestao de 03/11/2026).
REM Caminho completo: depois do npm, "start.bat" sozinho nao e encontrado.
start "EasyComfee" /min cmd /c ""%~dp0start.bat" noopen"
ping -n 4 127.0.0.1 >nul
exit 0
:sem_internet
echo.
echo No internet connection. Nothing was changed.
echo Connect to the internet, then double-click atualizar.bat in this folder
echo (or open EasyComfee with start.bat and press Update again).
pause
start "EasyComfee" /min cmd /c ""%~dp0start.bat" noopen"
exit /b 1
:erro
echo.
echo The update did not finish. Nothing of yours was deleted.
echo Usually the internet connection dropped. Double-click atualizar.bat in this folder
echo to try again (it continues from where it stopped), then start.bat opens the studio.
pause
exit /b 1
"""


SH = r"""#!/bin/bash
# Gerado pelo botao Update do EasyComfee. Pode fechar esta janela quando o app abrir.
cd "$(dirname "$0")" || exit 1
echo "Waiting for the studio to close..."
sleep 4
echo; echo "Checking the internet connection..."
if ! git ls-remote --heads origin >/dev/null 2>&1; then
  echo; echo "No internet connection. Nothing was changed."
  echo "Connect to the internet, then double-click atualizar.command in this folder"
  echo "(or open EasyComfee and press Update again)."
  read -r -p "Press Enter to continue..." _
  nohup ./start.command noopen >/dev/null 2>&1 &
  exit 1
fi
erro() {
  echo; echo "The update did not finish. Nothing of yours was deleted."
  echo "Usually the internet connection dropped. Double-click atualizar.command in this folder"
  echo "to try again (it continues from where it stopped), then start.command opens the studio."
  read -r -p "Press Enter to close..." _
  exit 1
}
tentar() { for n in 1 2 3; do "$@" && return 0; echo "Connection problem. Trying again..."; sleep 5; done; return 1; }
echo; echo "Downloading the new version..."
# Arquivos do app editados a mao travam o git pull: vao para o "git stash" (nada se perde).
git diff --quiet HEAD -- || { echo 'Saving your local edits to the app files with "git stash"...'; git stash push -q -m "EasyComfee: local edits before update" || erro; }
tentar git pull --ff-only || erro
echo; echo "Updating Python packages..."
tentar backend/.venv/bin/python -m pip install -q --retries 10 --timeout 60 -r backend/requirements.txt || erro
echo; echo "Building the interface..."
( cd frontend && { npm ci --no-audit --no-fund || npm ci --no-audit --no-fund; } && npm run build ) || erro
chmod +x ./*.command 2>/dev/null
./criar-atalho.command >/dev/null 2>&1
echo; echo "Update done. EasyComfee is starting in the background; you can close this window."
nohup ./start.command noopen >> logs/servidor.log 2>&1 &
sleep 3
exit 0
"""


# Mesmo .bat do git, trocando a conferencia de rede e o "git pull" por baixar e copiar o zip.
URL_ZIP = f"https://codeload.github.com/{REPO}/zip/refs/heads/{RAMO}"
BAT_ZIP = BAT[:BAT.index("echo Checking the internet connection...")] + r"""echo Downloading the new version...
set TMPZ=%TEMP%\easycomfee-update
if exist "%TMPZ%" rmdir /s /q "%TMPZ%"
mkdir "%TMPZ%"
set N=0
:baixar
curl.exe -fsSL --retry 3 -o "%TMPZ%\novo.zip" "URL_ZIP" && goto abrir
set /a N+=1
if %N% geq 3 goto sem_internet
echo Connection problem. Trying again...
ping -n 6 127.0.0.1 >nul
goto baixar
:abrir
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%TMPZ%\novo.zip' -DestinationPath '%TMPZ%\x' -Force" || goto erro
REM O zip tem uma pasta so (easycomfee-main): o conteudo dela vai por cima desta pasta.
for /d %%D in ("%TMPZ%\x\*") do robocopy "%%D" "%~dp0." /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto erro
rmdir /s /q "%TMPZ%"
""".replace("URL_ZIP", URL_ZIP) + BAT[BAT.index(":pip\n"):]

SH_ZIP = SH[:SH.index('echo; echo "Checking the internet connection..."')] + r"""erro() {
  echo; echo "The update did not finish. Nothing of yours was deleted."
  echo "Usually the internet connection dropped. Open EasyComfee and press Update again."
  read -r -p "Press Enter to close..." _
  exit 1
}
tentar() { for n in 1 2 3; do "$@" && return 0; echo "Connection problem. Trying again..."; sleep 5; done; return 1; }
echo; echo "Downloading the new version..."
TMPZ="$(mktemp -d)"
tentar curl -fsSL -o "$TMPZ/novo.zip" "URL_ZIP" || erro
unzip -q "$TMPZ/novo.zip" -d "$TMPZ/x" || erro
cp -R "$TMPZ"/x/*/. ./ || erro
rm -rf "$TMPZ"
""".replace("URL_ZIP", URL_ZIP) + SH[SH.index('echo; echo "Updating Python packages..."'):]


def aplicar() -> None:
    """Grava atualizar.bat (Mac: atualizar.command), abre numa janela propria e encerra este servidor."""
    agora = estado(forcar=True)
    if agora["sem_internet"]:
        raise SemInternet(SEM_INTERNET)
    if not agora["disponivel"]:
        raise RuntimeError("no update available")
    if sys.platform == "darwin":
        caminho = RAIZ / "atualizar.command"
        caminho.write_text(SH_ZIP if agora.get("zip") else SH, encoding="utf-8")
        caminho.chmod(0o755)
        subprocess.Popen(["open", "-a", "Terminal", str(caminho)], cwd=RAIZ)
        return
    caminho = RAIZ / "atualizar.bat"
    caminho.write_text((BAT_ZIP if agora.get("zip") else BAT).replace("\n", "\r\n"), encoding="ascii")
    # "start" com um .bat abre "cmd /k" (a janela ficava aberta); com "cmd /c" ela fecha no fim.
    subprocess.Popen(["cmd", "/c", "start", "EasyComfee update", "cmd", "/c", str(caminho)], cwd=RAIZ,
                     creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))


def encerrar_em(segundos: float) -> None:
    """Sai do processo depois da resposta HTTP ir embora (o .bat espera isso)."""
    import threading
    threading.Timer(segundos, lambda: os._exit(0)).start()
