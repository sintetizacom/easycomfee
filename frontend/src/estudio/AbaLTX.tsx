import { useEffect, useState } from 'react'
import { APPS } from './AbaApps'
import FerramentaLTX, { FERRAMENTAS, type Ferramenta } from './FerramentasLTX'

type Fluxo = { nome: string; descricao: string; destino: string; etiqueta?: string }

const CRIACAO: Fluxo[] = [
  { nome: 'Text → Video', descricao: 'Turn a scene description into a video with sound.', destino: '#video/texto' },
  { nome: 'Image → Video', descricao: 'Animate a still while keeping its subject and look.', destino: '#video/imagem' },
  { nome: 'First & last frame', descricao: 'Choose how the shot begins and ends.', destino: '#video/primeiro_ultimo' },
  { nome: 'References → Video', descricao: 'Bring up to four people or objects into one shot.', destino: '#video/referencia', etiqueta: 'Local GPU' },
  { nome: 'Ingredients', descricao: 'Build a shot from several visual ingredients.', destino: '#ltx/ingredientes', etiqueta: 'Local GPU' },
  { nome: 'Keyframes', descricao: 'Place 2 to 8 images at chosen seconds; LTX moves through them.', destino: '#ltx/chaves' },
  { nome: 'Cinema Studio', descricao: 'Direct LTX shots with framing, lighting and camera choices.', destino: '#cinema/ltx-video' },
]

const FINALIZACAO: Fluxo[] = [
  { nome: 'Latent upscale', descricao: 'Enlarge an existing video with the LTX latent upscaler.', destino: '#ltx/ampliar', etiqueta: 'Local GPU' },
  { nome: 'Lip Sync', descricao: 'Animate a portrait from a voice track with LTX 2.3.', destino: '#lipsync/ltx', etiqueta: 'LTX 2.3' },
  { nome: 'Recast', descricao: 'Change the cast or setting while preserving the video’s motion.', destino: '#genjutsu/recast', etiqueta: 'LTX Union Control' },
]

function Cartao({ fluxo }: { fluxo: Fluxo }) {
  return (
    <a className="hf-ltx-cartao" href={fluxo.destino}>
      <span className="hf-ltx-etiqueta">{fluxo.etiqueta ?? 'LTX 2.5'}</span>
      <strong>{fluxo.nome}</strong>
      <span>{fluxo.descricao}</span>
      <b aria-hidden="true">↗</b>
    </a>
  )
}

const lerFerramenta = () => {
  const id = location.hash.slice('#ltx/'.length)
  return location.hash.startsWith('#ltx/') && (FERRAMENTAS as readonly string[]).includes(id) ? id as Ferramenta : null
}

export default function AbaLTX() {
  // #ltx/<ferramenta> abre a tela propria; #ltx volta para a vitrine.
  const [ferramenta, setFerramenta] = useState(lerFerramenta)
  useEffect(() => {
    const ao = () => { setFerramenta(lerFerramenta()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', ao)
    return () => window.removeEventListener('hashchange', ao)
  }, [])
  if (ferramenta) return <FerramentaLTX key={ferramenta} id={ferramenta} />
  return (
    <div className="hf-aba hf-ltx">
      <div className="hf-ltx-capa">
        <div>
          <span className="hf-sobretitulo">LTX · OPEN WEIGHTS · VIDEO + VFX</span>
          <h1>One model. An entire creative studio.</h1>
          <p>Create a shot, reshape existing footage and finish it with LTX workflows running on your GPU or, where available, Comfy Cloud.</p>
          <a className="hf-ltx-destaque" href="#apps/noite">Explore LTX VFX <span aria-hidden="true">↗</span></a>
        </div>
        <video src="/exemplos/noite.mp4?v=4" muted loop autoPlay playsInline aria-hidden="true" />
      </div>

      <section className="hf-ltx-secao">
        <div className="hf-ltx-cabecalho"><span>01 / CREATE</span><h2>Make the shot</h2><p>Start from words, frames or visual references.</p></div>
        <div className="hf-ltx-grade">{CRIACAO.map((fluxo) => <Cartao key={fluxo.nome} fluxo={fluxo} />)}</div>
      </section>

      <section className="hf-ltx-secao" id="ltx-vfx">
        <div className="hf-ltx-cabecalho"><span>02 / TRANSFORM</span><h2>VFX built with LTX</h2>
          <p>Apply an LTX video workflow to footage you already have. These effects put LTX at the center of the result.</p></div>
        <div className="hf-ltx-grade hf-ltx-efeitos">
          {APPS.filter((app) => app.id !== 'mapa_profundidade').map((app) => <Cartao key={app.id} fluxo={{ nome: app.nome, descricao: app.frase, destino: `#apps/${app.id}`,
            etiqueta: app.id === 'slowmo' ? 'LTX Slow Motion' : 'LTX VFX' }} />)}
        </div>
      </section>

      <section className="hf-ltx-secao">
        <div className="hf-ltx-cabecalho"><span>03 / FINISH & PERFORM</span><h2>Take it further</h2>
          <p>Upscale, animate speech or carry a new character through the original motion.</p></div>
        <div className="hf-ltx-grade">{FINALIZACAO.map((fluxo) => <Cartao key={fluxo.nome} fluxo={fluxo} />)}</div>
      </section>
    </div>
  )
}
