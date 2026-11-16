"""Sobe o servidor MCP por stdio, lista as ferramentas e chama as que nao geram nada.
Rode com o python de easycomfee-mcp/server/.venv, com o EasyComfee aberto na porta 8600.
Passe --gerar para uma geracao local pequena (so se o motor local estiver livre).
"""
import asyncio
import json
import pathlib
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVIDOR = pathlib.Path(__file__).resolve().parents[1] / "server"


async def main():
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "easycomfee_mcp"],
        env={"PYTHONPATH": str(SERVIDOR), "EDITOR_URL": "http://127.0.0.1:8600"})
    async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        nomes = sorted(t.name for t in (await s.list_tools()).tools)
        print("tools:", nomes)
        assert {"status", "list_models", "estimate_cost", "generate", "job_status",
                "list_jobs", "set_engine"} <= set(nomes)

        async def chamar(nome, **args):
            res = await s.call_tool(nome, args)
            texto = res.content[0].text
            return res.is_error, texto

        erro, t = await chamar("status")
        print("status:", t[:200]); assert not erro
        erro, t = await chamar("list_models", kind="image")
        modelos = json.loads(t)
        print("image_local:", len(modelos["image_local"]), "cloud:", len(modelos["image_cloud_api"]))
        erro, t = await chamar("estimate_cost", model="qwen21", prompt="a red apple")
        print("estimate:", t); assert not erro
        # A trava: um modelo de API sem approved_usd precisa ser recusado.
        pago = modelos["image_cloud_api"][0]["id"]
        erro, t = await chamar("generate", model=pago, prompt="a red apple")
        print("paid without approval ->", t[:300])
        erro, t = await chamar("list_models", kind="audio")
        audio = json.loads(t)
        assert audio["music"] and "voice_how_to" in audio, t
        print("audio models:", [m["id"] for m in audio["music"]])
        for tipo, chave in (("lipsync", "lipsync"), ("genjutsu", "genjutsu")):
            erro, t = await chamar("list_models", kind=tipo)
            assert chave in json.loads(t), t
        with __import__("tempfile").TemporaryDirectory() as d:
            for nome, ferramenta in (("falso.wav", "upload_audio"), ("falso.mp4", "upload_video")):
                falso = pathlib.Path(d) / nome
                falso.write_text("not media")
                erro, t = await chamar(ferramenta, path=str(falso))
                assert "not really" in json.loads(t)["error"], t
        print("audio/video uploads refused when fake: ok")
        # Referencia: so imagem de verdade, e o erro tem de chegar legivel ao modelo.
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            falso = pathlib.Path(d) / "falso.png"
            falso.write_text("not an image")
            erro, t = await chamar("upload_reference", path=str(falso))
            assert "not really" in json.loads(t)["error"], t
            erro, t = await chamar("upload_reference", path=str(pathlib.Path(d) / "nada.png"))
            assert "No such file" in json.loads(t)["error"], t
        erro, t = await chamar("generate", model="krea", prompt="x",
                               options={"referencias": ["C:/pasta/foto.png"]})
        assert "invalid_references" in json.loads(t), t
        print("references: ok")
        if "--gerar" in sys.argv:
            erro, t = await chamar("generate", model="qwen21", prompt="a red apple on a table")
            print("generate:", t[:300]); assert not erro
            r = json.loads(t)
            # A chamada volta em ate ~40 s; se a imagem ainda nao esta pronta, consulta o job.
            while r["state"] not in ("pronto", "erro"):
                erro, t = await chamar("job_status", job_id=r["job_id"], wait_s=30)
                assert not erro
                r = json.loads(t)
                print("job_status:", r["state"], r.get("progress"))
            assert r["state"] == "pronto" and r["files"], r
            print("files:", r["files"])


asyncio.run(main())
