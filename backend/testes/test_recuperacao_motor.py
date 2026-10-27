"""Retomada após queda: prompt perdido libera a fila; timeout não o invalida."""
import asyncio
import pathlib
import sys
import unittest
from unittest.mock import AsyncMock, patch

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import app as A


class RecuperacaoMotor(unittest.IsolatedAsyncioTestCase):
    def tarefa(self):
        tarefa = A.Tarefa(A.PedidoGeracao(modelo="krea", prompt="teste"))
        tarefa.prompt_id = "pedido-anterior"
        tarefa.estado = "executando"
        return tarefa

    async def acompanhar(self, historicos, filas, mensagem):
        with patch.object(A.comfy, "historico", AsyncMock(side_effect=historicos)), \
             patch.object(A.comfy, "fila", AsyncMock(side_effect=filas)) as consultar_fila, \
             patch.object(A.asyncio, "sleep", AsyncMock()):
            with self.assertRaisesRegex(A.comfy.ErroComfy, mensagem):
                await A.esperar_fim(self.tarefa(), recuperada=True)
            return consultar_fila.await_count

    async def test_motor_reiniciado_nao_bloqueia_uma_hora(self):
        n = await self.acompanhar([None] * 3, [{}] * 3, "não está mais na fila")
        self.assertEqual(n, 3)

    async def test_prompt_na_fila_continua_sendo_acompanhado(self):
        fila = {"queue_pending": [[1, "pedido-anterior", {}, {}, []]]}
        n = await self.acompanhar([None, None, self.erro_real()], [fila, fila], "falha real")
        self.assertEqual(n, 2)

    async def test_timeout_historico_interrompe_contagem_de_ausencias(self):
        timeout = httpx.ReadTimeout("motor ocupado")
        await self.acompanhar([None, None, timeout, None, self.erro_real()],
                             [{}, {}, {}], "falha real")

    async def test_timeout_fila_interrompe_contagem_de_ausencias(self):
        await self.acompanhar([None, None, None, None, self.erro_real()],
                             [{}, {}, httpx.ReadTimeout("motor ocupado"), {}], "falha real")

    @staticmethod
    def erro_real():
        return {"status": {"status_str": "error", "messages": ["falha real"]}}

    async def test_cancelamento_exibe_mensagem_clara(self):
        historico = {"status": {"status_str": "error", "messages": [
            ["execution_start", {}], ["execution_interrupted", {"node_id": "passo"}]]}}
        await self.acompanhar([historico], [], "Geração interrompida")


if __name__ == "__main__":
    unittest.main()
