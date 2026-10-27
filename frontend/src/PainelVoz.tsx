import { useEffect, useRef, useState } from 'react'
import { api, urlImagem, type ItemGaleria } from './api'
import RotuloAjuda from './RotuloAjuda'

const idiomas = { Portuguese: "Português", English: "Inglês", Spanish: "Espanhol", German: "Alemão", Italian: "Italiano", French: "Francês", Japanese: "Japonês", Chinese: "Chinês", Korean: "Coreano" }
const idiomasASR = new Set(["Portuguese", "English", "Spanish", "German", "French", "Japanese"])

export default function PainelVoz({ motorVivo, aoErro, reuso, galeria }: { motorVivo: boolean; aoErro: (s: string) => void; reuso: ItemGaleria | null; galeria: ItemGaleria[] }) {
  const [modo, setModo] = useState('narrar')
  const [idioma, setIdioma] = useState('Portuguese')
  const [idiomaReferencia, setIdiomaReferencia] = useState('Portuguese')
  const [texto, setTexto] = useState('')
  const [nomeVoz, setNomeVoz] = useState('')
  const [tituloAudio, setTituloAudio] = useState('')
  const [referencia, setReferencia] = useState('')
  const [transcricao, setTranscricao] = useState('')
  const [genero, setGenero] = useState('female')
  const [idade, setIdade] = useState('young adult')
  const [pitch, setPitch] = useState('moderate pitch')
  const [estilo, setEstilo] = useState('')
  const [sotaque, setSotaque] = useState('')
  const [duracaoReferencia, setDuracaoReferencia] = useState<number | null>(null)
  const campoTexto = useRef<HTMLTextAreaElement>(null)
  const [velocidade, setVelocidade] = useState(1)
  const [enviando, setEnviando] = useState(false)
  const [transcrevendo, setTranscrevendo] = useState(false)
  const [tarefaTranscricao, setTarefaTranscricao] = useState<{ id: string; referencia: string } | null>(null)
  const [estadoTranscricao, setEstadoTranscricao] = useState('')
  const referenciaAtual = useRef(referencia)
  referenciaAtual.current = referencia
  const [caps, setCaps] = useState<{ disponivel: boolean; motivo: string; design: boolean; transcricao: boolean }>()
  useEffect(() => {
    try {
      const salva = JSON.parse(sessionStorage.getItem('transcricaoVoz') ?? 'null')
      if (salva?.id && salva?.referencia) {
        setReferencia(salva.referencia); setModo('clonar'); setTarefaTranscricao(salva)
      }
    } catch { /* Armazenamento indisponível: segue com o formulário atual. */ }
  }, [])
  useEffect(() => {
    if (!tarefaTranscricao) return
    let ativo = true
    let timer: ReturnType<typeof setTimeout>
    const controller = new AbortController()
    const terminar = () => {
      setTarefaTranscricao(null); setEstadoTranscricao('')
      try { sessionStorage.removeItem('transcricaoVoz') } catch { /* sem armazenamento */ }
    }
    const consultar = async () => {
      try {
        const r = await fetch(`/api/voz/transcricao/${encodeURIComponent(tarefaTranscricao.id)}`, { signal: controller.signal })
        if (r.status === 404) { if (ativo) { terminar(); aoErro('A transcrição não foi encontrada. Envie o áudio novamente.') } return }
        if (!r.ok) throw new Error('Servidor indisponível')
        const t = await r.json()
        if (!ativo) return
        if (t.estado === 'pronto') {
          if (referenciaAtual.current === tarefaTranscricao.referencia) setTranscricao(t.resultado_texto)
          terminar(); return
        }
        if (t.estado === 'erro') { terminar(); aoErro(t.erro); return }
        setEstadoTranscricao(t.estado === 'na_fila' ? 'Aguardando na fila…' : 'Transcrevendo áudio…')
      } catch {
        if (ativo) setEstadoTranscricao('Aguardando conexão com o servidor…')
      }
      if (ativo) timer = setTimeout(consultar, 1500)
    }
    void consultar()
    return () => { ativo = false; controller.abort(); clearTimeout(timer) }
  }, [tarefaTranscricao, aoErro])
  const ocupadoTranscricao = transcrevendo || !!tarefaTranscricao
  const transcrever = async () => {
    setTranscrevendo(true); aoErro('')
    try {
      const r = await fetch('/api/voz/transcrever', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ referencia, idioma: idiomaReferencia }) })
      const t = await r.json()
      if (!r.ok) throw new Error(t.detail ?? 'Não foi possível transcrever o áudio.')
      const pendente = { id: t.id, referencia }
      try { sessionStorage.setItem('transcricaoVoz', JSON.stringify(pendente)) } catch { /* sem armazenamento */ }
      setTarefaTranscricao(pendente)
    } catch (e) { aoErro(String(e)) } finally { setTranscrevendo(false) }
  }
  useEffect(() => {
    let ativo = true
    fetch('/api/voz').then(r => { if (!r.ok) throw new Error('Não foi possível consultar o motor de voz.'); return r.json() })
      .then(v => { if (ativo) setCaps(v) }).catch(e => { if (ativo) aoErro(String(e)) })
    return () => { ativo = false }
  }, [motorVivo, aoErro])
  useEffect(() => {
    if (!reuso) return
    const p = reuso.parametros
    setNomeVoz(String(p.nome_voz ?? '')); setTituloAudio(String(p.titulo_audio_voz ?? ''))
    setTexto(reuso.prompt); setModo(String(p.modo_voz ?? 'narrar'))
    setReferencia(String(p.referencia_voz ?? '')); setTranscricao(String(p.transcricao_voz ?? '')); setDuracaoReferencia(null)
    setIdioma(String(p.idioma_voz ?? "Portuguese")); setIdiomaReferencia(String(p.idioma_referencia_voz ?? "Portuguese"))
    setVelocidade(Number(p.velocidade_voz ?? 1))
    const partes = String(p.instrucao_voz ?? '').split(',').map(s => s.trim())
    if (['female', 'male'].includes(partes[0])) setGenero(partes[0])
    setIdade(partes.find(s => ['child', 'teenager', 'young adult', 'middle-aged', 'elderly'].includes(s)) ?? 'young adult')
    setPitch(partes.find(s => ['very low pitch', 'low pitch', 'moderate pitch', 'high pitch', 'very high pitch'].includes(s)) ?? 'moderate pitch')
    setEstilo(partes.includes('whisper') ? 'whisper' : '')
    setSotaque(partes.find(s => ['american', 'british', 'australian', 'canadian', 'indian', 'chinese', 'korean', 'japanese', 'portuguese', 'russian'].some(a => s === `${a} accent`)) ?? '')
  }, [reuso])
  const inserirMarca = (marca: string) => {
    const campo = campoTexto.current
    if (!campo) return
    const inicio = campo.selectionStart
    const fim = campo.selectionEnd
    const proximo = texto.slice(0, inicio) + marca + texto.slice(fim)
    if (proximo.length > 12000) return
    setTexto(proximo)
    requestAnimationFrame(() => { campo.focus(); campo.setSelectionRange(inicio + marca.length, inicio + marca.length) })
  }
  const gerar = async () => {
    setEnviando(true); aoErro('')
    try {
      const r = await fetch('/api/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({
        modelo: 'voz', idioma_voz: idioma, idioma_referencia_voz: idiomaReferencia, prompt: texto, modo_voz: modo, referencia_voz: referencia,
        nome_voz: nomeVoz, titulo_audio_voz: tituloAudio,
        transcricao_voz: transcricao, instrucao_voz: [genero, idade, pitch, estilo, idioma === 'English' ? sotaque : ''].filter(Boolean).join(', '),
        velocidade_voz: velocidade,
      }) })
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail ?? 'Falha ao gerar voz') }
    } catch (e) { aoErro(String(e)) } finally { setEnviando(false) }
  }
  return <div className="painel-voz">
    <h2>Voz</h2>
    <RotuloAjuda campo="nome-voz" rotulo="Voz" ajuda="Nome opcional da voz ou personagem. Ele identifica o arquivo salvo; caracteres especiais são normalizados." />
    <input id="nome-voz" maxLength={120} value={nomeVoz} onChange={e => setNomeVoz(e.target.value)} placeholder="Ex.: Narradora Ana" />
    <RotuloAjuda campo="titulo-audio-voz" rotulo="Título do áudio" ajuda="Nome opcional deste áudio. Entra no nome do arquivo salvo, com um número para evitar sobrescrever resultados." />
    <input id="titulo-audio-voz" maxLength={120} value={tituloAudio} onChange={e => setTituloAudio(e.target.value)} placeholder="Ex.: Abertura do episódio" />
    <RotuloAjuda campo="modo-voz" rotulo="O que você quer fazer?" ajuda="Gere uma narração, crie uma voz a partir das características escolhidas ou use um áudio como referência de voz." />
    <select id="modo-voz" value={modo} disabled={ocupadoTranscricao} onChange={e => setModo(e.target.value)}>
      <option value="narrar">Gerar narração</option>
      <option value="criar" disabled={!caps?.design}>Criar uma voz</option>
      <option value="clonar">Usar voz de referência</option>
    </select>
    <RotuloAjuda campo="idioma-voz" rotulo="Idioma da narração" ajuda="Escreva o texto no idioma escolhido. Essa seleção orienta a pronúncia, mas não traduz o texto." />
    <select id="idioma-voz" value={idioma} onChange={e => setIdioma(e.target.value)}>{Object.entries(idiomas).map(([valor, rotulo]) => <option key={valor} value={valor}>{rotulo}</option>)}</select>
    <RotuloAjuda campo="texto-voz" rotulo="Texto da narração" ajuda="Digite no idioma escolhido. O OmniVoice aceita [laughter] e [sigh] para sons expressivos. Em inglês, é possível indicar pronúncia fonética entre colchetes, por exemplo [B EY1 S]." />
    <textarea ref={campoTexto} id="texto-voz" value={texto} onChange={e => setTexto(e.target.value)} maxLength={12000} rows={8} placeholder="Escreva o texto que será falado…" />
    <div className="atalhos-voz" aria-label="Inserir expressão no texto"><button type="button" onClick={() => inserirMarca('[laughter] ')}>+ Risada</button><button type="button" onClick={() => inserirMarca('[sigh] ')}>+ Suspiro</button></div>
    {modo === 'criar' && <>
      <RotuloAjuda campo="genero-voz" rotulo="Voz" ajuda="Escolha uma voz de caráter feminino ou masculino. O resultado pode variar entre gerações." /><select id="genero-voz" value={genero} onChange={e => setGenero(e.target.value)}><option value="female">Feminina</option><option value="male">Masculina</option></select>
      <details className="avancado"><summary>Características da voz</summary>
        <RotuloAjuda campo="idade-voz" rotulo="Idade aparente" ajuda="Orienta o caráter da voz criada; não determina a idade real de uma pessoa." /><select id="idade-voz" value={idade} onChange={e => setIdade(e.target.value)}><option value="child">Criança</option><option value="teenager">Adolescente</option><option value="young adult">Adulto jovem</option><option value="middle-aged">Meia-idade</option><option value="elderly">Idoso</option></select>
        <RotuloAjuda campo="tom-voz" rotulo="Tom" ajuda="Altura aproximada da voz. Combinações de características podem ser interpretadas de modo variável." /><select id="tom-voz" value={pitch} onChange={e => setPitch(e.target.value)}><option value="very low pitch">Muito grave</option><option value="low pitch">Grave</option><option value="moderate pitch">Médio</option><option value="high pitch">Agudo</option><option value="very high pitch">Muito agudo</option></select>
        <RotuloAjuda campo="estilo-voz" rotulo="Estilo" ajuda="Sussurro é o estilo adicional documentado para criação de voz. Pode não funcionar igualmente bem em todos os idiomas." /><select id="estilo-voz" value={estilo} onChange={e => setEstilo(e.target.value)}><option value="">Normal</option><option value="whisper">Sussurro</option></select>
        {idioma === 'English' && <><RotuloAjuda campo="sotaque-voz" rotulo="Sotaque do inglês" ajuda="Aplica-se apenas a texto em inglês. É uma orientação para o modelo, sem garantia de resultado exato." /><select id="sotaque-voz" value={sotaque} onChange={e => setSotaque(e.target.value)}><option value="">Livre</option>{['american', 'british', 'australian', 'canadian', 'indian', 'chinese', 'korean', 'japanese', 'portuguese', 'russian'].map(a => <option key={a} value={`${a} accent`}>{a.charAt(0).toUpperCase() + a.slice(1)}</option>)}</select></>}
      </details>
    </>}
    {modo === 'clonar' && <>
      <RotuloAjuda campo="biblioteca-voz" rotulo="Voz da biblioteca" ajuda="Escolha uma narração salva na galeria para usá-la como referência. O áudio será carregado no campo abaixo." />
      <select id="biblioteca-voz" value="" disabled={enviando || ocupadoTranscricao} onChange={async e => {
        const item = galeria.find(i => i.id === Number(e.target.value)); if (!item) return
        setEnviando(true); setReferencia(''); aoErro('')
        try {
          const r = await fetch(urlImagem({ nome: item.arquivo, subpasta: item.subpasta }))
          if (!r.ok) throw new Error('Não foi possível carregar a voz salva.')
          const v = await api.enviarAudio(new File([await r.blob()], item.arquivo, { type: 'audio/flac' }))
          setReferencia(v.nome); setDuracaoReferencia(null); setTranscricao(item.prompt); setIdiomaReferencia(String(item.parametros.idioma_voz ?? "Portuguese"))
        } catch (err) { aoErro(String(err)) } finally { setEnviando(false) }
      }}>
        <option value="">Escolher uma narração salva…</option>
        {galeria.filter(i => i.modelo === 'voz').map(i => <option key={i.id} value={i.id}>{i.prompt.slice(0, 70)}</option>)}
      </select>
      <RotuloAjuda campo="arquivo-referencia-voz" rotulo="Ou enviar áudio de referência" ajuda="Prefira 3 a 10 segundos de fala limpa, com autorização de uso. Áudios mais longos podem piorar a clonagem. Gravar no mesmo idioma da narração tende a melhorar a pronúncia; entre idiomas, o sotaque da referência pode aparecer no resultado." />
      <input id="arquivo-referencia-voz" type="file" accept="audio/*,.wav,.mp3,.flac,.m4a,.ogg" disabled={enviando || ocupadoTranscricao} onChange={async e => {
        const f = e.target.files?.[0]; if (!f) return
        setEnviando(true); setReferencia(''); setTranscricao(''); setDuracaoReferencia(null)
        try { const v = await api.enviarAudio(f); setReferencia(v.nome) } catch (err) { aoErro(String(err)) } finally { setEnviando(false) }
      }} />
      {referencia && <audio key={referencia} controls preload="metadata" aria-label="Áudio de referência" src={`/api/imagem?tipo=input&nome=${encodeURIComponent(referencia)}`} onLoadedMetadata={e => setDuracaoReferencia(Number.isFinite(e.currentTarget.duration) ? e.currentTarget.duration : null)} onError={() => aoErro("Não foi possível reproduzir o áudio. Envie o arquivo novamente ou tente WAV ou MP3.")} />}
      {duracaoReferencia !== null && (duracaoReferencia < 3 || duracaoReferencia > 10) && <p className="aviso-atencao">Esta referência tem {duracaoReferencia.toFixed(1)} s. O OmniVoice recomenda entre 3 e 10 s de fala limpa; recorte o áudio para melhorar a clonagem.</p>}
      <RotuloAjuda campo="idioma-referencia" rotulo="Idioma do áudio de referência" ajuda="Informe o idioma falado no áudio para orientar a transcrição automática. Alguns idiomas exigem transcrição manual." />
      <select id="idioma-referencia" disabled={ocupadoTranscricao} value={idiomaReferencia} onChange={e => setIdiomaReferencia(e.target.value)}>{Object.entries(idiomas).map(([valor, rotulo]) => <option key={valor} value={valor}>{rotulo}</option>)}</select>
      {!idiomasASR.has(idiomaReferencia) && <p className="nota">A transcrição automática ainda não aceita esse idioma. Digite a fala exata no campo abaixo.</p>}
      <button onClick={transcrever} disabled={enviando || ocupadoTranscricao || !referencia || !caps?.transcricao || !idiomasASR.has(idiomaReferencia)}>
        {ocupadoTranscricao ? (estadoTranscricao || 'Enviando transcrição…') : 'Transcrever áudio'}
      </button>
      <RotuloAjuda campo="transcricao-voz" rotulo="O que é dito no áudio de referência?" ajuda="Transcreva ou digite a fala exata. Confira e corrija o texto reconhecido antes de gerar; a transcrição automática usa a mesma fila das imagens e vídeos." />
      <textarea id="transcricao-voz" rows={3} disabled={ocupadoTranscricao} value={transcricao} onChange={e => setTranscricao(e.target.value)} placeholder="Clique em Transcrever áudio ou digite a fala exata." />
    </>}
    <RotuloAjuda campo="velocidade-voz" rotulo={`Velocidade: ${velocidade.toFixed(2)}×`} ajuda="Ajuste a velocidade de leitura. 1× é normal; valores menores desaceleram e maiores aceleram a fala." />
    <input id="velocidade-voz" type="range" min="0.5" max="2" step="0.05" value={velocidade} onChange={e => setVelocidade(Number(e.target.value))} />
    {caps?.motivo && <p className="aviso-atencao">{caps.motivo}</p>}
    <button className="principal" onClick={gerar} disabled={enviando || ocupadoTranscricao || !caps?.disponivel || !texto.trim() || (modo === 'clonar' && (!referencia || !transcricao.trim()))}>{enviando ? 'Enviando…' : 'Gerar voz'}</button>
  </div>
}
