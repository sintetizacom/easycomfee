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
    if not forcar and _CACHE["dados"] and time.time() - _CACHE["quando"] < 1800:
        return _CACHE["dados"]
    dados = {"disponivel": False, "novos": 0, "versao": "", "motivo": ""}
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
    except Exception as e:  # sem git, sem rede, sem upstream: so nao oferece
        dados["motivo"] = str(e)[:200]
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
echo Downloading the new version...
git pull --ff-only || goto erro
echo.
echo Updating Python packages...
backend\.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt || goto erro
echo.
echo Building the interface...
pushd frontend
call npm ci --no-audit --no-fund || (popd & goto erro)
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
:erro
echo.
echo The update did not finish. Nothing of yours was deleted.
echo Run start.bat to open the studio again, or update by hand with "git pull".
pause
exit /b 1
"""


def aplicar() -> None:
    """Grava atualizar.bat, abre numa janela propria e encerra este servidor."""
    if not estado(forcar=True)["disponivel"]:
        raise RuntimeError("no update available")
    caminho = RAIZ / "atualizar.bat"
    caminho.write_text(BAT.replace("\n", "\r\n"), encoding="ascii")
    subprocess.Popen(["cmd", "/c", "start", "", str(caminho)], cwd=RAIZ,
                     creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))


def encerrar_em(segundos: float) -> None:
    """Sai do processo depois da resposta HTTP ir embora (o .bat espera isso)."""
    import threading
    threading.Timer(segundos, lambda: os._exit(0)).start()
