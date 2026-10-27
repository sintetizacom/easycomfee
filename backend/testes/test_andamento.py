"""Progresso por etapa, reconexão e telemetria sem geração real."""
import pathlib
import subprocess
import sys
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import app as A
import andamento


class Progresso(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tarefa = A.Tarefa(A.PedidoGeracao(modelo="video", prompt="teste", modelo_video="fasth3"))
        self.tarefa.prompt_id = "pedido"
        self.tarefa.estado = "executando"
        self.mapa = patch.object(A, "POR_PROMPT_ID", {"pedido": self.tarefa})
        self.anuncio = patch.object(A, "anunciar", AsyncMock())
        self.mapa.start()
        self.anuncio.start()

    async def asyncTearDown(self):
        self.anuncio.stop()
        self.mapa.stop()

    async def evento(self, tipo, **dados):
        await A.do_motor({"type": tipo, "data": {"prompt_id": "pedido", **dados}})

    async def test_fasth3_identifica_etapa_e_conta_passos_reais(self):
        await self.evento("executing", node="passo")
        self.assertEqual(self.tarefa.detalhe, "gerando o vídeo")
        await A.atualizar_fila_monitor({"queue_running": [[0, "pedido", {
            "passo": {"class_type": "SamplerCustomAdvanced", "inputs": {"sigmas": ["sigmas", 0]}},
            "sigmas": {"inputs": {"steps": 8}},
        }]]})
        self.assertEqual(self.tarefa.passos_total, 8)
        self.assertEqual(self.tarefa.passo_atual, 0)
        await self.evento("progress", value=2, max=8)
        self.assertEqual(self.tarefa.passo_atual, 2)
        self.assertEqual(self.tarefa.progresso, .25)
        self.assertGreater(self.tarefa.ultimo_avanco_em, 0)

    async def test_decodificacao_nao_mostra_percentual_do_sampler(self):
        await self.evento("executing", node="passo")
        await self.evento("progress", value=8, max=8)
        await self.evento("executing", node="decodifica")
        self.assertEqual(self.tarefa.detalhe, "decodificando o vídeo")
        self.assertEqual(self.tarefa.progresso, 0)
        self.assertEqual(self.tarefa.passos_total, 0)

    async def test_replay_apos_reconectar_nao_inventa_avanco(self):
        self.tarefa.ultimo_avanco_em = 123
        await A.do_motor({"type": "executing", "data": {"node": "passo"}})
        self.assertEqual(self.tarefa.etapa_no, "passo")
        self.assertEqual(self.tarefa.ultimo_avanco_em, 123)

    async def test_cliente_original_so_e_retomado_para_pedido_conhecido(self):
        fila = {"queue_running": [[0, "pedido", {}, {"client_id": "sessao-original"}]]}
        with patch.object(A.comfy, "ID_CLIENTE", "sessao-nova"), \
             patch.object(A.comfy, "fila", AsyncMock(return_value=fila)):
            await A.comfy.retomar_cliente({"outro-pedido"})
            self.assertEqual(A.comfy.ID_CLIENTE, "sessao-nova")
            await A.comfy.retomar_cliente({"pedido"})
            self.assertEqual(A.comfy.ID_CLIENTE, "sessao-original")

    async def test_dados_de_progresso_sobrevivem_a_persistencia(self):
        await self.evento("executing", node="passo")
        await self.evento("progress", value=3, max=8)
        recuperada = A.Tarefa.de_registro(self.tarefa.registro()).como_dict()
        self.assertEqual(recuperada["passo_atual"], 3)
        self.assertEqual(recuperada["modelo_video"], "fasth3")
        self.assertGreater(recuperada["ultimo_avanco_em"], 0)


class Telemetria(unittest.TestCase):
    def test_gpu_e_parseada_em_gib(self):
        with patch.object(andamento.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "8192, 16384, 97\n")):
            self.assertEqual(andamento.recursos()["gpu"],
                             {"vram_usada_gib": 8, "vram_total_gib": 16, "uso_pct": 97})

    def test_ausencia_de_nvidia_nao_impede_monitor(self):
        with patch.object(andamento.subprocess, "run", side_effect=FileNotFoundError()):
            self.assertIsNone(andamento.recursos()["gpu"])


if __name__ == "__main__":
    unittest.main()
