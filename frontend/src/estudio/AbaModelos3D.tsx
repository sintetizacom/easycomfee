import { useEffect, useState, createElement } from 'react'
import { api, urlImagem, type Referencia } from '../api'
import { BotaoGerar, CartaoTarefa, Chips, SlotImagem, arquivos, mensagem, useCusto, useTarefas, TituloPagina } from './comum'

// 3D: uma imagem vira um modelo 3D (arquivo GLB) por um modelo de API da Comfy Cloud
// (Tripo ou Meshy, creditos). O resultado abre num visualizador que gira com o mouse.

const MODELOS = [
  { id: 'tripo', rotulo: 'Tripo 3.1', dica: 'Textured model with PBR materials. A good all-rounder.' },
  { id: 'tripo_texto', rotulo: 'Tripo 3.1 · from text', dica: 'Describe the object; no image needed.' },
  { id: 'meshy', rotulo: 'Meshy 7.1', dica: 'Clean topology, textures up to 2K here.' },
]

/** O <model-viewer> e carregado so quando esta aba abre (e uma biblioteca grande). */
function useVisualizador3D() {
  const [pronto, setPronto] = useState(false)
  useEffect(() => { import('@google/model-viewer').then(() => setPronto(true)).catch(() => setPronto(false)) }, [])
  return pronto
}

function Modelo3D({ nome, subpasta }: { nome: string; subpasta: string }) {
  const pronto = useVisualizador3D()
  const url = urlImagem({ nome, subpasta })
  return (
    <div className="hf-m3d-cartao">
      {pronto
        ? createElement('model-viewer', { src: url, 'camera-controls': true, 'auto-rotate': true, 'shadow-intensity': '1',
            'touch-action': 'pan-y', style: { width: '100%', height: '100%', background: 'transparent' }, alt: '3D model' })
        : <p className="hf-dica">Loading the 3D viewer…</p>}
      <a className="hf-m3d-baixar" href={url} download={nome}>Download GLB</a>
    </div>
  )
}

export default function AbaModelos3D({ naNuvem }: { naNuvem: boolean }) {
  const tarefas = useTarefas()
  const [imagem, setImagem] = useState<Referencia | null>(null)
  const [modelo, setModelo] = useState('tripo')
  const [textura, setTextura] = useState(true)
  const [erro, setErro] = useState<string | null>(null)

  const [texto, setTexto] = useState('')
  const porTexto = modelo === 'tripo_texto'
  const pedido = { modelo: 'modelo3d', modelo_3d: modelo, textura_3d: textura, prompt: porTexto ? texto.trim() : '', proporcao: '1:1',
    referencias: !porTexto && imagem ? [imagem.nome] : [] }
  const pronto = naNuvem && (porTexto ? !!texto.trim() : !!imagem)
  const custo = useCusto(pronto ? pedido : null)
  const gerar = async () => {
    setErro(null)
    try { await api.gerar(pedido as Parameters<typeof api.gerar>[0]) } catch (e) { setErro(mensagem(e)) }
  }

  const minhas = tarefas.filter((t) => t.modelo === 'modelo3d')
  return (
    <div className="hf-aba hf-img">
      <TituloPagina antes="Turn a picture into" destaque="3D" sub="One image becomes a textured 3D model you can spin, download and use in Blender or a game engine." />
      <div className="hf-barra-prompt">
        <div className="hf-m3d-entrada">
          {porTexto
            ? <textarea aria-label="Describe the object" className="hf-campo" rows={5} maxLength={600} value={texto} onChange={(e) => setTexto(e.target.value)}
                placeholder="A small wooden chair with a red cushion, cartoon style" />
            : <SlotImagem rotulo="Image" valor={imagem} aoMudar={setImagem} />}
          <div className="hf-m3d-opcoes">
            <Chips rotulo="Model" opcoes={MODELOS.map((m) => ({ id: m.id, rotulo: m.rotulo, dica: m.dica }))} valor={modelo} aoMudar={setModelo} />
            <label className="hf-toggle"><input type="checkbox" checked={textura} onChange={(e) => setTextura(e.target.checked)} /> Textures</label>
            <p className="hf-dica">A single object on a plain background works best. Runs on Comfy Cloud (credits): the cost shows on the button.</p>
            {!naNuvem && <p className="hf-dica">Switch the engine to Comfy Cloud to use the 3D models.</p>}
            <BotaoGerar rotulo="Generate 3D ✦" est={custo} desligado={!pronto} aoClicar={gerar} />
            {erro && <p className="hf-erro" role="alert">{erro}</p>}
          </div>
        </div>
      </div>
      <div className="hf-m3d-lista">
        {minhas.length === 0 && <p className="hf-dica">Your 3D models show up here.</p>}
        {minhas.map((t) => {
          const arq = t.estado === 'pronto' ? arquivos(t).find((a) => /\.glb$/i.test(a.nome)) : undefined
          return arq ? <Modelo3D key={t.id} nome={arq.nome} subpasta={arq.subpasta} /> : <CartaoTarefa key={t.id} t={t} />
        })}
      </div>
    </div>
  )
}
