import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { mensagem } from './comum'

// YuE2 through Plenio (second engine), in the new Music tab. Same flow as the
// editor's music panel: Gemma writes title, style and lyrics, YuE2 plans the
// score and sings. With review on, the same graph runs in steps with one seed:
// it stops at the lyrics, then at the score (ABC), and each step can be edited
// here or in Plenio's full editor before going on. Cover: the score is
// transcribed from a recording first, then the lyrics (original, new or none).

export type ModeloYue = { id: string; rotulo: string; maximo: number; disponivel: boolean; motivo: string
  estilos?: string[]; cover?: boolean; ordem?: string[] }
type Etapa = 'letra' | 'partitura'
type Fase = 'inicio' | 'escrevendo' | 'letra' | 'planejando' | 'partitura' | 'gerando'

const IDIOMAS: Record<string, string> = { en: 'English', pt: 'Portuguese', es: 'Spanish', fr: 'French', de: 'German', it: 'Italian', ja: 'Japanese', zh: 'Chinese', ko: 'Korean' }
const minutos = (s: number) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`

export default function BlocoYue({ cfg, prompt }: { cfg: ModeloYue; prompt: string }) {
  const cover = !!cfg.cover
  const ordem = (cfg.ordem ?? ['letra', 'partitura']) as Etapa[]
  const proxima = (e: Etapa) => (ordem[ordem.indexOf(e) + 1] ?? 'gerar') as Etapa | 'gerar'
  const anterior = (e: Etapa) => ordem[ordem.indexOf(e) - 1] as Etapa | undefined
  const NOME = { letra: 'lyrics', partitura: 'score', gerar: 'the song' }

  const [estilo, setEstilo] = useState('none')
  const [cantada, setCantada] = useState(true)
  const [idioma, setIdioma] = useState('en')
  const [voz, setVoz] = useState('livre')
  const [duracao, setDuracao] = useState(120)
  const [revisar, setRevisar] = useState(true)
  // Cover
  const [origem, setOrigem] = useState<{ nome: string; url: string } | null>(null)
  const [vozCover, setVozCover] = useState<'original' | 'nova' | 'instrumental'>('original')
  const [tema, setTema] = useState('')
  const [harmonia, setHarmonia] = useState<'nova' | 'manter'>('nova')
  const [subindo, setSubindo] = useState(false)
  // Review state
  const [fase, setFase] = useState<Fase>('inicio')
  const [caixa, setCaixa] = useState<Etapa | null>(null)
  const [docs, setDocs] = useState<Record<string, string>>({})
  const docsRef = useRef<Record<string, string>>({})
  useEffect(() => { docsRef.current = docs }, [docs])
  const [folha, setFolha] = useState<Record<string, unknown> | null>(null)
  const [errosFolha, setErrosFolha] = useState<string[]>([])
  const [segundos, setSegundos] = useState<number | null>(null)
  const semente = useRef(0)
  const [erro, setErro] = useState<string | null>(null)
  const ocupado = fase === 'escrevendo' || fase === 'planejando' || fase === 'gerando'

  const pedidoBase = () => ({
    modelo: 'musica', modelo_musica: cfg.id, prompt: prompt.trim(), proporcao: '1:1',
    vocal_musica: cover ? vozCover !== 'instrumental' : cantada, duracao_musica: duracao,
    genero_vocal_musica: voz, idioma_musica: idioma, estilo_musica: estilo,
    ...(cover ? { referencia_musica: origem?.nome ?? '', voz_cover: vozCover, harmonia_cover: harmonia, tema_cover: tema } : {}),
  })

  // One round of the graph; waits for it to finish.
  const rodada = async (extra: Record<string, unknown>) => {
    const r = await fetch('/api/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...pedidoBase(), seed: semente.current, ...extra }) })
    const t = await r.json()
    if (!r.ok) throw new Error(typeof t.detail === 'string' ? t.detail : 'Check the song settings.')
    for (;;) {
      await new Promise((ok) => setTimeout(ok, 2500))
      const lista = await fetch('/api/tarefas').then((x) => x.json())
      const atual = (Array.isArray(lista) ? lista : lista.tarefas).find((x: { id: string }) => x.id === t.id)
      if (!atual) throw new Error('The job left the queue.')
      if (atual.estado === 'erro') throw new Error(atual.erro || 'This step failed.')
      if (atual.estado === 'pronto') return atual
    }
  }

  const revisao = async (etapa: Etapa | 'gerar', novaSemente = false) => {
    setErro(null)
    if (novaSemente || !semente.current) semente.current = Math.floor(Math.random() * 2 ** 31)
    const antes = fase
    setFase(etapa === 'letra' ? 'escrevendo' : etapa === 'partitura' ? 'planejando' : 'gerando')
    try {
      const t = await rodada({ etapa_musica: etapa, docs_musica: etapa === ordem[0] ? {} : docsRef.current })
      if (etapa === 'gerar') { setFase('inicio'); setCaixa(null); setDocs({}); semente.current = 0; return }
      const r = JSON.parse(t.resultado_texto || '{}')
      setErrosFolha(r.erros ?? []); setFolha(r.folha ?? null)
      if (etapa === 'partitura') setSegundos(r.segundos ?? null)
      setDocs({ ...(etapa === ordem[0] ? {} : docsRef.current), ...(r.docs ?? {}) })
      setCaixa(etapa); setFase(etapa)
    } catch (e) {
      setErro(mensagem(e)); setFase(antes === 'escrevendo' || antes === 'planejando' ? (caixa ?? 'inicio') : antes)
    }
  }

  // Plenio's full editor (score, piano roll, chords, MIDI), loaded on demand.
  const abrirEditor = async () => {
    setErro(null)
    try {
      const w = window as unknown as { PlenioSheet?: { openSheetDialog: (o: Record<string, unknown>) => void } }
      if (!w.PlenioSheet) await new Promise<void>((ok, falha) => {
        const s = document.createElement('script'); s.src = '/plenio/editor.js'
        s.onload = () => ok(); s.onerror = () => falha(new Error('Could not load the Plenio editor.'))
        document.head.append(s)
      })
      const etapa = caixa ?? 'letra'
      const kinds = etapa === 'letra' ? ['title', 'style', 'lyrics'] : ['score']
      const daFolha = (k: string) => (folha?.docs as Record<string, { text?: string }> | undefined)?.[k]?.text ?? ''
      const docsEstado: Record<string, { state: string; text: string }> = {}
      for (const k of kinds) if ((docs[k] ?? '') !== daFolha(k)) docsEstado[k] = { state: 'manual', text: docs[k] ?? '' }
      w.PlenioSheet!.openSheetDialog({
        title: etapa === 'letra' ? 'Lyrics' : 'Score',
        state: { schema: 'plenio.sheet_state/1', docs: docsEstado },
        payload: folha, owned: (folha?.owned as string[] | undefined) ?? kinds, review: 'stop for review',
        fetcher: { fetchApi: (rota: string, opcoes?: RequestInit) => fetch('/api' + rota, opcoes) },
        layout: etapa === 'partitura' ? 'review' : null,
        onApply: (estado: { docs?: Record<string, { state: string; text?: string }> }, _g: unknown, _l: unknown, _s: unknown, aprovado: boolean) => {
          const novos: Record<string, string> = {}
          for (const k of kinds) {
            const e = estado.docs?.[k]
            novos[k] = e && e.state !== 'auto' && e.text != null ? e.text : (daFolha(k) || docs[k] || '')
          }
          setDocs((d) => ({ ...d, ...novos }))
          if (aprovado) setTimeout(() => { docsRef.current = { ...docsRef.current, ...novos }; void revisao(proxima(etapa)) }, 0)
        },
      })
    } catch (e) { setErro(mensagem(e)) }
  }

  const gerarDireto = async () => {
    setErro(null)
    try {
      const r = await fetch('/api/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(pedidoBase()) })
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? 'Could not start the song.')
    } catch (e) { setErro(mensagem(e)) }
  }

  const podeComecar = cfg.disponivel && !!prompt.trim() && (!cover || !!origem) && !subindo && fase === 'inicio'
  const opcoesEstilo = (cfg.estilos ?? []).filter((x) => x !== 'none')

  const caixaLetra = (
    <div className="hf-revisao">
      <span className="hf-passo">{ordem.indexOf('letra') + 1} · Lyrics</span>
      {cover && <p className="hf-dica">{vozCover === 'original' ? 'Lyrics transcribed from the recording: check every word, the ear makes mistakes.'
        : vozCover === 'nova' ? 'New lyrics, written for the melody of the recording.' : 'Instrumental cover: check the title and style.'}</p>}
      <label className="hf-ctrl"><small>Title</small>
        <input className="hf-campo" value={docs.title ?? ''} disabled={fase !== 'letra'} onChange={(e) => setDocs((d) => ({ ...d, title: e.target.value }))} /></label>
      <label className="hf-ctrl"><small>Style (what YuE2 receives)</small>
        <textarea rows={2} value={docs.style ?? ''} disabled={fase !== 'letra'} onChange={(e) => setDocs((d) => ({ ...d, style: e.target.value }))} /></label>
      <label className="hf-ctrl"><small>Lyrics · keep the [Verse], [Chorus] sections: the score is built on them</small>
        <textarea rows={14} value={docs.lyrics ?? ''} disabled={fase !== 'letra'} onChange={(e) => setDocs((d) => ({ ...d, lyrics: e.target.value }))} /></label>
      {errosFolha.map((x) => <p key={x} className="hf-erro">{x}</p>)}
      <div className="hf-linha-controles">
        <button type="button" className="hf-botao" disabled={fase !== 'letra'} onClick={() => revisao(proxima('letra'))}>
          {ocupado ? 'Working…' : `Approve and go on to ${NOME[proxima('letra')]}`}</button>
        <button type="button" className="hf-botao-sec" disabled={fase !== 'letra'} onClick={abrirEditor}>Open the full editor</button>
        {!cover && <button type="button" className="hf-botao-sec" disabled={fase !== 'letra'} onClick={() => revisao('letra', true)}>Write other lyrics</button>}
        {anterior('letra') && <button type="button" className="hf-botao-sec" disabled={fase !== 'letra'} onClick={() => { setCaixa(anterior('letra')!); setFase(anterior('letra')!) }}>Back to the score</button>}
        <button type="button" className="hf-botao-sec" disabled={fase !== 'letra'} onClick={() => { setFase('inicio'); setCaixa(null); setDocs({}) }}>Cancel</button>
      </div>
    </div>
  )
  const caixaPartitura = (
    <div className="hf-revisao">
      <span className="hf-passo">{ordem.indexOf('partitura') + 1} · Score</span>
      <p className="hf-dica">{cover ? 'Melody and chords transcribed from the recording (SheetSage2)' : `“${docs.title ?? ''}”`}
        {' '}· about {segundos ? minutos(segundos) : '—'}. In ABC notation; “Open the full editor” shows it as a score, piano roll, chords and MIDI.</p>
      <textarea aria-label="Score in ABC notation" rows={16} spellCheck={false} className="hf-abc" value={docs.score ?? ''} disabled={fase !== 'partitura'}
        onChange={(e) => setDocs((d) => ({ ...d, score: e.target.value }))} />
      {errosFolha.map((x) => <p key={x} className="hf-erro">{x}</p>)}
      <div className="hf-linha-controles">
        <button type="button" className="hf-botao" disabled={fase !== 'partitura'} onClick={() => revisao(proxima('partitura'))}>
          {ocupado ? 'Working…' : `Approve and go on to ${NOME[proxima('partitura')]}`}</button>
        <button type="button" className="hf-botao-sec" disabled={fase !== 'partitura'} onClick={abrirEditor}>Open the full editor</button>
        {anterior('partitura') && <button type="button" className="hf-botao-sec" disabled={fase !== 'partitura'} onClick={() => { setCaixa(anterior('partitura')!); setFase(anterior('partitura')!) }}>Back to the lyrics</button>}
        <button type="button" className="hf-botao-sec" disabled={fase !== 'partitura'} onClick={() => { setFase('inicio'); setCaixa(null); setDocs({}) }}>Cancel</button>
      </div>
    </div>
  )

  return (
    <>
      <p className="hf-dica">
        {cover ? 'Cover: melody and chords are transcribed from the recording, the lyrics are the original (transcribed), new ones or none, and YuE2 sings in the style you describe. Use only recordings you have the right to use; publishing a cover usually needs the composer’s permission.'
          : 'Plenio writes the title, style and lyrics from your description, YuE2 composes and sings, and the song comes out mastered (−14 LUFS) with the score as PDF.'}
        {' '}<b>Non-commercial use</b> (YuE2 license).</p>

      {cover && (
        <label className="hf-slot hf-slot-audio" data-cheio={!!origem} title="WAV, MP3, FLAC or OGG, 10 to 600 s, up to 40 MB.">
          {origem ? <audio src={origem.url} controls /> : <span>{subindo ? 'Uploading…' : '+ Source recording'}</span>}
          <input type="file" accept="audio/*" className="hf-arquivo" disabled={ocupado} onChange={async (e) => {
            const f = e.target.files?.[0]
            if (!f) return
            setSubindo(true); setErro(null)
            try { setOrigem({ nome: (await api.enviarAudio(f)).nome, url: URL.createObjectURL(f) }) }
            catch (x) { setErro(mensagem(x)) } finally { setSubindo(false) }
          }} />
        </label>
      )}

      <div className="hf-linha-controles">
        <label className="hf-ctrl"><small>Preset style</small>
          <select value={estilo} onChange={(e) => setEstilo(e.target.value)} disabled={fase !== 'inicio'}>
            <option value="none">None, just the description</option>
            {opcoesEstilo.map((x) => <option key={x} value={x}>{x.replace('/', ' · ').replace(/-/g, ' ')}</option>)}
          </select></label>
        {cover ? <>
          <label className="hf-ctrl"><small>Vocals</small>
            <select value={vozCover} onChange={(e) => setVozCover(e.target.value as 'original')} disabled={fase !== 'inicio'}>
              <option value="original">Original lyrics</option><option value="nova">New lyrics</option><option value="instrumental">Instrumental</option>
            </select></label>
          <label className="hf-ctrl"><small>Harmony</small>
            <select value={harmonia} onChange={(e) => setHarmonia(e.target.value as 'nova')} disabled={fase !== 'inicio'}>
              <option value="nova">New accompaniment</option><option value="manter">Keep the original chords</option>
            </select></label>
        </> : (
          <label className="hf-ctrl"><small>Type</small>
            <select value={cantada ? 'v' : 'i'} onChange={(e) => setCantada(e.target.value === 'v')} disabled={fase !== 'inicio'}>
              <option value="v">Sung</option><option value="i">Instrumental</option>
            </select></label>
        )}
        {(cover ? vozCover !== 'instrumental' : cantada) && (
          <label className="hf-ctrl"><small>Singer</small>
            <select value={voz} onChange={(e) => setVoz(e.target.value)} disabled={fase !== 'inicio'}>
              <option value="livre">Any</option><option value="feminino">Female</option><option value="masculino">Male</option>
            </select></label>
        )}
        {(cover ? vozCover === 'nova' : cantada) && (
          <label className="hf-ctrl"><small>Lyrics language</small>
            <select value={idioma} onChange={(e) => setIdioma(e.target.value)} disabled={fase !== 'inicio'}>
              {Object.entries(IDIOMAS).map(([v, r]) => <option key={v} value={v}>{r}</option>)}
            </select></label>
        )}
        {!cover && (
          <label className="hf-ctrl hf-ctrl-largo"><small>Length · about {minutos(duracao)}</small>
            <input type="range" min={60} max={Math.min(360, cfg.maximo)} step={30} value={duracao} disabled={fase !== 'inicio'}
              onChange={(e) => setDuracao(Number(e.target.value))} /></label>
        )}
      </div>
      {cover && vozCover === 'nova' && (
        <input className="hf-campo" value={tema} maxLength={300} onChange={(e) => setTema(e.target.value)} disabled={fase !== 'inicio'}
          placeholder="What the new lyrics are about, e.g. coming home after a long time" />
      )}

      <div className="hf-linha-controles">
        <label className="hf-chave-dir"><input type="checkbox" checked={revisar} disabled={fase !== 'inicio'} onChange={(e) => setRevisar(e.target.checked)} />
          Review the {cover ? 'score and lyrics' : 'lyrics and score'} before the song</label>
        <button type="button" className="hf-botao" disabled={!podeComecar || ocupado}
          onClick={() => (revisar ? revisao(ordem[0], true) : gerarDireto())}>
          {ocupado ? (fase === 'escrevendo' ? 'Writing the lyrics…' : fase === 'planejando' ? 'Planning the score…' : 'Making the song…')
            : revisar ? (ordem[0] === 'partitura' ? 'Transcribe the recording ✦' : 'Write the lyrics ✦') : 'Generate ✦'}
        </button>
      </div>
      {!cfg.disponivel && <p className="hf-erro">{cfg.motivo}</p>}

      {revisar && caixa && (ordem[0] === 'partitura'
        ? <>{caixa === 'partitura' && caixaPartitura}{caixa === 'letra' && caixaLetra}</>
        : <>{caixa === 'letra' && caixaLetra}{caixa === 'partitura' && caixaPartitura}</>)}
      {erro && <p className="hf-erro">{erro}</p>}
    </>
  )
}
