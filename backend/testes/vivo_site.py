# -*- coding: utf-8 -*-
r"""Confere o SITE RODANDO, nao o codigo-fonte.

Existe por causa de 22/09/2026. Naquele dia a bateria inteira ficou verde —
contratos puros, 35 grafos contra o ComfyUI vivo — enquanto o aplicativo em
127.0.0.1:8600 nao tinha NENHUMA das mudancas. Duas ferramentas novas foram
dadas como entregues sem que estivessem no ar.

A causa e que todos os outros testes fazem `import workflows` e leem o
codigo-fonte. O processo do site, esse, carregou os modulos quando subiu, e o
navegador carregou o bundle que existia quando a pagina abriu. Os tres podem
estar em versoes diferentes, e nada avisa.

Este arquivo fecha essa lacuna, e so ela: nao confere grafo nem qualidade.
Pergunta duas coisas que o resto da bateria nao tem como perguntar:

  1. o BACKEND no ar conhece o que presets.py define?
  2. o BUILD do frontend e mais novo que o codigo-fonte dele?

    backend\.venv\Scripts\python.exe backend\testes\vivo_site.py
"""
import json
import pathlib
import sys
import urllib.error
import urllib.request

RAIZ = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ.parent))

import presets as P     # noqa: E402

SITE = "http://127.0.0.1:8600"
PROJETO = RAIZ.parent.parent
FONTE = PROJETO / "frontend" / "src"
BUILD = PROJETO / "frontend" / "dist"

_falhas = []


def conferir_que(nome, condicao, detalhe=""):
    if not condicao:
        _falhas.append(f"{nome}: falso{(' — ' + detalhe) if detalhe else ''}")


def buscar(caminho, timeout=60):
    with urllib.request.urlopen(SITE + caminho, timeout=timeout) as r:
        return r.read()


def teste_o_backend_no_ar_conhece_o_catalogo_do_codigo():
    """Toda ferramenta definida em presets.EDICAO tem de estar sendo SERVIDA.

    Este e o teste que teria gritado em 22/09: `folha` estava em presets.py e
    ausente de /api/modelos, porque o uvicorn subira antes da edicao.
    """
    catalogo = json.loads(buscar("/api/modelos"))
    servidos = {i["id"] for i in catalogo["edicao"]}
    for chave in P.EDICAO:
        conferir_que(f"/api/modelos serve o modo {chave!r}", chave in servidos,
                     "presets.py define, o site no ar nao conhece — "
                     "reinicie o site (parar.bat e iniciar.bat)")

    # O encadeado e o FastH3 tem o MESMO portao: ambos dependem do checkpoint
    # do FastH3 estar no disco. Entao "um sem o outro" so pode ser defasagem.
    geradores = {g["id"] for g in catalogo["video"]["geradores"]}
    if "fasth3" in geradores:
        conferir_que("o gerador de varios planos acompanha o FastH3",
                     "planos" in geradores,
                     "os dois tem o mesmo portao; falta um = backend velho")
    if "planos" in geradores:
        planos = next(g for g in catalogo["video"]["geradores"]
                      if g["id"] == "planos")
        # A tela decide pela CAPACIDADE. Sem ela declarada, o painel cai no
        # campo de prompt unico e o encadeamento fica inalcancavel.
        conferir_que("o gerador declara max_planos", planos.get("max_planos"),
                     "sem isto a tela nao mostra a lista de planos")


def teste_o_build_do_frontend_nao_esta_atrasado():
    """Nenhum arquivo de frontend/src pode ser mais novo que o build.

    Em 22/09 o build era de 21/09 e a interface nova simplesmente nao existia
    na pagina. `tsc --noEmit` passa sem construir nada, entao ele nao protege
    disto — pelo contrario, da a sensacao de que protege.
    """
    conferir_que("frontend/dist existe", BUILD.is_dir(),
                 "rode: cd frontend && npm run build")
    if not BUILD.is_dir():
        return

    saidas = list(BUILD.rglob("*"))
    arquivos_build = [a for a in saidas if a.is_file()]
    conferir_que("o build tem arquivos", arquivos_build)
    if not arquivos_build:
        return

    mais_novo_build = max(a.stat().st_mtime for a in arquivos_build)
    fontes = [a for a in FONTE.rglob("*") if a.is_file()]
    atrasados = [a.name for a in fontes
                 if a.stat().st_mtime > mais_novo_build]
    conferir_que(
        "o build e mais novo que o codigo-fonte do frontend",
        not atrasados,
        f"mudou depois do ultimo build: {', '.join(sorted(atrasados)[:6])}"
        " — rode: cd frontend && npm run build")


def teste_o_site_entrega_o_bundle_que_esta_no_build():
    """O HTML servido aponta para um arquivo que realmente existe no build.

    Protege do caso em que o build rodou mas o site serve outra pasta, e do
    HTML velho em cache do proprio servidor.
    """
    import re
    html = buscar("/").decode("utf-8", "replace")
    achados = re.findall(r"assets/index-[A-Za-z0-9_-]+\.js", html)
    conferir_que("o HTML servido aponta para um bundle", achados,
                 "nenhum <script> de assets/index-*.js no HTML")
    for caminho in achados:
        conferir_que(f"o bundle {caminho} existe no build",
                     (BUILD / caminho).is_file(),
                     "o site serve um HTML que nao bate com frontend/dist")


def main():
    try:
        buscar("/api/modelos", timeout=15)
    except (urllib.error.URLError, OSError) as erro:
        print(f"o site nao respondeu em {SITE}: {erro}")
        print("suba com iniciar.bat (ou iniciar-oculto.vbs) e rode de novo")
        return 1

    for nome, fn in sorted(globals().items()):
        if nome.startswith("teste_"):
            fn()
    if _falhas:
        print(f"{len(_falhas)} FALHA(S):")
        for falha in _falhas:
            print("  -", falha)
        return 1
    print("o site no ar esta em dia com o codigo-fonte")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
