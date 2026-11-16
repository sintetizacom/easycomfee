"""Registra o EasyComfee MCP nos apps de IA do PC (LM Studio, Claude Desktop, Cursor).

So acrescenta a entrada "easycomfee", mantem os outros servidores e guarda uma copia .bak
do arquivo antes. EASYCOMFEE_TESTE_HOME troca a pasta do usuario (testes).
Uso: escrever_config.py [--registrar "LM Studio,Claude Desktop"] [--mostrar]
"""
import json
import os
import pathlib
import shutil
import sys

PASTA = pathlib.Path(__file__).resolve().parent
NOME = "easycomfee"
ENTRADA = {
    "command": str(PASTA / ".venv" / "Scripts" / "python.exe"),
    "args": ["-m", "easycomfee_mcp"],
    "env": {"PYTHONPATH": str(PASTA), "EDITOR_URL": "http://127.0.0.1:8600"},
}


def texto_config() -> str:
    return json.dumps({"mcpServers": {NOME: ENTRADA}}, indent=2)


def clientes() -> list[tuple[str, pathlib.Path]]:
    """Os clientes MCP instalados neste PC e o arquivo de configuracao de cada um."""
    teste = os.environ.get("EASYCOMFEE_TESTE_HOME")
    casa = pathlib.Path(teste or pathlib.Path.home())
    roaming = casa / "AppData" / "Roaming" if teste else pathlib.Path(
        os.environ.get("APPDATA") or casa / "AppData" / "Roaming")
    achados = []
    if (casa / ".lmstudio").is_dir():
        achados.append(("LM Studio", casa / ".lmstudio" / "mcp.json"))
    if (roaming / "Claude").is_dir():
        achados.append(("Claude Desktop", roaming / "Claude" / "claude_desktop_config.json"))
    if (casa / ".cursor").is_dir():
        achados.append(("Cursor", casa / ".cursor" / "mcp.json"))
    return achados


def registrar(arquivo: pathlib.Path) -> str:
    dados = {}
    if arquivo.exists():
        texto = arquivo.read_text(encoding="utf-8").strip()
        if texto:
            dados = json.loads(texto)  # JSON quebrado: para aqui e nao estraga nada
        shutil.copy2(arquivo, arquivo.with_name(arquivo.name + ".bak"))
    servidores = dados.setdefault("mcpServers", {})
    acao = "updated" if NOME in servidores else "added"
    servidores[NOME] = ENTRADA
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(dados, indent=2), encoding="utf-8")
    return acao


def registrado(arquivo: pathlib.Path) -> bool:
    try:
        return NOME in json.loads(arquivo.read_text(encoding="utf-8")).get("mcpServers", {})
    except (OSError, ValueError, AttributeError):
        return False


def main():
    if "--registrar" in sys.argv:
        pedidos = sys.argv[sys.argv.index("--registrar") + 1].split(",")
        for nome, arquivo in clientes():
            if nome in pedidos:
                print(f"{nome}: {registrar(arquivo)}")
        return
    print(texto_config())


if __name__ == "__main__":
    main()
