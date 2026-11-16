"""Servidor MCP do EasyComfee: a IA do usuario gera imagem, video, musica e voz pelo app.

Funciona com qualquer cliente MCP (Claude, LM Studio, VS Code, Cursor...). Usa so a API
publica do app (porta 8600): as geracoes entram na mesma fila, aparecem na galeria e
respeitam o controle de VRAM. Nunca le nem devolve a chave da Comfy Cloud.

Trava de custo: gerar com custo (API ou GPU da nuvem) so passa se o preco estiver dentro do
limite que o USUARIO definiu no app (padrao 0 = nada pago). A IA nao tem como mudar o limite.
Local e gratis e passa direto.
"""

import asyncio
import functools
import json
import os
import pathlib
import time

import httpx
from mcp.server.mcpserver import MCPServer

BASE = os.environ.get("EDITOR_URL", "http://127.0.0.1:8600")
SAIDA = pathlib.Path(os.environ.get("EASYCOMFEE_MCP_OUTPUT",
                                    pathlib.Path.home() / "EasyComfee-mcp"))
FIM = {"pronto", "erro"}
# Quanto uma chamada espera antes de devolver o job_id. Os clientes MCP (LM Studio, Codex...)
# desistem de uma chamada parada por cerca de um minuto, e o job continua no app.
ESPERA_MAX = 40
ATIVAS = {"na_fila", "preparando", "submetendo", "executando"}


class ErroApp(RuntimeError):
    pass


def legivel(fn):
    """A biblioteca MCP troca qualquer excecao por 'Error executing tool', e o modelo nunca ve o
    motivo (app fechado, arquivo que nao e imagem...). Os erros nossos voltam como texto."""
    @functools.wraps(fn)
    async def envolta(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except ErroApp as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)
    return envolta


async def _req(metodo, caminho, timeout=60.0, **kw):
    try:
        async with httpx.AsyncClient(base_url=BASE, timeout=timeout) as c:
            r = await c.request(metodo, caminho, **kw)
    except httpx.ConnectError:
        raise ErroApp(f"EasyComfee is not answering at {BASE}. Open it from its shortcut "
                      "(or start.bat) and try again.") from None
    if r.status_code >= 400:
        try:
            detalhe = r.json().get("detail", r.text)
        except ValueError:
            detalhe = r.text
        raise ErroApp(f"EasyComfee answered {r.status_code} on {caminho}: {str(detalhe)[:800]}")
    return r


def _json(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1)


mcp = MCPServer(
    "easycomfee",
    instructions=(
        "Generates images, videos, music and voice with EasyComfee, a creative studio on "
        "ComfyUI that runs on the user's GPU (free) or on Comfy Cloud (credits). Call "
        "list_models first to see the model ids, then generate. Prefer free local models. "
        "Paid jobs only run within a spending limit that the user sets in the app (off by "
        "default); if generate refuses one, tell the user the price and stop or use a free "
        "model. Never try to get around the limit. Never guess a model id."),
)


def _resumo(lista, campos):
    return [{c: m[c] for c in campos if c in m} for m in lista or []]


@mcp.tool()
@legivel
async def status() -> str:
    """Is EasyComfee running, which engine is active (local GPU or Comfy Cloud), and what
    is generating now."""
    saude = (await _req("GET", "/api/saude", timeout=10)).json()
    motor = (await _req("GET", "/api/motor", timeout=10)).json()
    tarefas = (await _req("GET", "/api/tarefas", timeout=20)).json()
    return _json({
        "engine": motor.get("modo"), "cloud_key_set": motor.get("chave_nuvem"),
        "queue": saude.get("na_fila"), "busy": any(t.get("estado") in ATIVAS for t in tarefas),
        "running": [{"id": t["id"], "model": t.get("modelo"), "state": t["estado"],
                     "progress": t.get("progresso")} for t in tarefas if t.get("estado") in ATIVAS]})


@mcp.tool()
@legivel
async def list_models(kind: str = "all") -> str:
    """The model ids you can pass to generate. kind: 'image' (text to image, local and
    cloud), 'edit' (edit images with references), 'video' (video generators) or 'all'.
    A model marked paid=true is an API model and costs credits on Comfy Cloud."""
    d = (await _req("GET", "/api/modelos", timeout=60)).json()
    out = {}
    if kind in ("image", "all"):
        out["image_local"] = _resumo(d.get("modelos"), ("id", "rotulo", "descricao"))
        out["image_cloud_api"] = [{**m, "paid": True} for m in _resumo(
            d.get("nuvem"), ("id", "rotulo", "descricao", "preco_usd", "max_referencias"))]
    if kind in ("edit", "all"):
        out["edit"] = _resumo(d.get("edicao"), (
            "id", "rotulo", "descricao", "min_referencias", "max_referencias"))
    if kind in ("video", "all"):
        v = d.get("video") or {}
        out["video_how_to"] = ("generate(model='video', options={'modelo_video': <id>, "
                               "'modo_video': <mode>, 'duracao_video': <seconds>, "
                               "'referencias': [names from upload_reference]}). Modes: texto "
                               "(text only), imagem (first frame = 1 reference), "
                               "primeiro_ultimo (first and last frame = 2), referencia.")
        out["video_local_and_cloud"] = [
            {c: g[c] for c in ("id", "rotulo", "modos", "duracao_min", "duracao_max", "nuvem")
             if c in g} for g in v.get("geradores", [])]
        out["video_api"] = [{**m, "paid": True} for m in _resumo(
            d.get("video_api"), ("id", "rotulo", "modos", "duracao_min", "duracao_max"))]
    return _json(out)


LIMITE_IMAGEM = 40 * 1024 * 1024  # o mesmo teto do app
EXT_IMAGEM = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".webp": "image/webp"}


def _eh_imagem(cabeca: bytes) -> bool:
    """Confere os primeiros bytes: o app aceita qualquer coisa, e uma 'referencia' que nao e
    imagem seria enviada tal qual (inclusive para a nuvem, num modelo de API)."""
    return (cabeca.startswith(bytes([0x89]) + b"PNG\r\n" + bytes([0x1a]) + b"\n")
            or cabeca.startswith(bytes([0xff, 0xd8, 0xff]))
            or (cabeca[:4] == b"RIFF" and cabeca[8:12] == b"WEBP"))


@mcp.tool()
@legivel
async def upload_reference(path: str) -> str:
    """Send a local IMAGE (png, jpg, webp, up to 40 MB) to EasyComfee so it can be used as a
    reference: to edit it, restyle it, keep a character, or as the first frame of a video.
    `path` is a file on the user's PC (an image they gave you, or one saved earlier in
    ~/EasyComfee-mcp). Returns a `reference` name: pass it in generate's options as
    {"referencias": ["<name>"]}. Non-image files are refused."""
    arquivo = pathlib.Path(path).expanduser()
    if not arquivo.is_file():
        raise ErroApp(f"No such file: {path}")
    if arquivo.suffix.lower() not in EXT_IMAGEM:
        raise ErroApp("Only png, jpg and webp images can be sent as a reference.")
    if arquivo.stat().st_size > LIMITE_IMAGEM:
        raise ErroApp("The image is above 40 MB.")
    dados = arquivo.read_bytes()
    if not _eh_imagem(dados[:16]):
        raise ErroApp("That file is not really a png/jpg/webp image, so it was not sent.")
    r = await _req("POST", "/api/referencia", timeout=300, files={
        "arquivo": (arquivo.name, dados, EXT_IMAGEM[arquivo.suffix.lower()])})
    nome = r.json()["nome"]
    return _json({"reference": nome, "use_it": {"referencias": [nome]},
                  "note": "Put this in generate's options. Check list_models(kind='edit') for "
                          "how many references each model takes."})


def _referencias_cruas(opcoes):
    """Um caminho do PC em `referencias` (em vez do nome devolvido por upload_reference)."""
    ruins = [r for r in (opcoes or {}).get("referencias", []) if not isinstance(r, str)
             or "\\" in r or (len(r) > 1 and r[1] == ":") or r.startswith("/")]
    if not ruins:
        return None
    return {"invalid_references": ruins,
            "hint": "`referencias` takes the names returned by upload_reference, not file "
                    "paths. Call upload_reference(path) for each image, then pass the names. "
                    "Nothing was generated."}


_CAMPOS = {}


async def _campos():
    """Os campos que o app aceita num pedido (do OpenAPI dele). O app ignora em silencio o que
    nao conhece, entao um nome errado (aspect_ratio em vez de proporcao) viraria um padrao."""
    if not _CAMPOS:
        try:
            esquema = (await _req("GET", "/openapi.json", timeout=20)).json()
            props = esquema["components"]["schemas"]["PedidoGeracao"]["properties"]
            _CAMPOS["nomes"] = set(props)
        except (ErroApp, KeyError, ValueError):
            _CAMPOS["nomes"] = set()  # sem o esquema, nao valida
    return _CAMPOS["nomes"]


async def _opcoes_invalidas(opcoes):
    """None se estiver tudo certo; senao a resposta de erro para a IA corrigir e tentar de novo."""
    cruas = _referencias_cruas(opcoes)
    if cruas:
        return cruas
    nomes = await _campos()
    if not nomes or not opcoes:
        return None
    erradas = [k for k in opcoes if k not in nomes]
    if not erradas:
        return None
    import difflib
    return {"invalid_options": {k: difflib.get_close_matches(k, nomes, n=3, cutoff=0.4)
                                for k in erradas},
            "hint": "EasyComfee does not know these option names and would ignore them. "
                    "Use the exact names, e.g. {\"proporcao\": \"16:9\"} for the aspect "
                    "ratio. Nothing was generated; fix the names and call again."}


async def _estimar(modelo, prompt, opcoes):
    pedido = {**(opcoes or {}), "modelo": modelo, "prompt": prompt}
    return pedido, (await _req("POST", "/api/estimar", json=pedido, timeout=120)).json()


def _maximo(est):
    """(custo maximo em USD, conhecido?) da resposta de /api/estimar."""
    tipo = est.get("tipo")
    if tipo == "gratis":
        return 0.0, True
    if tipo == "api":
        return float(est.get("max", 0)), True
    if tipo == "gpu":
        return float(est.get("usd", 0)), True
    return 0.0, False


@mcp.tool()
@legivel
async def estimate_cost(model: str, prompt: str, options: dict | None = None) -> str:
    """Price of a generation before running it, without sending anything. Returns
    {'type': 'free'|'api'|'gpu'|'unknown', usd...}. Local generation is free. Tell the
    user the number. `options` are extra fields of
    the request (e.g. {"modelo_video": "ltx23", "duracao_video": 5})."""
    erro = await _opcoes_invalidas(options)
    if erro:
        return _json(erro)
    _, est = await _estimar(model, prompt, options)
    return _json(est)


async def _limite_usd():
    """O teto de gasto por geracao que o USUARIO definiu no app (0 = nada pago). A IA nao
    tem como mudar isto: nao existe ferramenta nem parametro para isso."""
    try:
        return float((await _req("GET", "/api/ia-mcp/limite", timeout=10)).json()["usd"])
    except (ErroApp, KeyError, ValueError):
        return 0.0  # sem conseguir ler, nada pago


@mcp.tool()
@legivel
async def generate(model: str, prompt: str, options: dict | None = None,
                   wait: bool = True, timeout_s: int = ESPERA_MAX) -> str:
    """Generate with a model id from list_models. Free local jobs run at once. A job that
    costs credits runs ONLY if its price is within the spending limit the user set in the
    EasyComfee app (Config Models -> Connect your AI); otherwise it is refused and you must
    tell the user the price and that they can raise the limit there. You cannot change the
    limit and must not try to work around a refusal: pick a free local model or stop.
    To use images (edit, restyle, keep a character, image-to-video) first call
    upload_reference for each file and pass {"referencias": [names]}. For video use
    model='video' (see list_models kind='video').
    Extra settings go in `options` with the app's exact names, e.g. {"proporcao": "16:9"}
    (also "1:1", "9:16"); unknown names are rejected. The result has the real `size`: report
    that, not what you asked for. It waits up to ~40 s; if the image is not ready it returns state 'na_fila' or
    'executando' with a job_id: then call job_status(job_id) until state is 'pronto' (do not
    start the job again). wait=false returns the job id at once. Files are saved under
    ~/EasyComfee-mcp and appear in the app gallery."""
    erro = await _opcoes_invalidas(options)
    if erro:
        return _json(erro)
    pedido, est = await _estimar(model, prompt, options)
    teto, conhecido = _maximo(est)
    limite = await _limite_usd()
    if not conhecido:
        return _json({"refused": True, "reason": "The cost of this job is unknown "
                      f"({est.get('motivo', '')}), so it cannot be checked against the "
                      "user's spending limit. Use a free local model, or ask the user to "
                      "run it in the app.", "estimate": est})
    if teto > 0 and teto > limite + 1e-9:
        return _json({"refused": True, "reason": (
            f"This job can cost up to US$ {teto:.4f}, above the AI spending limit the user "
            f"set in EasyComfee (US$ {limite:.2f} per generation). Tell the user the price. "
            "Only they can raise the limit, in Config Models -> Connect your AI. Do not "
            "retry; offer a free local model instead."), "estimate": est})
    tarefa = (await _req("POST", "/api/gerar", json=pedido, timeout=120)).json()
    tid = tarefa.get("id") or tarefa.get("tarefa")
    if not tid:
        return _json({"submitted": tarefa})
    if not wait:
        return _json({"job_id": tid, "estimate": est})
    return _json(await _fim(tid, timeout_s))


async def _tarefa(tid):
    for t in (await _req("GET", "/api/tarefas", timeout=20)).json():
        if t.get("id") == tid:
            return t
    raise ErroApp(f"job {tid} is not among the recent EasyComfee jobs")


def _itens(t):
    saidas = []
    for item in t.get("imagens") or []:
        if isinstance(item, str):
            try:
                item = json.loads(item)
            except ValueError:
                item = {"nome": item}
        saidas.append(item)
    return saidas


async def _baixar(item, pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    params = {"nome": item["nome"], "subpasta": item.get("subpasta", ""),
              "tipo": item.get("tipo", "output")}
    r = await _req("GET", "/api/imagem", params=params, timeout=600)
    alvo = pasta / pathlib.Path(item["nome"]).name
    alvo.write_bytes(r.content)
    return str(alvo)


async def _fim(tid, timeout_s):
    limite = time.monotonic() + max(1, min(timeout_s, ESPERA_MAX))
    t = await _tarefa(tid)
    while t.get("estado") not in FIM and time.monotonic() < limite:
        await asyncio.sleep(3)
        t = await _tarefa(tid)
    resp = {"job_id": tid, "state": t.get("estado"), "progress": t.get("progresso"),
            "cost_usd": t.get("custo_usd")}
    if t.get("largura") and t.get("altura"):
        resp["size"] = f"{t['largura']}x{t['altura']}"  # o que saiu de fato; relate este valor
    if t.get("estado") == "erro":
        resp["error"] = (t.get("erro") or "")[:800]
    elif t.get("estado") == "pronto":
        pasta = SAIDA / time.strftime("%Y%m%d")
        resp["files"] = [await _baixar(i, pasta) for i in _itens(t) if i.get("nome")]
    else:
        resp["note"] = ("Still running in EasyComfee, nothing is lost. Call job_status with this "
                        "job_id again (do not start a new job).")
    return resp


@mcp.tool()
@legivel
async def job_status(job_id: str, wait_s: int = 30) -> str:
    """State of a job from generate. Waits up to wait_s seconds (max 40) for it to finish;
    when done, the files are saved to ~/EasyComfee-mcp and their paths returned. If it is
    still running, call this again with the same job_id."""
    return _json(await _fim(job_id, wait_s))


@mcp.tool()
@legivel
async def list_jobs(limit: int = 10) -> str:
    """The most recent jobs: id, model, state, prompt."""
    ts = (await _req("GET", "/api/tarefas", timeout=20)).json()[:max(1, min(limit, 50))]
    return _json([{"id": t["id"], "model": t.get("modelo"), "state": t["estado"],
                   "prompt": (t.get("prompt") or "")[:120]} for t in ts])


@mcp.tool()
@legivel
async def set_engine(mode: str) -> str:
    """Switch the engine: 'local' (your GPU, free) or 'nuvem' (Comfy Cloud, credits;
    needs the key set in the app). Refused while something is generating."""
    if mode not in ("local", "nuvem"):
        raise ErroApp("mode must be 'local' or 'nuvem'")
    tarefas = (await _req("GET", "/api/tarefas", timeout=20)).json()
    if any(t.get("estado") in ATIVAS for t in tarefas):
        raise ErroApp("Something is generating right now. Wait for it to finish.")
    return _json((await _req("POST", "/api/motor", json={"modo": mode}, timeout=60)).json())


def main():
    mcp.run("stdio")
