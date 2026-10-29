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
import time

import config

RAIZ = config.RAIZ
# Origem aceita alem do GitHub (so para testar o fluxo com um repositorio local).
ORIGEM_EXTRA = config._valor("atualizar_de")
_CACHE: dict = {"quando": 0.0, "dados": None}
# Sem internet a resposta vale pouco: assim que a conexao volta, a novidade aparece.
VALIDADE, VALIDADE_SEM_INTERNET = 1800, 120
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


def estado(forcar: bool = False) -> dict:
    """{"disponivel": bool, "novos": n, "versao": sha curto, "motivo": texto}.
    Consulta o GitHub no maximo a cada 30 min (git fetch), salvo forcar."""
    validade = VALIDADE_SEM_INTERNET if (_CACHE["dados"] or {}).get("sem_internet") else VALIDADE
    if not forcar and _CACHE["dados"] and time.time() - _CACHE["quando"] < validade:
        return _CACHE["dados"]
    dados = {"disponivel": False, "novos": 0, "versao": "", "motivo": "", "sem_internet": False}
    try:
        if not (RAIZ / ".git").exists():
            dados["motivo"] = "not a git install"
        elif not _origem_valida(_git("remote", "get-url", "origin")):
            dados["motivo"] = "origin is not the published repository"
        else:
            dados["versao"] = _git("rev-parse", "--short", "HEAD")
            _git("fetch", "--quiet", "origin", timeout=120)
            dados["novos"] = int(_git("rev-list", "--count", "HEAD..@{u}") or 0)
            dados["disponivel"] = dados["novos"] > 0
    except subprocess.TimeoutExpired:
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
echo Done. Starting EasyComfee...
REM O app volta numa janela minimizada (fechar ela desliga o estudio) e esta
REM janela se fecha. Caminho completo: depois do npm, "start.bat" sozinho nao e encontrado.
start "EasyComfee" /min cmd /c ""%~dp0start.bat" noopen"
exit /b 0
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


def aplicar() -> None:
    """Grava atualizar.bat, abre numa janela propria e encerra este servidor."""
    agora = estado(forcar=True)
    if agora["sem_internet"]:
        raise SemInternet(SEM_INTERNET)
    if not agora["disponivel"]:
        raise RuntimeError("no update available")
    caminho = RAIZ / "atualizar.bat"
    caminho.write_text(BAT.replace("\n", "\r\n"), encoding="ascii")
    subprocess.Popen(["cmd", "/c", "start", "", str(caminho)], cwd=RAIZ,
                     creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))


def encerrar_em(segundos: float) -> None:
    """Sai do processo depois da resposta HTTP ir embora (o .bat espera isso)."""
    import threading
    threading.Timer(segundos, lambda: os._exit(0)).start()
