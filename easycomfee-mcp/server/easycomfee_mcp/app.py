"""Servidor MCP do EasyComfee: a IA do usuario gera imagem, video, musica e voz pelo app.

Funciona com qualquer cliente MCP (Claude, LM Studio, VS Code, Cursor...). Usa so a API
publica do app (porta 8600): as geracoes entram na mesma fila, aparecem na galeria e
respeitam o controle de VRAM. Nunca le nem devolve a chave da Comfy Cloud.

Trava de custo: gerar com custo (API ou GPU da nuvem) so passa se o preco estiver dentro do
limite que o USUARIO definiu no app (padrao 0 = nada pago). A IA nao tem como mudar o limite.
Local e gratis e passa direto.
"""

import asyncio
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
        out["video"] = {"id": "video", "note": "use modelo='video' and modelo_video=<id>",
                        "default": _resumo([v], ("id", "rotulo", "descricao", "duracao_min",
                                                 "duracao_max"))}
        out["video_api"] = [{**m, "paid": True} for m in _resumo(
            d.get("video_api"), ("id", "rotulo", "modos", "duracao_min", "duracao_max"))]
    return _json(out)


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
async def estimate_cost(model: str, prompt: str, options: dict | None = None) -> str:
    """Price of a generation before running it, without sending anything. Returns
    {'type': 'free'|'api'|'gpu'|'unknown', usd...}. Local generation is free. Tell the
    user the number. `options` are extra fields of
    the request (e.g. {"modelo_video": "ltx23", "duracao_video": 5})."""
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
async def generate(model: str, prompt: str, options: dict | None = None,
                   wait: bool = True, timeout_s: int = ESPERA_MAX) -> str:
    """Generate with a model id from list_models. Free local jobs run at once. A job that
    costs credits runs ONLY if its price is within the spending limit the user set in the
    EasyComfee app (Config Models -> Connect your AI); otherwise it is refused and you must
    tell the user the price and that they can raise the limit there. You cannot change the
    limit and must not try to work around a refusal: pick a free local model or stop.
    It waits up to ~40 s; if the image is not ready it returns state 'na_fila' or
    'executando' with a job_id: then call job_status(job_id) until state is 'pronto' (do not
    start the job again). wait=false returns the job id at once. Files are saved under
    ~/EasyComfee-mcp and appear in the app gallery."""
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
async def job_status(job_id: str, wait_s: int = 30) -> str:
    """State of a job from generate. Waits up to wait_s seconds (max 40) for it to finish;
    when done, the files are saved to ~/EasyComfee-mcp and their paths returned. If it is
    still running, call this again with the same job_id."""
    return _json(await _fim(job_id, wait_s))


@mcp.tool()
async def list_jobs(limit: int = 10) -> str:
    """The most recent jobs: id, model, state, prompt."""
    ts = (await _req("GET", "/api/tarefas", timeout=20)).json()[:max(1, min(limit, 50))]
    return _json([{"id": t["id"], "model": t.get("modelo"), "state": t["estado"],
                   "prompt": (t.get("prompt") or "")[:120]} for t in ts])


@mcp.tool()
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
