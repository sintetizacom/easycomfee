import { useContext, useState } from 'react'
import { MotorCtx, useEscolha } from './motor'
import { api, urlImagem } from '../api'
import { BotaoGerar, CartaoTarefa, Chips, Galeria, TituloPagina, arquivos, mensagem, useCusto, useTarefas } from './comum'

// Lip Sync > "Dub a video": the speech of a video is translated, each voice is cloned and the
// mouths are redrawn to match. Hosted models on Comfy Cloud (credits); picking one switches the engine.

const IDIOMAS = ['English', 'Portuguese', 'Spanish', 'French', 'German', 'Italian', 'Japanese', 'Chinese', 'Korean']
const MODELOS = [
  { id: 'dub_veed', rotulo: 'VEED Dubbing', frase: 'Clones each speaker and syncs the lips', etiquetas: ['Needs real speech', 'Best on longer clips'],
    dica: 'Clones each speaker’s voice and syncs the lips to the translation. Needs clips with real speech; very short clips (a few seconds) may be refused.' },
  { id: 'dub_heygen', rotulo: 'HeyGen Video Translate', frase: 'Clones the voice and redraws the mouth', etiquetas: ['Speed mode', 'Short clips ok'],
    dica: 'Clones the original voice and re-animates the mouth. Speed mode.' },
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
      <ol className="hf-lsn-etapas" aria-label="Steps">
        <li data-feito={!!video}><i>1</i>Video</li>
        <li data-feito><i>2</i>Language</li>
        <li data-feito><i>3</i>Model</li>
      </ol>

      <div className="hf-barra-prompt hf-ls">
        <div className="hf-ls-passos">
          <section className="hf-ls-cartao" data-pronto={!!video}>
            <header><b>1</b> Video</header>
            <label className="hf-slot hf-dub-video" data-cheio={!!video}>
              {video ? <video src={video.url} muted loop autoPlay playsInline />
                : <span>{enviando ? 'Uploading…' : '+ Your video'}<small>Drop it here or click to choose</small></span>}
              {video && <button type="button" className="hf-slot-x" onClick={(e) => { e.preventDefault(); setVideo(null) }}>×</button>}
              <input type="file" accept="video/*" className="hf-arquivo" onChange={async (e) => {
                const f = e.target.files?.[0]
                if (!f) return
                setEnviando(true); setErro(null)
                try { const r = await api.enviarReferencia(f); setVideo({ ref: `entrada:${r.nome}`, url: r.url }) }
                catch (x) { setErro(mensagem(x)) } finally { setEnviando(false) }
              }} />
            </label>
            {recentes.length > 0 && (
              <>
                <span className="hf-grupo-rotulo">Or pick one of yours</span>
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
            <p className="hf-dica">The video needs a visible face and speech. The result is as long as the speech and plays at 25 fps.</p>
          </section>

          <section className="hf-ls-cartao" data-pronto>
            <header><b>2</b> Dub into</header>
            <Chips rotulo="Language" opcoes={IDIOMAS.map((i) => ({ id: i, rotulo: i }))} valor={idioma} aoMudar={setIdioma} />
            <p className="hf-dica">The original speech is translated into this language and spoken again in the same voices.</p>
          </section>

          <section className="hf-ls-cartao" data-pronto>
            <header><b>3</b> Model</header>
            <div className="hf-dub-modelos" role="radiogroup" aria-label="Model">
              {MODELOS.map((m) => (
                <button key={m.id} type="button" role="radio" aria-checked={modelo.id === m.id} data-ativo={modelo.id === m.id}
                  onClick={() => escolher(`nuvem:${m.id}`)}>
                  <b>{m.rotulo}</b>
                  <small>{m.frase}</small>
                  <span>{m.etiquetas.map((t) => <i key={t}>{t}</i>)}</span>
                </button>
              ))}
            </div>
            <p className="hf-dica">{modelo.dica}{!naNuvem && ' Picking one switches the engine to Comfy Cloud.'}</p>
          </section>
        </div>

        <div className="hf-gj-opcoes">
          <span className="hf-dica hf-dub-resumo">{video ? 'Ready: ' : 'Add a video, then press Dub. '}
            {video && <>{modelo.rotulo} · into {idioma}</>}</span>
          <div className="hf-gj-direita">
            <div className="hf-gj-opc hf-gj-opc-gerar">
              <BotaoGerar rotulo="Dub ✦" est={custo} desligado={!video} aoClicar={gerar} />
            </div>
          </div>
        </div>
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
