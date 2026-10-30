import { useEffect, useState } from 'react'
import { api, type ItemGaleria } from '../api'
import { Midia, Galeria } from './comum'

// Assets: everything generated, newest first, images and videos together.

export default function AbaAssets() {
  const [itens, setItens] = useState<ItemGaleria[] | null>(null)
  const [filtro, setFiltro] = useState<'tudo' | 'imagem' | 'video'>('tudo')
  const [falhou, setFalhou] = useState(false)

  useEffect(() => { api.galeria(120).then(setItens).catch(() => { setFalhou(true); setItens([]) }) }, [])

  const visiveis = (itens ?? []).filter((i) =>
    filtro === 'tudo' || (filtro === 'video') === (i.duracao_video ?? 0) > 0)

  return (
    <div className="hf-aba">
      <div className="hf-heroi pequeno hf-heroi-compacto">
        <span className="hf-sobretitulo">ASSETS</span>
        <h1>Everything <em>you made</em></h1>
        <div className="hf-chips">
          {(['tudo', 'imagem', 'video'] as const).map((f) => (
            <button key={f} data-ativo={filtro === f} aria-pressed={filtro === f} onClick={() => setFiltro(f)}>
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
      </Galeria>
      {/* Fora da Galeria: dentro dela (mosaico em colunas) a mensagem ficava presa na 1a coluna. */}
      {itens && visiveis.length === 0 && <Vazio filtro={filtro} nada={itens.length === 0} falhou={falhou} />}
    </div>
  )
}

/** Galeria vazia: diz o que falta e leva a aba que cria (antes era o mesmo
 *  "Nothing here yet." nos tres filtros, sem caminho para seguir). */
function Vazio({ filtro, nada, falhou }: { filtro: 'tudo' | 'imagem' | 'video'; nada: boolean; falhou: boolean }) {
  if (falhou) return <p className="hf-vazio">Could not load your files. Check that the app is running and reload the page.</p>
  const texto = nada ? 'Nothing here yet. What you generate in any tab shows up here.'
    : filtro === 'video' ? 'No videos yet.' : 'No images yet.'
  return (
    <div className="hf-vazio">
      <p>{texto}</p>
      <div className="hf-linha-controles" style={{ justifyContent: 'center' }}>
        {filtro !== 'video' && <a className="hf-botao-sec" href="#image">Create an image</a>}
        {filtro !== 'imagem' && <a className="hf-botao-sec" href="#video">Make a video</a>}
      </div>
    </div>
  )
}
