# -*- coding: utf-8 -*-
"""Regressões de acesso local, custo e retomada. Não chama o ComfyUI."""

import asyncio
import json
import pathlib
import sys
import tempfile

import httpx
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import app as A  # noqa: E402
import biblioteca as B  # noqa: E402


async def acesso_local():
    transporte = httpx.ASGITransport(app=A.app)
    async with httpx.AsyncClient(transport=transporte,
                                 base_url="http://127.0.0.1:8600") as c:
        pedido = {"modelo": "krea", "prompt": ""}  # recusa antes da fila
        r = await c.post("/api/gerar", json=pedido,
                         headers={"Origin": "https://site-externo.example"})
        assert r.status_code == 403, r.text
        r = await c.post("/api/gerar", json=pedido,
                         headers={"Origin": "http://127.0.0.1:8600"})
        assert r.status_code == 400, r.text
        r = await c.post("/api/gerar", json=pedido,
                         headers={"Sec-Fetch-Site": "cross-site"})
        assert r.status_code == 403, r.text
        r = await c.post("/api/gerar", json=pedido,
                         headers={"Host": "site-externo.example"})
        assert r.status_code == 403, r.text
    cliente = TestClient(A.app, base_url="http://127.0.0.1:8600")
    try:
        with cliente.websocket_connect(
                "/ws", headers={"Host": "127.0.0.1:8600",
                                 "Origin": "https://site-externo.example"}):
            raise AssertionError("WebSocket externo foi aceito")
    except WebSocketDisconnect as e:
        assert e.code == 1008
    with cliente.websocket_connect(
            "/ws", headers={"Host": "127.0.0.1:8600",
                             "Origin": "http://127.0.0.1:8600"}):
        pass


async def persistencia_e_custo():
    antigo_banco, antigas_tarefas, antiga_fila = B.BANCO, A.TAREFAS, A.FILA
    antigas_funcoes = (A.comfy.esta_vivo, A.comfy.historico,
                       A.comfy.tamanho_imagem, A.comfy.dimensoes_imagem)
    try:
        with tempfile.TemporaryDirectory() as pasta:
            B.BANCO = pathlib.Path(pasta) / "teste.db"
            B.criar_tabelas()
            imagens = [json.dumps({"nome": f"saida-{n}.png", "subpasta": "teste"})
                       for n in (1, 2, 3)]
            with B._conectar() as con:
                for n in (1, 2, 3):
                    con.execute("""INSERT INTO imagens
                        (criada_em, modelo, prompt, prompt_final, arquivo,
                         subpasta, parametros) VALUES (0,'teste','','',?, 'teste','{}')""",
                                (f"saida-{n}.png",))
            assert B.anotar_custo(imagens, 0.1201) == 3
            assert B.gasto_total()["usd"] == 0.1201

            na_fila = A.Tarefa(A.PedidoGeracao(modelo="krea", prompt="teste"))
            incerta = A.Tarefa(A.PedidoGeracao(modelo="krea", prompt="teste"))
            incerta.estado = "submetendo"
            executando = A.Tarefa(A.PedidoGeracao(modelo="krea", prompt="teste"))
            executando.estado = "executando"
            executando.prompt_id = "prompt-recuperado"
            B.salvar_tarefa(na_fila.registro())
            B.salvar_tarefa(incerta.registro())
            B.salvar_tarefa(executando.registro())
            A.TAREFAS = {t.id: A.Tarefa.de_registro(t.registro())
                         for t in (na_fila, incerta, executando)}
            A.FILA = asyncio.Queue()

            async def vivo():
                return True

            consultas = 0

            async def historico(_):
                nonlocal consultas
                consultas += 1
                if consultas == 1:
                    # O ComfyUI pode deixar /history sem resposta enquanto um
                    # modelo pesado monopoliza a GPU. Isso deve ser polling
                    # transitório, não erro da geração.
                    raise httpx.ReadTimeout("", request=httpx.Request("GET", "http://motor/history"))
                return {"status": {"status_str": "success"},
                        "outputs": {"salva": {"images": [
                            {"filename": "recuperada.png", "subfolder": "teste",
                             "type": "output"}]}}}

            async def tamanho(*_):
                return 1234

            async def dimensoes(*_):
                return 256, 256

            A.comfy.esta_vivo = vivo
            A.comfy.historico = historico
            A.comfy.tamanho_imagem = tamanho
            A.comfy.dimensoes_imagem = dimensoes
            await A.recuperar_pendentes()
            assert A.FILA.qsize() == 1
            assert A.TAREFAS[incerta.id].estado == "erro"
            assert "histórico" in A.TAREFAS[incerta.id].erro
            assert A.TAREFAS[na_fila.id].estado == "na_fila"
            assert A.TAREFAS[executando.id].estado == "pronto"
            assert consultas == 2
            assert B.listar(limite=5)[0]["arquivo"] == "recuperada.png"
            assert len(B.carregar_tarefas()) == 3
    finally:
        B.BANCO, A.TAREFAS, A.FILA = antigo_banco, antigas_tarefas, antiga_fila
        (A.comfy.esta_vivo, A.comfy.historico,
         A.comfy.tamanho_imagem, A.comfy.dimensoes_imagem) = antigas_funcoes


async def cobranca_anterior_bloqueia_novo_envio_pago():
    antigo_enfileirar = A.comfy.enfileirar
    antigo_saldo = A.chaves.saldo
    antiga_cobranca = A.COBRANCA_PENDENTE
    antigo_banco = B.BANCO
    try:
        with tempfile.TemporaryDirectory() as pasta:
            B.BANCO = pathlib.Path(pasta) / "cobranca.db"
            B.criar_tabelas()
            chamados = []

            async def enfileirar(grafo):
                chamados.append(grafo)
                return "prompt-teste"

            async def saldo(forcar=False):
                return {"ok": True, "usd": 10.0}

            A.comfy.enfileirar = enfileirar
            A.chaves.saldo = saldo
            pendencia = asyncio.Event()
            A.COBRANCA_PENDENTE = asyncio.create_task(pendencia.wait())
            modelo_pago = next(iter(A.presets.NUVEM))
            tarefa = A.Tarefa(A.PedidoGeracao(modelo=modelo_pago, prompt="teste"))
            envio = asyncio.create_task(A.submeter(tarefa, {"teste": True}))
            await asyncio.sleep(0)
            assert not chamados, "enviou outra geração paga antes de apurar a anterior"
            pendencia.set()
            await envio
            assert len(chamados) == 1
            assert tarefa.saldo_antes == 10.0
            assert tarefa.estado == "executando"
    finally:
        A.comfy.enfileirar = antigo_enfileirar
        A.chaves.saldo = antigo_saldo
        A.COBRANCA_PENDENTE = antiga_cobranca
        B.BANCO = antigo_banco


async def main():
    await acesso_local()
    await persistencia_e_custo()
    await cobranca_anterior_bloqueia_novo_envio_pago()
    print("acesso local, divisão de custo e recuperação segura passaram")


if __name__ == "__main__":
    asyncio.run(main())


def test_interface_nao_sai_da_pasta():
    # A rota da interface nao pode entregar arquivos de fora de frontend/dist
    # (por exemplo backend/chaves.json) com "../" codificado.
    async def rodar():
        transporte = httpx.ASGITransport(app=A.app)
        async with httpx.AsyncClient(transport=transporte, base_url="http://127.0.0.1:8600") as c:
            for caminho in ("/..%2f..%2fbackend%2fapp.py", "/%2e%2e/%2e%2e/backend/app.py",
                            "/..%5c..%5cbackend%5capp.py"):
                r = await c.get(caminho)
                assert "Servidor do Editor" not in r.text, caminho
    if A.ESTATICOS.exists():
        asyncio.run(rodar())


def test_rotas_get_nao_se_repetem():
    # Duas rotas GET com o mesmo endereco: so a primeira responde (o progresso dos
    # nos do Config Models ficou mudo assim, 27/10/2026).
    from collections import Counter
    rotas = Counter((r.path, m) for r in A.app.routes for m in getattr(r, "methods", ()) or ())
    assert not [k for k, n in rotas.items() if n > 1]
