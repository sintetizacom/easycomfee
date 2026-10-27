import io,sys,pathlib,unittest
import numpy as np
import soundfile as sf
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import finalizacao_musica as f
import musica,app

def arquivo(a,sr=4000):
 b=io.BytesIO();sf.write(b,a,sr,format='FLAC',subtype='PCM_16');return b.getvalue()
def tom(segundos=16,sr=4000):
 t=np.arange(round(segundos*sr))/sr;return .2*np.sin(2*np.pi*220*t)
class FinalizacaoTests(unittest.TestCase):
 def test_respeita_cauda_e_preserva_original(self):
  sr=4000;a=tom();a[12*sr:13*sr]*=np.linspace(1,0,sr);a[13*sr:]=0
  dados=arquivo(a);out,rel=f.finalizar(dados,12,4)
  self.assertIsNotNone(out);self.assertGreater(rel['duracao_final'],13);self.assertLess(rel['duracao_final'],14)
  novo,_=sf.read(io.BytesIO(out));original,_=sf.read(io.BytesIO(dados))
  np.testing.assert_allclose(novo[:-80],original[:len(novo)-80],atol=1/32768)
 def test_pausa_no_meio_com_reentrada_nao_autoriza_corte(self):
  a=tom();a[11*4000:13*4000]=0
  out,rel=f.finalizar(arquivo(a),12,4);self.assertIsNone(out);self.assertFalse(rel['alterado'])
 def test_batida_sem_final_nao_e_compasso_garantido(self):
  a=tom();out,rel=f.finalizar(arquivo(a),12,4)
  self.assertIsNone(out)
 def test_vocal_sem_modelo_de_fala_preserva_frase(self):
  out,rel=f.finalizar(arquivo(tom()),12,4,vocal=True)
  self.assertIsNone(out);self.assertIn('frases cantadas',rel['motivo'])
 def test_fade_so_por_escolha_e_termina_zero(self):
  dados=arquivo(tom());out,rel=f.finalizar(dados,12,4,modo='fade')
  a,sr=sf.read(io.BytesIO(out));self.assertEqual(len(a),12*sr);self.assertEqual(a[-1],0)
  self.assertTrue(rel['alterado']);self.assertIn('escolha',rel['motivo'])
 def test_limites_e_pedidos_antigos(self):
  p=app.PedidoGeracao(modelo='musica',prompt='Descrição',modelo_musica='stable-audio3',duracao_musica=375,encerramento_musica='natural')
  desc,dur=musica.configuracao_geracao(p);self.assertEqual(dur,380);self.assertIn('outro',desc)
  p=app.PedidoGeracao(modelo='musica',prompt='Descrição',duracao_musica=180)
  self.assertEqual(musica.configuracao_geracao(p),('Descrição',180))
 def test_sem_sinal_preserva_original(self):
  out,rel=f.finalizar(arquivo(np.zeros(4000*16)),12,4);self.assertIsNone(out)
if __name__=='__main__':unittest.main()
