# -*- coding: utf-8 -*-
"""Executa testes puros e, opcionalmente, o que depende de coisa no ar.

    (sem bandeira)   so contratos puros — nao precisa de nada rodando
    --site           + confere o SITE no ar contra o codigo-fonte (rapido)
    --integracao     + monta os grafos e confere contra o ComfyUI vivo
    --smoke          + tudo acima, mais inferencias reais na placa

`--site` existe desde 22/09/2026 e e barato: sobe nada, so pergunta. Ver o
cabecalho de vivo_site.py para a historia de por que ele foi preciso.
"""
import pathlib
import subprocess
import sys


def main():
    pasta = pathlib.Path(__file__).resolve().parent
    # Os contratos puros (test_*.py) rodam todos pelo pytest: alguns arquivos
    # so tem testes no formato do pytest (tmp_path, monkeypatch) e, rodados
    # como script, davam ModuleNotFoundError ou passavam sem testar nada.
    print("\n== testes puros (pytest) ==", flush=True)
    import importlib.util
    if importlib.util.find_spec("pytest") is None:
        # A instalacao do app nao traz o pytest (requirements.txt e so o que o app usa).
        print("pytest nao esta instalado. Rode, na pasta backend:\n"
              "    .venv\\Scripts\\python -m pip install -r requirements-dev.txt")
        return 1
    puros = subprocess.run([sys.executable, "-m", "pytest", str(pasta), "-q",
                            "-p", "no:cacheprovider"], cwd=pasta.parent, check=False)
    falhas = ["testes puros (pytest)"] if puros.returncode else []
    testes = []
    # Vem ANTES dos pesados: se o site no ar estiver defasado, saber disso
    # custa um segundo e muda o que os outros resultados significam.
    if "--site" in sys.argv or "--smoke" in sys.argv:
        testes.append(pasta / "vivo_site.py")
    if "--integracao" in sys.argv or "--smoke" in sys.argv:
        testes.append(pasta / "integracao_comfy.py")
    if "--smoke" in sys.argv:
        testes.append(pasta / "smoke_comfy.py")
    for teste in testes:
        print(f"\n== {teste.name} ==", flush=True)
        resultado = subprocess.run([sys.executable, str(teste)], check=False)
        if resultado.returncode:
            falhas.append(teste.name)
    if falhas:
        print("\nFalharam:", ", ".join(falhas))
        return 1
    print(f"\nTestes puros e {len(testes)} verificacoes extras passaram")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
