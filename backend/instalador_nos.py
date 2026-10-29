"""Instala os nos extras do ComfyUI (catalogo/nos.json) na pasta custom_nodes.

Cada no vem numa versao FIXA, a mesma que o app foi testado: do registro da
Comfy (o mesmo do ComfyUI-Manager), do zip de um commit no GitHub, ou de uma
pasta deste repositorio. Nao precisa de git. Depois de copiar, instala as
dependencias com o Python do proprio ComfyUI. No fim o ComfyUI precisa ser
reiniciado para carregar os nos novos.

Um no que ja existe na pasta nao e tocado: quem ja tem o ComfyUI montado nao
perde a versao que usa.

Quando o app sabe religar o ComfyUI (motores.pode_religar), ele o religa sozinho no
fim, e o desliga no meio se o pip precisar trocar um arquivo que o ComfyUI carregou.
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
import motores

CATALOGO = config.RAIZ / "catalogo" / "nos.json"
ESTADO = {"ativo": False, "atual": None, "feitos": [], "erros": [], "log": "",
          "reiniciar": False, "religado": False, "terminado_em": None}
_tarefa: asyncio.Task | None = None
# Quem chama (app.py) diz se ha geracao em andamento: com uma, o ComfyUI nao e desligado.
_ocupado = lambda: False


class PipFalhou(RuntimeError):
    """O pip terminou com erro. `em_uso`: tentou trocar um arquivo que o ComfyUI ligado
    esta usando (WinError 5 "Acesso negado" / WinError 32), o que se resolve desligando-o."""

    def __init__(self, pasta: str, saida: str):
        self.em_uso = "WinError 5]" in saida or "WinError 32]" in saida
        super().__init__(f"pip failed in {pasta}: {motivo_pip(saida)}")


def motivo_pip(saida: str) -> str:
    """A linha que explica a falha (o pip escreve "ERROR:", ou "ERRO:" em portugues),
    em vez de so o codigo de saida."""
    linhas = [l.strip() for l in saida.splitlines() if l.strip()]
    for l in linhas:
        if l.upper().startswith(("ERROR", "ERRO:")):
            return l[:400]
    uteis = [l for l in linhas if not l.startswith("[")]  # "[notice]"/"[aviso]" do pip
    return (uteis[-1] if uteis else "no output")[:400]


def carregar() -> list[dict]:
    return json.loads(CATALOGO.read_text(encoding="utf-8"))["nos"]


def pasta_nos(no: dict | None = None) -> pathlib.Path | None:
    segundo = (no is not None and no.get("motor") == "segundo"
               and config.COMFY_URL_FLUX3 != config.COMFY_URL)
    raiz = config.COMFY_DIR_FLUX3 if segundo else config.COMFY_CODIGO_DIR
    return raiz / "custom_nodes" if raiz else None


def pacotes_conhecidos() -> set[str]:
    """Os pacotes do Config Models e os que aparecem no catalogo de nos."""
    import pacotes
    return {p["id"] for p in pacotes.carregar()} | {i for n in carregar() for i in n["pacotes"]}


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
    texto = saida.decode("utf-8", "replace")
    ESTADO["log"] = texto[-4000:]
    if proc.returncode != 0:
        raise PipFalhou(pasta.name, texto)


async def _desligar_comfy() -> bool:
    """Desliga o ComfyUI principal se pode; o vigia fica parado ate religar."""
    if not motores.pode_religar() or _ocupado():
        return False
    motores._pausa.set()
    await asyncio.to_thread(motores.desligar)
    return True


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
        try:
            await _dependencias(temporaria, no)
        except PipFalhou as e:
            # Ex.: o LayerStyle troca o OpenCV e o cv2.pyd esta carregado no ComfyUI.
            # Com ele desligado o mesmo pip passa.
            if not e.em_uso or pasta_nos(no) != pasta_nos() or motores._pausa.is_set():
                raise
            ESTADO["atual"] = f"{no['nome']} (closing ComfyUI to replace a file it uses)"
            if not await _desligar_comfy():
                raise RuntimeError(f"{e}. A file ComfyUI is using must be replaced: close ComfyUI, "
                                   "press Install again, then start ComfyUI.") from e
            ESTADO["atual"] = no["nome"]
            await _dependencias(temporaria, no)
        temporaria.replace(final)  # so aparece para o ComfyUI quando completo
    return True


async def _instalar(lista: list[dict]):
    ESTADO.update(ativo=True, feitos=[], erros=[], log="", religado=False, terminado_em=None)
    segundo = False  # no novo no segundo motor: esse o app nao religa
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60, read=300), follow_redirects=True,
                                     verify=config.ssl_sistema()) as c:
            for no in lista:
                ESTADO["atual"] = no["nome"]
                try:
                    if await instalar_um(c, no):
                        ESTADO["feitos"].append(no["nome"])
                        ESTADO["reiniciar"] = True
                        segundo = segundo or pasta_nos(no) != pasta_nos()
                except Exception as e:
                    ESTADO["erros"].append(f"{no['nome']}: {e}")
        # Nos novos so carregam com o ComfyUI religado: o app faz isso em vez de pedir.
        if ESTADO["feitos"] and not segundo and not motores._pausa.is_set():
            ESTADO["atual"] = "restarting ComfyUI"
            await _desligar_comfy()
    finally:
        if motores._pausa.is_set():
            ESTADO["atual"] = "starting ComfyUI"
            try:
                if await asyncio.to_thread(motores.ligar):
                    ESTADO.update(religado=True, reiniciar=segundo)
                else:
                    ESTADO["erros"].append("ComfyUI could not be started again: open EasyComfee from its shortcut.")
            finally:
                motores._pausa.clear()
        ESTADO.update(ativo=False, atual=None, terminado_em=time.time())
        comfy.esquecer_info()


def iniciar(id_pacote: str | None, ocupado=None) -> dict:
    global _tarefa, _ocupado
    if ESTADO["ativo"]:
        raise RuntimeError("Ja ha uma instalacao de nos em andamento.")
    if id_pacote and id_pacote not in pacotes_conhecidos():
        # Antes instalava so os nos da base e respondia como se fosse o pacote.
        raise KeyError(id_pacote)
    lista = para_pacote(id_pacote) if id_pacote else carregar()
    for no in lista:
        raiz = pasta_nos(no)
        if raiz is None or not raiz.is_dir():
            raise RuntimeError(f"Configure a pasta custom_nodes do motor para {no['nome']}.")
    lista = [n for n in lista if not (pasta_nos(n) / n["pasta"]).is_dir()]
    _ocupado = ocupado or (lambda: False)
    _tarefa = asyncio.create_task(_instalar(lista))
    return {"nos": [n["nome"] for n in lista]}
