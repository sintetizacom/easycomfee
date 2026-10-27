import { useEffect, useRef, useState } from 'react'
import type { ItemGaleria } from './api'
import RotuloAjuda from './RotuloAjuda'

type ModeloMusica = { id: string; rotulo: string; disponivel: boolean; motivo: string; letra: boolean; maximo: number; plenio?: boolean; estilos?: string[]; cover?: boolean; ordem?: string[] }
function formatarDuracao(segundos: number) {
  const minutos = Math.floor(segundos / 60)
  const resto = segundos % 60
  return `${minutos} min${resto ? ` ${resto} s` : ''}`
}
const notasAce = ['C', 'C#', 'Db', 'D', 'D#', 'Eb', 'E', 'F', 'F#', 'Gb', 'G', 'G#', 'Ab', 'A', 'A#', 'Bb', 'B']
export default function PainelMusica({ motorVivo, aoErro, reuso }: { motorVivo: boolean; aoErro: (s: string) => void; reuso: ItemGaleria | null }) {
  const [modelos, setModelos] = useState<ModeloMusica[]>([])
  const [modelo, setModelo] = useState('minimax-music3')
  const [referencia, setReferencia] = useState('')
  const [transformacao, setTransformacao] = useState(0.75)
  const [subindo, setSubindo] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [projeto, setProjeto] = useState('')
  const [titulo, setTitulo] = useState('')
  const [letra, setLetra] = useState('')
  const [vocal, setVocal] = useState(false)
  const [encerramento, setEncerramento] = useState("natural")
  const [margem, setMargem] = useState(10)
  const [duracao, setDuracao] = useState(30)
  const [bpm, setBpm] = useState(120)
  const [tonalidade, setTonalidade] = useState('C major')
  const [generoVocal, setGeneroVocal] = useState('livre')
  const [idioma, setIdioma] = useState('pt')
  const [estilo, setEstilo] = useState('none')
  // Cover (YuE2 Cover): a voz, a harmonia e o tema da letra nova.
  const [vozCover, setVozCover] = useState<'original' | 'nova' | 'instrumental'>('original')
  const [harmonia, setHarmonia] = useState<'nova' | 'manter'>('nova')
  const [tema, setTema] = useState('')
  // A caixa de revisao aberta (letra ou partitura); fica visivel enquanto a rodada seguinte roda.
  const [caixa, setCaixa] = useState<'letra' | 'partitura' | null>(null)
  // Revisao antes de gerar (YuE2): tres rodadas do mesmo grafo, mesma seed.
  const [revisar, setRevisar] = useState(true)
  const [fase, setFase] = useState<'inicio' | 'escrevendo' | 'letra' | 'planejando' | 'partitura' | 'gerando'>('inicio')
  const [docs, setDocs] = useState<Record<string, string>>({})
  // Espelho de docs para as rodadas disparadas de dentro do editor (fecho sem o estado novo).
  const docsRef = useRef<Record<string, string>>({})
  useEffect(() => { docsRef.current = docs }, [docs])
  const [segundosPartitura, setSegundosPartitura] = useState<number | null>(null)
  const [errosFolha, setErrosFolha] = useState<string[]>([])
  const semente = useRef(0)
  // O payload inteiro da Song Sheet que parou: o editor completo abre com ele.
  const [folha, setFolha] = useState<Record<string, unknown> | null>(null)
  const [enviando, setEnviando] = useState(false)
  useEffect(() => {
    const controller = new AbortController()
    const consultar = () => fetch('/api/musica', { signal: controller.signal }).then(r => { if (!r.ok) throw new Error('Não foi possível consultar os modelos de música.'); return r.json() }).then(setModelos).catch(e => { if (!controller.signal.aborted) aoErro(String(e)) })
    void consultar(); const timer = setInterval(consultar, 20000)
    return () => { controller.abort(); clearInterval(timer) }
  }, [motorVivo, aoErro])
  useEffect(() => {
    if (!reuso) return
    const p = reuso.parametros
    setProjeto(String(p.projeto_musica ?? '')); setTitulo(String(p.titulo_musica ?? ''))
    setReferencia(String(p.referencia_musica ?? '')); setTransformacao(Number(p.transformacao_musica ?? .75))
    setModelo(String(p.modelo_musica ?? 'minimax-music3')); setPrompt(reuso.prompt)
    setEncerramento(String(p.encerramento_musica ?? "original")); setMargem(Number(p.margem_musica ?? 10))
    setLetra(String(p.letra_musica ?? '')); setVocal(Boolean(p.vocal_musica))
    setDuracao(Number(p.duracao_musica ?? 30)); setBpm(Number(p.bpm_musica ?? 120)); setIdioma(String(p.idioma_musica ?? 'pt'))
    setTonalidade(String(p.tonalidade_musica ?? 'C major')); setGeneroVocal(String(p.genero_vocal_musica ?? 'livre'))
    setEstilo(String(p.estilo_musica ?? 'none'))
  }, [reuso])
  const cfg = modelos.find(m => m.id === modelo)
  // YuE2 (Plenio): a letra e escrita pela IA; o vocal e so cantado ou instrumental.
  const plenio = !!cfg?.plenio
  const cover = !!cfg?.cover
  // Ordem das paradas: musica = letra -> partitura; cover = partitura (transcrita) -> letra.
  const ordem = (cfg?.ordem ?? ['letra', 'partitura']) as ('letra' | 'partitura')[]
  const proxima = (e: string) => (ordem[ordem.indexOf(e as 'letra') + 1] ?? 'gerar') as 'letra' | 'partitura' | 'gerar'
  const anterior = (e: string) => ordem[ordem.indexOf(e as 'letra') - 1] as 'letra' | 'partitura' | undefined
  const rotuloEtapa = { letra: 'a letra', partitura: 'a partitura', gerar: 'a música' }
  const camposCover = () => cover ? { referencia_musica: referencia, voz_cover: vozCover, harmonia_cover: harmonia, tema_cover: tema } : {}
  const pedidoBase = () => ({ modelo: 'musica', projeto_musica: projeto, titulo_musica: titulo, modelo_musica: modelo, prompt,
    vocal_musica: cover ? vozCover !== 'instrumental' : vocal, duracao_musica: duracao, genero_vocal_musica: generoVocal,
    idioma_musica: idioma, estilo_musica: estilo, ...camposCover() })
  // Envia uma rodada e espera ela terminar; devolve a tarefa.
  const rodada = async (extra: Record<string, unknown>) => {
    const r = await fetch('/api/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...pedidoBase(), seed: semente.current, ...extra }) })
    const t = await r.json()
    if (!r.ok) throw new Error(typeof t.detail === 'string' ? t.detail : 'Confira os parâmetros da música.')
    for (;;) {
      await new Promise(ok => setTimeout(ok, 2500))
      const lista = await fetch('/api/tarefas').then(x => x.json())
      const atual = (Array.isArray(lista) ? lista : lista.tarefas).find((x: { id: string }) => x.id === t.id)
      if (!atual) throw new Error('A tarefa sumiu da fila.')
      if (atual.estado === 'erro') throw new Error(atual.erro || 'A rodada falhou.')
      if (atual.estado === 'pronto') return atual
    }
  }
  const revisao = async (etapa: 'letra' | 'partitura' | 'gerar', novaSemente = false) => {
    aoErro('')
    if (novaSemente || !semente.current) semente.current = Math.floor(Math.random() * 2 ** 31)
    const antes = fase
    setFase(etapa === 'letra' ? 'escrevendo' : etapa === 'partitura' ? 'planejando' : 'gerando')
    try {
      const t = await rodada({ etapa_musica: etapa, docs_musica: etapa === ordem[0] ? {} : docsRef.current })
      if (etapa === 'gerar') { setFase('inicio'); setCaixa(null); setDocs({}); semente.current = 0; return }
      const r = JSON.parse(t.resultado_texto || '{}')
      setErrosFolha(r.erros ?? []); setFolha(r.folha ?? null)
      const base = etapa === ordem[0] ? {} : docsRef.current
      if (etapa === 'partitura') setSegundosPartitura(r.segundos ?? null)
      setDocs({ ...base, ...(r.docs ?? {}) }); setCaixa(etapa); setFase(etapa)
    } catch (e) { aoErro(String(e)); setFase(antes === 'escrevendo' || antes === 'planejando' ? (caixa ?? 'inicio') : antes) }
  }
  // Editor completo do Plenio (Vue, vendor/plenio-frontend), carregado so quando abre.
  const abrirEditor = async () => {
    aoErro('')
    try {
      const w = window as unknown as { PlenioSheet?: { openSheetDialog: (o: Record<string, unknown>) => void } }
      if (!w.PlenioSheet) await new Promise<void>((ok, falha) => {
        const s = document.createElement('script'); s.src = '/plenio/editor.js'
        s.onload = () => ok(); s.onerror = () => falha(new Error('Não consegui carregar o editor do Plenio.'))
        document.head.append(s)
      })
      const etapa = caixa ?? 'letra'
      const kinds = etapa === 'letra' ? ['title', 'style', 'lyrics'] : ['score']
      // O que ja foi editado aqui entra como texto "manual" do editor.
      const docsEstado: Record<string, { state: string; text: string }> = {}
      for (const k of kinds) {
        const up = (folha?.docs as Record<string, { text?: string }> | undefined)?.[k]?.text ?? ''
        if ((docs[k] ?? '') !== up) docsEstado[k] = { state: 'manual', text: docs[k] ?? '' }
      }
      w.PlenioSheet!.openSheetDialog({
        title: etapa === 'letra' ? 'Letra' : 'Partitura',
        state: { schema: 'plenio.sheet_state/1', docs: docsEstado },
        payload: folha, owned: (folha?.owned as string[] | undefined) ?? kinds,
        review: 'stop for review',
        fetcher: { fetchApi: (rota: string, opcoes?: RequestInit) => fetch('/api' + rota, opcoes) },
        layout: etapa === 'partitura' ? 'review' : null,
        onApply: (estado: { docs?: Record<string, { state: string; text?: string }> }, _g: unknown, _l: unknown, _s: unknown, aprovado: boolean) => {
          const novos: Record<string, string> = {}
          for (const k of kinds) {
            const e = estado.docs?.[k]
            novos[k] = e && e.state !== 'auto' && e.text != null ? e.text
              : ((folha?.docs as Record<string, { text?: string }> | undefined)?.[k]?.text ?? docs[k] ?? '')
          }
          setDocs(d => ({ ...d, ...novos }))
          if (aprovado) setTimeout(() => { void revisaoCom(proxima(etapa), novos) }, 0)
        },
      })
    } catch (e) { aoErro(String(e)) }
  }
  // Mesma rodada de revisao, mas com documentos recem-editados no editor.
  const revisaoCom = async (etapa: 'letra' | 'partitura' | 'gerar', novos: Record<string, string>) => {
    docsRef.current = { ...docsRef.current, ...novos }
    await revisao(etapa)
  }
  const ocupadoRevisao = fase === 'escrevendo' || fase === 'planejando' || fase === 'gerando'
  const gerar = async () => {
    setEnviando(true); aoErro('')
    try {
      const r = await fetch('/api/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ modelo: 'musica', projeto_musica: projeto, titulo_musica: titulo, referencia_musica: modelo === 'ace-step15' || cover ? referencia : '', ...camposCover(), transformacao_musica: transformacao, encerramento_musica: encerramento, margem_musica: margem, modelo_musica: modelo, prompt, letra_musica: letra, vocal_musica: vocal && (cfg?.letra || plenio), estilo_musica: estilo, duracao_musica: duracao, bpm_musica: bpm, tonalidade_musica: tonalidade, genero_vocal_musica: generoVocal, idioma_musica: idioma }) })
      if (!r.ok) { const e = await r.json(); throw new Error(typeof e.detail === 'string' ? e.detail : 'Confira os parâmetros da música.') }
    } catch (e) { aoErro(String(e)) } finally { setEnviando(false) }
  }
  return <div className="painel-voz">
    <h2>Música</h2>
    <RotuloAjuda campo="projeto-musica" rotulo="Nome do projeto" ajuda="Opcional. Identifica o artista ou projeto no nome do arquivo salvo." />
    <input id="projeto-musica" maxLength={120} value={projeto} onChange={e => setProjeto(e.target.value)} placeholder="Ex.: Meu projeto" />
    <RotuloAjuda campo="titulo-musica" rotulo="Nome da música" ajuda="Opcional. Entra no nome do arquivo. Caracteres especiais são normalizados e um número evita sobrescrever gerações." />
    <input id="titulo-musica" maxLength={120} value={titulo} onChange={e => setTitulo(e.target.value)} placeholder="Ex.: Chuva de setembro" />
    <RotuloAjuda campo="modelo-musica" rotulo="Modelo" ajuda="Escolha o motor local. O limite de duração aparece ao lado do nome; cada modelo tem recursos diferentes." />
    <select id="modelo-musica" value={modelo} onChange={e => { const m = modelos.find(x => x.id === e.target.value); setModelo(e.target.value); setVocal(!!m?.plenio); setDuracao(d => m?.plenio ? Math.max(60, Math.min(d, m.maximo)) : Math.min(d, m?.maximo ?? 30)) }}>
      {modelos.map(m => <option key={m.id} value={m.id}>{m.rotulo} — até {formatarDuracao(m.maximo)}{m.disponivel ? '' : ' — indisponível'}</option>)}
    </select>
    {cfg && !cfg.disponivel && <p className="aviso-atencao">{cfg.motivo}</p>}
    {modelo === 'ace-step15' && <>
      <RotuloAjuda campo="guia-musica" rotulo="Composição como guia (opcional)" ajuda="No ACE-Step, envie uma gravação de 10 a 600 segundos, até 40 MB. A nova música segue a duração e parte da estrutura da guia, mas pode reinterpretar melodia e voz." />
      <input id="guia-musica" type="file" accept=".wav,.mp3,.flac,.ogg,.m4a" disabled={subindo || enviando} onChange={async e => {
        const arquivo=e.target.files?.[0]; if (!arquivo) return
        setSubindo(true); aoErro(''); setReferencia('')
        try {
          const form=new FormData(); form.append('arquivo', arquivo)
          const r=await fetch('/api/referencia-audio', {method:'POST',body:form})
          const dados=await r.json(); if (!r.ok) throw new Error(dados.detail ?? 'Falha no envio')
          setReferencia(dados.nome); setEncerramento('original')
        } catch (erro) { aoErro(String(erro)) } finally {setSubindo(false)}
      }} />
      {referencia && <>
        <audio key={referencia} controls preload="metadata" aria-label="Ouvir composição guia" src={`/api/imagem?tipo=input&nome=${encodeURIComponent(referencia)}`} onError={() => aoErro('Não foi possível ouvir a guia. Tente WAV, FLAC ou MP3.')} />
        <button onClick={() => setReferencia('')}>Remover guia</button>
        <RotuloAjuda campo="transformacao-musica" rotulo={<>Transformação: {Math.round(transformacao*100)}%</>} ajuda="Valores menores preservam mais da guia; maiores permitem mais mudanças no arranjo. Não garante cada nota da gravação." />
        <input id="transformacao-musica" type="range" min={.3} max={1} step={.05} value={transformacao} onChange={e => setTransformacao(Number(e.target.value))} />
      </>}
    </>}
    <RotuloAjuda campo="descricao-musica" rotulo="Descrição da música" ajuda="Descreva gênero, instrumentos, ritmo e clima. O resultado pode variar; prompts em inglês às vezes são seguidos com mais consistência." />
    <textarea id="descricao-musica" rows={6} maxLength={12000} value={prompt} onChange={e => setPrompt(e.target.value)} placeholder="Ex.: lo-fi hip-hop, piano suave, baixo quente, bateria discreta, clima relaxante, sem vocais." />
    {plenio && <>
      {cover ? <>
        <p className="nota">Cover pelo Plenio: a melodia e os acordes são transcritos da gravação, a letra é a original (transcrita), uma nova ou nenhuma, e o YuE2 canta no estilo que você descrever. <strong>Uso não comercial</strong> (YuE2 e SheetSage2). <strong>Só use gravações que você tem direito de usar</strong>; publicar um cover geralmente exige autorização de quem detém a composição.</p>
        <RotuloAjuda campo="origem-cover" rotulo="Gravação de origem" ajuda="WAV, MP3, FLAC ou OGG de 10 a 600 segundos, até 40 MB. É dela que saem a melodia, os acordes e, se escolher, a letra." />
        <input id="origem-cover" type="file" accept=".wav,.mp3,.flac,.ogg,.m4a" disabled={subindo || ocupadoRevisao} onChange={async e => {
          const arquivo = e.target.files?.[0]; if (!arquivo) return
          setSubindo(true); aoErro(''); setReferencia('')
          try {
            const form = new FormData(); form.append('arquivo', arquivo)
            const r = await fetch('/api/referencia-audio', { method: 'POST', body: form })
            const dados = await r.json(); if (!r.ok) throw new Error(dados.detail ?? 'Falha no envio')
            setReferencia(dados.nome)
          } catch (erro) { aoErro(String(erro)) } finally { setSubindo(false) }
        }} />
        {referencia && <audio key={referencia} controls preload="metadata" aria-label="Ouvir a gravação de origem" src={`/api/imagem?tipo=input&nome=${encodeURIComponent(referencia)}`} />}
        <RotuloAjuda campo="estilo-musica" rotulo="Estilo pronto (opcional)" ajuda="O estilo de chegada do cover. A descrição continua valendo por cima." />
        <select id="estilo-musica" value={estilo} onChange={e => setEstilo(e.target.value)}>
          <option value="none">Nenhum — só a descrição</option>
          {(cfg?.estilos ?? []).filter(x => x !== 'none').map(x => <option key={x} value={x}>{x.replace('/', ' · ').replace(/-/g, ' ')}</option>)}
        </select>
        <RotuloAjuda campo="voz-cover" rotulo="Voz" ajuda="Letra original: as palavras da gravação, transcritas (confira na revisão). Letra nova: palavras novas na mesma melodia. Instrumental: um instrumento toca a melodia." />
        <select id="voz-cover" value={vozCover} onChange={e => setVozCover(e.target.value as 'original')}>
          <option value="original">Letra original</option>
          <option value="nova">Letra nova</option>
          <option value="instrumental">Instrumental</option>
        </select>
        {vozCover === 'nova' && <>
          <RotuloAjuda campo="tema-cover" rotulo="Tema da letra nova" ajuda="Sobre o que a nova letra fala." />
          <input id="tema-cover" maxLength={300} value={tema} onChange={e => setTema(e.target.value)} placeholder="Ex.: voltar para casa depois de muito tempo" />
          <RotuloAjuda campo="idioma-cover" rotulo="Idioma da letra nova" ajuda="A IA escreve a letra nova já nesse idioma." />
          <select id="idioma-cover" value={idioma} onChange={e => setIdioma(e.target.value)}>{Object.entries({pt:'Português',en:'Inglês',es:'Espanhol',de:'Alemão',it:'Italiano',fr:'Francês',ja:'Japonês',zh:'Chinês',ko:'Coreano'}).map(([v,r]) => <option key={v} value={v}>{r}</option>)}</select>
        </>}
        {vozCover !== 'instrumental' && <>
          <RotuloAjuda campo="voz-yue" rotulo="Cantor" ajuda="Uma preferência; não é garantia. Escolha uma voz que alcance a melodia da gravação." />
          <select id="voz-yue" value={generoVocal} onChange={e => setGeneroVocal(e.target.value)}>
            <option value="livre">Sem preferência</option>
            <option value="feminino">Feminina</option>
            <option value="masculino">Masculina</option>
          </select>
        </>}
        <RotuloAjuda campo="harmonia-cover" rotulo="Harmonia" ajuda="Novo acompanhamento: os acordes da gravação saem e o YuE2 harmoniza de novo. Manter os acordes: a harmonia original fica." />
        <select id="harmonia-cover" value={harmonia} onChange={e => setHarmonia(e.target.value as 'nova')}>
          <option value="nova">Novo acompanhamento</option>
          <option value="manter">Manter os acordes originais</option>
        </select>
      </> : <>
      <p className="nota">Gerado pelo Plenio no segundo motor: a IA escreve título, estilo e letra a partir da descrição, o YuE2 compõe e canta, e a música sai masterizada (−14 LUFS), com a partitura em PDF. <strong>Uso não comercial</strong> (licença do YuE2).</p>
      <RotuloAjuda campo="estilo-musica" rotulo="Estilo pronto (opcional)" ajuda="Um dos estilos do Plenio: define gênero, andamento, compasso e voz de partida. A descrição continua valendo por cima." />
      <select id="estilo-musica" value={estilo} onChange={e => setEstilo(e.target.value)}>
        <option value="none">Nenhum — só a descrição</option>
        {(cfg?.estilos ?? []).filter(x => x !== 'none').map(x => <option key={x} value={x}>{x.replace('/', ' · ').replace(/-/g, ' ')}</option>)}
      </select>
      <RotuloAjuda campo="tipo-musica-yue" rotulo="Tipo de música" ajuda="Cantada: a IA escreve a letra no idioma escolhido. Instrumental: um instrumento leva a melodia." />
      <select id="tipo-musica-yue" value={vocal ? 'cantada' : 'instrumental'} onChange={e => setVocal(e.target.value === 'cantada')}>
        <option value="cantada">Cantada</option>
        <option value="instrumental">Instrumental</option>
      </select>
      {vocal && <>
        <RotuloAjuda campo="idioma-yue" rotulo="Idioma da letra" ajuda="A letra é escrita pela IA já nesse idioma." />
        <select id="idioma-yue" value={idioma} onChange={e => setIdioma(e.target.value)}>{Object.entries({pt:'Português',en:'Inglês',es:'Espanhol',de:'Alemão',it:'Italiano',fr:'Francês',ja:'Japonês',zh:'Chinês',ko:'Coreano'}).map(([v,r]) => <option key={v} value={v}>{r}</option>)}</select>
        <RotuloAjuda campo="voz-yue" rotulo="Voz" ajuda="Uma preferência para o cantor; não é garantia." />
        <select id="voz-yue" value={generoVocal} onChange={e => setGeneroVocal(e.target.value)}>
          <option value="livre">Sem preferência</option>
          <option value="feminino">Feminina</option>
          <option value="masculino">Masculina</option>
        </select>
      </>}
      <RotuloAjuda campo="duracao-yue" rotulo={<>Duração aproximada: {formatarDuracao(duracao)}</>} ajuda="O Plenio trabalha em faixas de duração (1 a 6 minutos); a música termina por conta própria perto disso." />
      <input id="duracao-yue" type="range" min={60} max={360} step={30} value={Math.max(60, duracao)} onChange={e => setDuracao(Number(e.target.value))} />
      </>}
      <label className="alternador">
        <input type="checkbox" checked={revisar} disabled={fase !== 'inicio'} onChange={e => setRevisar(e.target.checked)} />
        <span>Revisar {cover ? 'partitura e letra' : 'letra e partitura'} antes de gerar</span>
      </label>
{ordem[0] === 'partitura' ? <>
      {revisar && caixa === 'partitura' && <div className="revisao-musica">
        <h3>{ordem.indexOf('partitura') + 1} · Partitura</h3>
        <p className="nota">{cover ? 'Melodia e acordes transcritos da gravação (SheetSage2)' : `“${docs.title ?? ''}”`} · cerca de {segundosPartitura ? formatarDuracao(Math.round(segundosPartitura)) : '—'}. A partitura está em notação ABC; para ver e editar como partitura, piano roll, acordes e MIDI, use “Abrir no editor completo”.</p>
        <textarea rows={18} spellCheck={false} style={{ fontFamily: 'monospace', fontSize: 12 }} value={docs.score ?? ''} disabled={fase !== 'partitura'} onChange={e => setDocs(d => ({ ...d, score: e.target.value }))} />
        {errosFolha.map(x => <p key={x} className="aviso-atencao">{x}</p>)}
        <div className="opcoes">
          <button className="principal" disabled={fase !== 'partitura' || !motorVivo} onClick={() => revisao(proxima('partitura'))}>{ocupadoRevisao ? 'Trabalhando…' : `Aprovar e seguir para ${rotuloEtapa[proxima('partitura')]}`}</button>
          <button disabled={fase !== 'partitura'} onClick={abrirEditor}>Abrir no editor completo</button>
          {anterior('partitura') && <button disabled={fase !== 'partitura'} onClick={() => { setCaixa(anterior('partitura')!); setFase(anterior('partitura')!) }}>Voltar à letra</button>}
          {cover && <button disabled={fase !== 'partitura'} onClick={() => { setFase('inicio'); setCaixa(null); setDocs({}) }}>Cancelar</button>}
        </div>
      </div>}
      {revisar && caixa === 'letra' && <div className="revisao-musica">
        <h3>{ordem.indexOf('letra') + 1} · Letra</h3>
        {cover && <p className="nota">{vozCover === 'original' ? 'Letra transcrita da gravação (faster-whisper): confira palavra por palavra — erros de ouvido acontecem.' : vozCover === 'nova' ? 'Letra nova, escrita para a melodia da gravação.' : 'Cover instrumental: confira título e estilo.'}</p>}
        <RotuloAjuda campo="titulo-yue" rotulo="Título" ajuda="Vai nas tags do arquivo e no nome exportado pelo Plenio." />
        <input id="titulo-yue" value={docs.title ?? ''} disabled={fase !== 'letra'} onChange={e => setDocs(d => ({ ...d, title: e.target.value }))} />
        <RotuloAjuda campo="estilo-yue" rotulo="Estilo" ajuda="Uma linha curta: gênero, instrumentos, voz, andamento. É o que o YuE2 recebe como estilo." />
        <textarea id="estilo-yue" rows={2} value={docs.style ?? ''} disabled={fase !== 'letra'} onChange={e => setDocs(d => ({ ...d, style: e.target.value }))} />
        <RotuloAjuda campo="letra-yue" rotulo="Letra" ajuda="Edite à vontade. Mantenha as seções entre colchetes ([Verse], [Chorus], [Outro]): a partitura é organizada por elas." />
        <textarea id="letra-yue" rows={16} value={docs.lyrics ?? ''} disabled={fase !== 'letra'} onChange={e => setDocs(d => ({ ...d, lyrics: e.target.value }))} />
        {errosFolha.map(x => <p key={x} className="aviso-atencao">{x}</p>)}
        <div className="opcoes">
          <button className="principal" disabled={fase !== 'letra' || !motorVivo} onClick={() => revisao(proxima('letra'))}>{ocupadoRevisao ? 'Trabalhando…' : `Aprovar e seguir para ${rotuloEtapa[proxima('letra')]}`}</button>
          <button disabled={fase !== 'letra'} onClick={abrirEditor}>Abrir no editor completo</button>
          {!cover && <button disabled={fase !== 'letra'} onClick={() => revisao('letra', true)}>Escrever outra letra</button>}
          {anterior('letra') && <button disabled={fase !== 'letra'} onClick={() => { setCaixa(anterior('letra')!); setFase(anterior('letra')!) }}>Voltar à partitura</button>}
          <button disabled={fase !== 'letra'} onClick={() => { setFase('inicio'); setCaixa(null); setDocs({}) }}>Cancelar</button>
        </div>
      </div>}
      </> : <>
      {revisar && caixa === 'letra' && <div className="revisao-musica">
        <h3>{ordem.indexOf('letra') + 1} · Letra</h3>
        {cover && <p className="nota">{vozCover === 'original' ? 'Letra transcrita da gravação (faster-whisper): confira palavra por palavra — erros de ouvido acontecem.' : vozCover === 'nova' ? 'Letra nova, escrita para a melodia da gravação.' : 'Cover instrumental: confira título e estilo.'}</p>}
        <RotuloAjuda campo="titulo-yue" rotulo="Título" ajuda="Vai nas tags do arquivo e no nome exportado pelo Plenio." />
        <input id="titulo-yue" value={docs.title ?? ''} disabled={fase !== 'letra'} onChange={e => setDocs(d => ({ ...d, title: e.target.value }))} />
        <RotuloAjuda campo="estilo-yue" rotulo="Estilo" ajuda="Uma linha curta: gênero, instrumentos, voz, andamento. É o que o YuE2 recebe como estilo." />
        <textarea id="estilo-yue" rows={2} value={docs.style ?? ''} disabled={fase !== 'letra'} onChange={e => setDocs(d => ({ ...d, style: e.target.value }))} />
        <RotuloAjuda campo="letra-yue" rotulo="Letra" ajuda="Edite à vontade. Mantenha as seções entre colchetes ([Verse], [Chorus], [Outro]): a partitura é organizada por elas." />
        <textarea id="letra-yue" rows={16} value={docs.lyrics ?? ''} disabled={fase !== 'letra'} onChange={e => setDocs(d => ({ ...d, lyrics: e.target.value }))} />
        {errosFolha.map(x => <p key={x} className="aviso-atencao">{x}</p>)}
        <div className="opcoes">
          <button className="principal" disabled={fase !== 'letra' || !motorVivo} onClick={() => revisao(proxima('letra'))}>{ocupadoRevisao ? 'Trabalhando…' : `Aprovar e seguir para ${rotuloEtapa[proxima('letra')]}`}</button>
          <button disabled={fase !== 'letra'} onClick={abrirEditor}>Abrir no editor completo</button>
          {!cover && <button disabled={fase !== 'letra'} onClick={() => revisao('letra', true)}>Escrever outra letra</button>}
          {anterior('letra') && <button disabled={fase !== 'letra'} onClick={() => { setCaixa(anterior('letra')!); setFase(anterior('letra')!) }}>Voltar à partitura</button>}
          <button disabled={fase !== 'letra'} onClick={() => { setFase('inicio'); setCaixa(null); setDocs({}) }}>Cancelar</button>
        </div>
      </div>}
      {revisar && caixa === 'partitura' && <div className="revisao-musica">
        <h3>{ordem.indexOf('partitura') + 1} · Partitura</h3>
        <p className="nota">{cover ? 'Melodia e acordes transcritos da gravação (SheetSage2)' : `“${docs.title ?? ''}”`} · cerca de {segundosPartitura ? formatarDuracao(Math.round(segundosPartitura)) : '—'}. A partitura está em notação ABC; para ver e editar como partitura, piano roll, acordes e MIDI, use “Abrir no editor completo”.</p>
        <textarea rows={18} spellCheck={false} style={{ fontFamily: 'monospace', fontSize: 12 }} value={docs.score ?? ''} disabled={fase !== 'partitura'} onChange={e => setDocs(d => ({ ...d, score: e.target.value }))} />
        {errosFolha.map(x => <p key={x} className="aviso-atencao">{x}</p>)}
        <div className="opcoes">
          <button className="principal" disabled={fase !== 'partitura' || !motorVivo} onClick={() => revisao(proxima('partitura'))}>{ocupadoRevisao ? 'Trabalhando…' : `Aprovar e seguir para ${rotuloEtapa[proxima('partitura')]}`}</button>
          <button disabled={fase !== 'partitura'} onClick={abrirEditor}>Abrir no editor completo</button>
          {anterior('partitura') && <button disabled={fase !== 'partitura'} onClick={() => { setCaixa(anterior('partitura')!); setFase(anterior('partitura')!) }}>Voltar à letra</button>}
          {cover && <button disabled={fase !== 'partitura'} onClick={() => { setFase('inicio'); setCaixa(null); setDocs({}) }}>Cancelar</button>}
        </div>
      </div>}
      </>}
    </>}
    {cfg?.letra ? <>
      <RotuloAjuda campo="tipo-musica" rotulo="Tipo de música" ajuda="Escolha instrumental ou com letra. Stable Audio 3 é voltado a instrumentais e efeitos, sem controle de letra." />
      <select id="tipo-musica" value={vocal ? 'com-letra' : 'instrumental'} onChange={e => setVocal(e.target.value === 'com-letra')}>
        <option value="instrumental">Instrumental</option>
        <option value="com-letra">Com letra</option>
      </select>
      {vocal && <><RotuloAjuda campo="letra-musica" rotulo="Letra" ajuda="Digite as palavras a serem cantadas. Use seções como [Verse], [Chorus] e [Bridge] para orientar a estrutura." /><textarea id="letra-musica" rows={8} maxLength={12000} value={letra} onChange={e => setLetra(e.target.value)} placeholder={'[Verse]\nSua letra aqui\n\n[Chorus]\nSeu refrão'} /></>}
    </> : null}
    {!(modelo === 'ace-step15' && referencia) && !plenio && <>
    <RotuloAjuda campo="duracao-musica" rotulo={<>{encerramento === 'original' ? 'Duração solicitada' : 'Duração aproximada'} (segundos)</>} ajuda={`O máximo de ${cfg?.rotulo ?? 'este modelo'} é ${cfg?.maximo ?? 180} segundos. A duração final pode variar conforme o modelo e o encerramento escolhido.`} />
    <input id="duracao-musica" type="number" min={10} max={cfg?.maximo ?? 180} value={duracao} onChange={e => setDuracao(Number(e.target.value))} />
    <RotuloAjuda campo="encerramento-musica" rotulo="Encerramento" ajuda="Natural procura uma pausa perto da duração escolhida e preserva o original se não encontrar. Com letra, não faz corte natural para proteger frases; fade-out pode interrompê-las." />
    <select id="encerramento-musica" value={encerramento} onChange={e => setEncerramento(e.target.value)}>
      <option value="natural">Procurar encerramento natural</option>
      <option value="original">Manter original</option>
      <option value="fade">Aplicar fade-out</option>
    </select>
    {encerramento !== 'original' && <details className="avancado">
      <summary>Margem · {margem} s</summary>
      <RotuloAjuda campo="margem-musica" rotulo="Margem de duração (segundos)" ajuda="Permite até 10 segundos extras em instrumentais para buscar uma pausa final, sem superar o limite do modelo. O original fica salvo." />
      <input id="margem-musica" type="number" min={0} max={10} value={margem} onChange={e => setMargem(Number(e.target.value))} />
    </details>}
    </>}
    {modelo === 'ace-step15' && <details className="avancado">
      <summary>Ajustes musicais · {bpm} BPM · {tonalidade}{vocal && generoVocal !== 'livre' ? ` · ${generoVocal}` : ''}</summary>
      <RotuloAjuda campo="bpm-musica" rotulo="Tempo (BPM)" ajuda="Indica a velocidade musical desejada. O ACE-Step usa o valor como orientação; o resultado pode variar." /><input id="bpm-musica" type="number" min={10} max={300} value={bpm} onChange={e => setBpm(Number(e.target.value))} />
      <RotuloAjuda campo="tonalidade-musica" rotulo="Tonalidade musical" ajuda="Envia a nota e a escala maior ou menor ao ACE-Step. A tonalidade gerada pode não ser exata." />
      <select id="tonalidade-musica" value={tonalidade} onChange={e => setTonalidade(e.target.value)}>
        {(['major', 'minor'] as const).flatMap(modo => notasAce.map(nota => <option key={`${nota} ${modo}`} value={`${nota} ${modo}`}>{nota} {modo === 'major' ? 'maior' : 'menor'}</option>))}
      </select>
      {vocal && <>
        <RotuloAjuda campo="genero-vocal-musica" rotulo="Gênero do vocal" ajuda="Acrescenta voz feminina ou masculina à descrição. É uma preferência, não uma garantia; com guia, a voz também pode ser reinterpretada." />
        <select id="genero-vocal-musica" value={generoVocal} onChange={e => setGeneroVocal(e.target.value)}>
          <option value="livre">Sem preferência</option>
          <option value="feminino">Feminino</option>
          <option value="masculino">Masculino</option>
        </select>
        <RotuloAjuda campo="idioma-musica" rotulo="Idioma da letra" ajuda="Indica o idioma ao ACE-Step; escreva a letra nesse idioma. Não traduz o texto automaticamente." /><select id="idioma-musica" value={idioma} onChange={e => setIdioma(e.target.value)}>{Object.entries({pt:'Português',en:'Inglês',es:'Espanhol',de:'Alemão',it:'Italiano',fr:'Francês',ja:'Japonês',zh:'Chinês',ko:'Coreano'}).map(([v,r]) => <option key={v} value={v}>{r}</option>)}</select>
      </>}
    </details>}
    {plenio && revisar ? caixa === null && <button className="principal" onClick={() => revisao(ordem[0], true)} disabled={ocupadoRevisao || subindo || !motorVivo || !cfg?.disponivel || !prompt.trim() || (cover && !referencia)}>{ocupadoRevisao ? (ordem[0] === 'partitura' ? 'Transcrevendo a gravação…' : 'Escrevendo a letra…') : (ordem[0] === 'partitura' ? 'Transcrever a gravação' : 'Escrever a letra')}</button> :
    <button className="principal" onClick={gerar} disabled={subindo || enviando || !motorVivo || !cfg?.disponivel || !prompt.trim() || margem < 0 || margem > 10 || duracao < 10 || duracao > cfg.maximo || (vocal && cfg.letra && !letra.trim())}>{enviando ? 'Enviando…' : 'Gerar música'}</button>}
  </div>
}
