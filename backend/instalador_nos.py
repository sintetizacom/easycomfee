"""Instala os nos extras do ComfyUI (catalogo/nos.json) na pasta custom_nodes.

Cada no vem numa versao FIXA, a mesma que o app foi testado: do registro da
Comfy (o mesmo do ComfyUI-Manager), do zip de um commit no GitHub, ou de uma
pasta deste repositorio. Nao precisa de git. Depois de copiar, instala as
dependencias com o Python do proprio ComfyUI. No fim o ComfyUI precisa ser
reiniciado para carregar os nos novos.

Um no que ja existe na pasta nao e tocado: quem ja tem o ComfyUI montado nao
perde a versao que usa.
"""
import asyncio
import io
import json
import pathlib
import shutil
import tempfile
import time
import zipfile

import httpx

import comfy
import config

CATALOGO = config.RAIZ / "catalogo" / "nos.json"
ESTADO = {"ativo": False, "atual": None, "feitos": [], "erros": [], "log": "",
          "reiniciar": False, "terminado_em": None}
_tarefa: asyncio.Task | None = None


def carregar() -> list[dict]:
    return json.loads(CATALOGO.read_text(encoding="utf-8"))["nos"]


def pasta_nos(no: dict | None = None) -> pathlib.Path | None:
    segundo = (no is not None and no.get("motor") == "segundo"
               and config.COMFY_URL_FLUX3 != config.COMFY_URL)
    raiz = config.COMFY_DIR_FLUX3 if segundo else config.COMFY_CODIGO_DIR
    return raiz / "custom_nodes" if raiz else None


def para_pacote(id_pacote: str) -> list[dict]:
    """Nos que um pacote de modelo precisa, mais os da base."""
    return [n for n in carregar() if "base" in n["pacotes"] or id_pacote in n["pacotes"]]


def situacao() -> list[dict]:
    return [n | {"instalado": None if (raiz := pasta_nos(n)) is None
                 else (raiz / n["pasta"]).is_dir()} for n in carregar()]


async def _url_zip(c: httpx.AsyncClient, no: dict) -> str:
    if no["fonte"] == "registro":
        r = await c.get(f"https://api.comfy.org/nodes/{no['id']}/versions/{no['versao']}")
        r.raise_for_status()
        return r.json()["downloadUrl"]
    return f"{no['repo']}/archive/{no['commit']}.zip"


def _extrair(dados: bytes, destino: pathlib.Path):
    """Extrai o zip em `destino`, tirando a pasta de topo unica que o GitHub
    poe (repo-commit/) e recusando caminhos que escapem da pasta."""
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        nomes = [n for n in z.namelist() if not n.endswith("/")]
        topos = {n.split("/", 1)[0] for n in z.namelist()}
        prefixo = (next(iter(topos)) + "/") if len(topos) == 1 and all("/" in n for n in nomes) else ""
        for nome in nomes:
            rel = nome[len(prefixo):]
            alvo = (destino / rel).resolve()
            if not alvo.is_relative_to(destino.resolve()):
                raise RuntimeError(f"caminho invalido no zip: {nome}")
            alvo.parent.mkdir(parents=True, exist_ok=True)
            alvo.write_bytes(z.read(nome))


async def _dependencias(pasta: pathlib.Path, no: dict):
    req = pasta / "requirements.txt"
    if not req.exists():
        return
    python = config.COMFY_PYTHON
    if (no.get("motor") == "segundo"
            and config.COMFY_URL_FLUX3 != config.COMFY_URL):
        raiz = config.COMFY_DIR_FLUX3
        python = (raiz / ".venv" / "Scripts" / "python.exe") if raiz else None
    if not python or not python.exists():
        raise RuntimeError("Nao achei o Python do ComfyUI; informe comfy_python no config.json.")
    proc = await asyncio.create_subprocess_exec(
        str(python), "-m", "pip", "install", "-r", str(req),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    saida, _ = await proc.communicate()
    ESTADO["log"] = saida.decode("utf-8", "replace")[-4000:]
    if proc.returncode != 0:
        raise RuntimeError(f"pip falhou em {pasta.name} (codigo {proc.returncode})")


async def instalar_um(c: httpx.AsyncClient, no: dict):
    raiz = pasta_nos(no)
    final = raiz / no["pasta"]
    if final.is_dir():
        return False
    with tempfile.TemporaryDirectory(dir=raiz) as tmp:
        temporaria = pathlib.Path(tmp) / no["pasta"]
        # Copiar e extrair mexem em muitos arquivos: fora do laco de eventos,
        # para o servidor nao parar de responder durante a instalacao.
        if no["fonte"] == "projeto":
            await asyncio.to_thread(shutil.copytree, config.RAIZ / no["origem"], temporaria)
        else:
            r = await c.get(await _url_zip(c, no))
            r.raise_for_status()
            temporaria.mkdir()
            await asyncio.to_thread(_extrair, r.content, temporaria)
        await _dependencias(temporaria, no)
        temporaria.replace(final)  # so aparece para o ComfyUI quando completo
    return True


async def _instalar(lista: list[dict]):
    ESTADO.update(ativo=True, feitos=[], erros=[], log="", terminado_em=None)
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, read=300), follow_redirects=True,
                                     verify=config.ssl_sistema()) as c:
            for no in lista:
                ESTADO["atual"] = no["nome"]
                try:
                    if await instalar_um(c, no):
                        ESTADO["feitos"].append(no["nome"])
                        ESTADO["reiniciar"] = True
                except Exception as e:
                    ESTADO["erros"].append(f"{no['nome']}: {e}")
    finally:
        ESTADO.update(ativo=False, atual=None, terminado_em=time.time())
        comfy.esquecer_info()


def iniciar(id_pacote: str | None) -> dict:
    global _tarefa
    if ESTADO["ativo"]:
        raise RuntimeError("Ja ha uma instalacao de nos em andamento.")
    lista = para_pacote(id_pacote) if id_pacote else carregar()
    for no in lista:
        raiz = pasta_nos(no)
        if raiz is None or not raiz.is_dir():
            raise RuntimeError(f"Configure a pasta custom_nodes do motor para {no['nome']}.")
    lista = [n for n in lista if not (pasta_nos(n) / n["pasta"]).is_dir()]
    _tarefa = asyncio.create_task(_instalar(lista))
    return {"nos": [n["nome"] for n in lista]}
