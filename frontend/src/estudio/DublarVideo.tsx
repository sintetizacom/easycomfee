import { useContext, useState } from 'react'
import { MotorCtx, useEscolha } from './motor'
import { api, urlImagem } from '../api'
import { BotaoGerar, CartaoTarefa, Galeria, TituloPagina, arquivos, mensagem, useCusto, useTarefas } from './comum'

// Lip Sync > "Dub a video": the speech of a video is translated, each voice is cloned and the
// mouths are redrawn to match. Hosted models on Comfy Cloud (credits); picking one switches the engine.

const IDIOMAS = ['English', 'Portuguese', 'Spanish', 'French', 'German', 'Italian', 'Japanese', 'Chinese', 'Korean']
const MODELOS = [
  { id: 'dub_veed', rotulo: 'VEED Dubbing', dica: 'Clones each speaker’s voice and syncs the lips to the translation. Needs clips with real speech; very short clips (a few seconds) may be refused.' },
  { id: 'dub_heygen', rotulo: 'HeyGen Video Translate', dica: 'Clones the original voice and re-animates the mouth. Speed mode.' },
]

export default function DublarVideo({ ferramentas }: { ferramentas: React.ReactNode }) {
  const tarefas = useTarefas()
  const { naNuvem } = useContext(MotorCtx)
  const [escolhido, setEscolhido] = useState('dub_veed')
  const escolher = useEscolha(setEscolhido)
  const [idioma, setIdioma] = useState('English')
  const [video, setVideo] = useState<{ ref: string; url: string } | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const modelo = MODELOS.find((m) => m.id === escolhido) ?? MODELOS[0]

  const recentes = tarefas.filter((t) => t.estado === 'pronto' && !(t.modelo === 'limpar_video' && t.prompt.startsWith('Dub to')))
    .flatMap((t) => arquivos(t).filter((a) => /\.(mp4|webm|mov)$/i.test(a.nome)).map((a) => ({ ...a, t })))
    .slice(0, 12)

  const pedido = video ? { modelo: 'limpar_video', metodo_video: modelo.id, idioma_destino: idioma, prompt: `Dub to ${idioma}`,
    proporcao: '1:1', referencias: [video.ref] } : null
  const custo = useCusto(pedido)
  const gerar = async () => {
    if (!pedido) return
    setErro(null)
    try { await api.gerar(pedido as Parameters<typeof api.gerar>[0]) } catch (e) { setErro(mensagem(e)) }
  }
  const minhas = tarefas.filter((t) => t.modelo === 'limpar_video' && t.prompt.startsWith('Dub to'))

  return (
    <div className="hf-aba hf-img hf-lsn">
      <TituloPagina antes="Dub any video into" destaque={idioma} selo={modelo.rotulo}
        sub="The speech is translated, each voice is cloned and the lips are synced to the new language. Comfy Cloud, credits." />
      {ferramentas}
      <div className="hf-barra-prompt">
        <div className="hf-slots">
          <label className="hf-slot" data-cheio={!!video}>
            {video ? <video src={video.url} muted loop autoPlay playsInline /> : <span>{enviando ? 'Uploading…' : '+ Upload video'}</span>}
            {video && <button type="button" className="hf-slot-x" onClick={(e) => { e.preventDefault(); setVideo(null) }}>×</button>}
            <input type="file" accept="video/*" className="hf-arquivo" onChange={async (e) => {
              const f = e.target.files?.[0]
              if (!f) return
              setEnviando(true); setErro(null)
              try { const r = await api.enviarReferencia(f); setVideo({ ref: `entrada:${r.nome}`, url: r.url }) }
              catch (x) { setErro(mensagem(x)) } finally { setEnviando(false) }
            }} />
          </label>
        </div>
        {recentes.length > 0 && (
          <>
            <span className="hf-grupo-rotulo">Or pick one of your videos</span>
            <div className="hf-ampliar-lista">
              {recentes.map((a) => {
                const ref = `${a.subpasta}/${a.nome}`
                return (
                  <button key={ref} type="button" data-ativo={video?.ref === ref} aria-pressed={video?.ref === ref}
                    onClick={() => setVideo({ ref, url: urlImagem(a) })}>
                    <video src={urlImagem(a)} muted preload="metadata" />
                  </button>
                )
              })}
            </div>
          </>
        )}
        <div className="hf-linha-controles">
          <label className="hf-campo"><span>Model</span>
            <select className="hf-select" aria-label="Model" value={`nuvem:${modelo.id}`} onChange={(e) => escolher(e.target.value)}>
              <optgroup label="Comfy Cloud · credits">{MODELOS.map((m) => <option key={m.id} value={`nuvem:${m.id}`}>{m.rotulo}</option>)}</optgroup>
            </select></label>
          <label className="hf-campo"><span>Dub into</span>
            <select className="hf-select" aria-label="Target language" value={idioma} onChange={(e) => setIdioma(e.target.value)}>
              {IDIOMAS.map((i) => <option key={i}>{i}</option>)}
            </select></label>
          <span className="hf-dica">{modelo.dica}{!naNuvem && ' Picking it switches the engine to Comfy Cloud.'}</span>
          <span className="hf-espaco" />
          <BotaoGerar rotulo="Dub ✦" est={custo} desligado={!video} aoClicar={gerar} />
        </div>
        <p className="hf-dica">The video needs a visible face and speech. The result is as long as the speech and plays at 25 fps.</p>
        {erro && <p className="hf-erro" role="alert">{erro}</p>}
      </div>
      <section className="hf-img-recentes hf-lsn-recentes" aria-label="Your dubbed videos">
        <span className="hf-img-titulo">Your dubbed videos</span>
        <Galeria tipo="video">
          {minhas.map((t) => <CartaoTarefa key={t.id} t={t} />)}
          {minhas.length === 0 && <p className="hf-vazio">Your dubbed videos will appear here.</p>}
        </Galeria>
      </section>
    </div>
  )
}
