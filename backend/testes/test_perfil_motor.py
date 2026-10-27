"""Protege a troca de perfil de memória sem encerrar gerações em andamento."""
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import motores


def resposta(conteudo):
    return httpx.Response(200, json=conteudo, request=httpx.Request('GET', 'http://127.0.0.1:8188'))


class Perfil(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # A troca de perfil so existe onde o app sobe o proprio motor.
        p = patch.object(motores, "GERENCIADO", True)
        p.start()
        self.addCleanup(p.stop)

    def test_perfil_por_familia_sem_alterar_nuvem_e_imagens(self):
        self.assertEqual(motores.perfil_do('video', 'ltx'), 'tradicional')
        self.assertEqual(motores.perfil_do('video', 'ltx23'), 'tradicional')
        # O MiniMax H3 local saiu em 16/10/2026: nenhum id pede mais o dinamico.
        for modelo in ('fasth3', 'planos', 'minimax'):
            self.assertIsNone(motores.perfil_do('video', modelo))
        self.assertIsNone(motores.perfil_do('video', 'minimax-nuvem'))
        self.assertIsNone(motores.perfil_do('krea', 'ltx'))

    async def test_motor_ja_correto_nao_reinicia(self):
        cliente = AsyncMock()
        cliente.__aenter__.return_value = cliente
        cliente.get.return_value = resposta({'system': {'argv': ['--enable-dynamic-vram', '--vram-headroom', '2', '--disable-comfy-compiler']}})
        with patch.object(motores.httpx, 'AsyncClient', return_value=cliente), \
             patch.object(motores, '_trocar_perfil') as trocar, \
             patch.object(motores, '_gravar_perfil') as gravar:
            self.assertFalse(await motores.garantir_perfil('dinamico'))
            trocar.assert_not_called()
            gravar.assert_called_once_with('dinamico')

    async def test_troca_espera_motor_voltar_com_perfil_exato(self):
        cliente = AsyncMock()
        cliente.__aenter__.return_value = cliente
        cliente.get.side_effect = [
            resposta({'system': {'argv': ['--disable-dynamic-vram']}}),
            httpx.ConnectError('subindo'),
            resposta({'system': {'argv': ['--enable-dynamic-vram', '--vram-headroom', '2', '--disable-comfy-compiler']}})]
        with patch.object(motores.httpx, 'AsyncClient', return_value=cliente), \
             patch.object(motores, '_trocar_perfil') as trocar, \
             patch.object(motores.asyncio, 'sleep', AsyncMock()):
            self.assertTrue(await motores.garantir_perfil('dinamico'))
            trocar.assert_called_once_with('dinamico')

    async def test_configuracao_desconhecida_nao_encerra_motor(self):
        cliente = AsyncMock()
        cliente.__aenter__.return_value = cliente
        cliente.get.return_value = resposta({'system': {}})
        with patch.object(motores.httpx, 'AsyncClient', return_value=cliente), \
             patch.object(motores, '_trocar_perfil') as trocar:
            with self.assertRaisesRegex(RuntimeError, 'não informou'):
                await motores.garantir_perfil('tradicional')
            trocar.assert_not_called()

    def test_fila_ativa_ou_pendente_impede_encerramento(self):
        for fila in ({'queue_running': [[1]], 'queue_pending': []},
                     {'queue_running': [], 'queue_pending': [[2]]}):
            cliente = MagicMock()
            cliente.__enter__.return_value = cliente
            cliente.get.return_value = resposta(fila)
            with patch.object(motores.httpx, 'Client', return_value=cliente), \
                 patch.object(motores, '_encerrar') as encerrar, \
                 patch.object(motores, '_gravar_perfil') as gravar:
                with self.assertRaisesRegex(RuntimeError, 'ocupado'):
                    motores._trocar_perfil('dinamico')
                encerrar.assert_not_called()
                gravar.assert_not_called()

    def test_apenas_arvore_unica_identificada_pode_ser_reiniciada(self):
        cliente = MagicMock()
        cliente.__enter__.return_value = cliente
        cliente.get.return_value = resposta({'queue_running': [], 'queue_pending': []})
        with patch.object(motores.httpx, 'Client', return_value=cliente), \
             patch.object(motores, 'inspecionar', return_value={'instancias': 2, 'servindo': 11}), \
             patch.object(motores, '_encerrar') as encerrar:
            with self.assertRaisesRegex(RuntimeError, 'única'):
                motores._trocar_perfil('dinamico')
            encerrar.assert_not_called()

    def test_perfil_persistido_sem_flags_arbitrarias(self):
        with tempfile.TemporaryDirectory() as pasta, \
             patch.object(motores, 'PERFIL_ARQUIVO', pathlib.Path(pasta) / 'perfil-motor.txt'):
            motores._gravar_perfil('dinamico')
            self.assertEqual(motores.PERFIL_ARQUIVO.read_text(), 'dinamico')

    def test_dinamico_sem_margem_e_tradicional_lowvram_precisam_ajuste(self):
        self.assertFalse(motores._perfil_configurado(['--enable-dynamic-vram'], 'dinamico'))
        self.assertFalse(motores._perfil_configurado(['--disable-dynamic-vram', '--lowvram'], 'tradicional'))
        self.assertFalse(motores._perfil_configurado(['--enable-dynamic-vram', '--vram-headroom', '2'], 'dinamico'))
        self.assertTrue(motores._perfil_configurado(['--enable-dynamic-vram', '--vram-headroom', '2', '--disable-comfy-compiler'], 'dinamico'))


if __name__ == '__main__':
    unittest.main()
