import { useEffect, useState } from 'react'
import { api, type ItemGaleria } from '../api'
import { Midia, Galeria } from './comum'

// Assets: everything generated, newest first, images and videos together.

export default function AbaAssets() {
  const [itens, setItens] = useState<ItemGaleria[] | null>(null)
  const [filtro, setFiltro] = useState<'tudo' | 'imagem' | 'video'>('tudo')

  useEffect(() => { api.galeria(120).then(setItens).catch(() => setItens([])) }, [])

  const visiveis = (itens ?? []).filter((i) =>
    filtro === 'tudo' || (filtro === 'video') === (i.duracao_video ?? 0) > 0)

  return (
    <div className="hf-aba">
      <div className="hf-heroi pequeno">
        <span className="hf-sobretitulo">ASSETS</span>
        <h1>Everything you made</h1>
        <div className="hf-chips">
          {(['tudo', 'imagem', 'video'] as const).map((f) => (
            <button key={f} data-ativo={filtro === f} onClick={() => setFiltro(f)}>
              {{ tudo: 'All', imagem: 'Images', video: 'Videos' }[f]}
            </button>
          ))}
        </div>
      </div>
      {itens === null && <p className="hf-vazio">Loading…</p>}
      <Galeria>
        {visiveis.map((i) => (
          <div key={i.id} className="hf-tarefa">
            <Midia nome={i.arquivo} subpasta={i.subpasta} />
            <p className="hf-legenda" title={i.prompt}>{i.prompt}</p>
          </div>
        ))}
        {itens && visiveis.length === 0 && <p className="hf-vazio">Nothing here yet.</p>}
      </Galeria>
    </div>
  )
}
