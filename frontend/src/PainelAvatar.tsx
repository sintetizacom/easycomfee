import { useEffect, useState } from 'react'
import { api, referenciaDaGaleria, urlEntrada, urlImagem, type ItemGaleria } from './api'
import RotuloAjuda from './RotuloAjuda'

// LongCat-Avatar 1.5, medido em 03/10/2026: 14,6 s de fala em 1012 s
// (~70 s por segundo). Aos 30 s os labios ganham cor de batom e o rosto vira
// de frente; aos 15 s nada disso aparece.
// Os valores reais vem do servidor (/api/avatar); estes so valem ate ele responder.
type ModeloAvatar = { id: string; rotulo: string; limite: number; resolucao: string
  segundos_por_segundo: number; disponivel: boolean; motivo: string }
const PADRAO: ModeloAvatar = { id: 'longcat', rotulo: 'LongCat 1.5', limite: 15, resolucao: '832×480',
  segundos_por_segundo: 70, disponivel: true, motivo: '' }

const ehImagem = (i: ItemGaleria) =>
  !i.duracao_video && i.modelo !== 'voz' && i.modelo !== 'musica'

function formatarMinutos(segundos: number) {
  const min = Math.max(1, Math.round(segundos / 60))
  return min === 1 ? '~1 min' : `~${min} min`
}

export default function PainelAvatar({ motorVivo, aoErro, galeria }: {
  motorVivo: boolean; aoErro: (s: string) => void; galeria: ItemGaleria[]
}) {
  const [caps, setCaps] = useState<{ disponivel: boolean; motivo: string; modelos?: ModeloAvatar[] } | null>(null)
  // Os dois motores ficam lado a lado para comparar (14/10/2026).
  const [modeloId, setModeloId] = useState('longcat')
  const modelo = caps?.modelos?.find(m => m.id === modeloId) ?? PADRAO
  const LIMITE = modelo.limite
  const SEGUNDOS_POR_SEGUNDO = modelo.segundos_por_segundo
  // 9:16 so existe no LTX 2.3; o LongCat foi medido so na horizontal.
  const [formato, setFormato] = useState<'horizontal' | 'vertical'>('horizontal')
  const vertical = modeloId === 'ltx23' && formato === 'vertical'
  const resolucao = vertical ? '704×1280' : modelo.resolucao
  // A foto escolhida, antes do recorte: trocar o formato recorta de novo.
  const [original, setOriginal] = useState('')
  const [foto, setFoto] = useState('')
  // null = ainda nao recortou; false = nao achou rosto e usou a foto inteira
  const [rosto, setRosto] = useState<boolean | null>(null)
  const [fala, setFala] = useState('')
  const [duracao, setDuracao] = useState<number | null>(null)
  const [cena, setCena] = useState('')
  const [subindo, setSubindo] = useState(false)
  const [enviando, setEnviando] = useState(false)

  // A galeria da tela traz so as 60 mais recentes; as listas daqui precisam
  // de todas as vozes e fotos, inclusive as antigas.
  const [acervo, setAcervo] = useState<ItemGaleria[]>([])
  useEffect(() => { api.galeria(2000).then(setAcervo).catch(() => {}) }, [galeria])
  const itens = acervo.length ? acervo : galeria

  useEffect(() => {
    fetch('/api/avatar').then(r => r.json()).then(setCaps)
      .catch(() => setCaps({ disponivel: false, motivo: 'Não foi possível consultar o motor.' }))
  }, [motorVivo])

  const subir = async (f: () => Promise<void>) => {
    setSubindo(true); aoErro('')
    try { await f() } catch (e) { aoErro(String(e)) } finally { setSubindo(false) }
  }

  // A foto sobe inteira e o servidor devolve o recorte de cabeca e ombros.
  // Com a foto inteira, a boca tinha poucos pixels e os dentes saiam borrados.
  const usarFoto = async (nome: string, emPe = vertical) => {
    setOriginal(nome); setFoto(''); setRosto(null)
    const r = await fetch('/api/avatar/recorte', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ foto: nome, vertical: emPe }) })
    const d = await r.json()
    if (!r.ok) throw new Error(d.detail ?? 'Não foi possível preparar a foto.')
    setFoto(d.nome); setRosto(d.rosto)
  }

  useEffect(() => {
    if (original) subir(() => usarFoto(original, vertical))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vertical])

  const fotoDaGaleria = (id: string) => subir(async () => {
    const item = itens.find(i => i.id === Number(id)); if (!item) return
    await usarFoto((await referenciaDaGaleria(item)).nome)
  })

  const falaDaGaleria = (id: string) => subir(async () => {
    const item = itens.find(i => i.id === Number(id)); if (!item) return
    setFala(''); setDuracao(null)
    const r = await fetch(urlImagem({ nome: item.arquivo, subpasta: item.subpasta }))
    if (!r.ok) throw new Error('Não foi possível carregar a voz salva.')
    setFala((await api.enviarAudio(new File([await r.blob()], item.arquivo, { type: 'audio/flac' }))).nome)
  })

  const longa = duracao !== null && duracao > LIMITE + 0.05
  const pronto = !!foto && !!fala && duracao !== null && !longa && modelo.disponivel && !!caps?.disponivel && motorVivo

  const gerar = async () => {
    setEnviando(true); aoErro('')
    try {
      const r = await fetch('/api/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ modelo: 'avatar', prompt: cena, referencias: [foto], referencia_avatar: fala, modelo_avatar: modeloId, vertical_avatar: vertical }) })
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail ?? 'Falha ao gerar o avatar') }
    } catch (e) { aoErro(String(e)) } finally { setEnviando(false) }
  }

  return <div className="painel-voz">
    <h2>Avatar</h2>
    <p className="nota">Uma foto e uma fala viram um vídeo da pessoa falando, com a boca sincronizada. Até {LIMITE} s, em {resolucao}.</p>
    {caps && !caps.disponivel && <p className="aviso-atencao">{caps.motivo}</p>}

    <RotuloAjuda campo="modelo-avatar" rotulo="Modelo" ajuda="LongCat 1.5: especializado em rosto falando, 832×480, até 15 s (~70 s de processamento por segundo de fala). LTX 2.3: cena inteira em 1280×704, até 30 s, bem mais rápido (~15 s por segundo); a foto é presa no início e no fim para a câmera não se afastar." />
    <select id="modelo-avatar" value={modeloId} onChange={e => setModeloId(e.target.value)}>
      {(caps?.modelos ?? [PADRAO]).map(m => <option key={m.id} value={m.id} disabled={!m.disponivel}>
        {m.rotulo} — até {m.limite} s, {m.resolucao}{m.disponivel ? '' : ' — indisponível'}</option>)}
    </select>
    {!modelo.disponivel && modelo.motivo && <p className="aviso-atencao">{modelo.motivo}</p>}

    {modeloId === 'ltx23' && <>
      <RotuloAjuda campo="formato-avatar" rotulo="Formato" ajuda="Horizontal 16:9 (1280×704) ou vertical 9:16 (704×1280, para Reels, Shorts e TikTok). O recorte da foto em volta do rosto segue o formato escolhido." />
      <select id="formato-avatar" value={formato} onChange={e => setFormato(e.target.value as 'horizontal' | 'vertical')}>
        <option value="horizontal">Horizontal 16:9 — 1280×704</option>
        <option value="vertical">Vertical 9:16 — 704×1280</option>
      </select>
    </>}

    <RotuloAjuda campo="foto-avatar" rotulo="Foto da pessoa" ajuda="Rosto bem visível, de frente ou levemente de lado. A foto é recortada automaticamente em cabeça e ombros, em volta do rosto: assim a boca tem pixels suficientes para os dentes saírem nítidos." />
    <select id="foto-avatar" value="" disabled={subindo} onChange={e => fotoDaGaleria(e.target.value)}>
      <option value="">Escolher uma imagem da galeria…</option>
      {itens.filter(ehImagem).map(i =>
        <option key={i.id} value={i.id}>{(i.rotulo || i.prompt || i.arquivo).slice(0, 70)}</option>)}
    </select>
    <input type="file" accept="image/*" aria-label="Ou enviar uma foto" disabled={subindo} onChange={e => {
      const f = e.target.files?.[0]; if (!f) return
      subir(async () => usarFoto((await api.enviarReferencia(f)).nome))
    }} />
    {foto && <img className="previa-avatar" src={urlEntrada(foto)} alt="Enquadramento que será animado" />}
    {rosto === false && <p className="aviso-atencao">Nenhum rosto encontrado com segurança — a foto será usada inteira, e a boca pode sair menos nítida.</p>}

    <RotuloAjuda campo="fala-avatar" rotulo="Fala" ajuda={`Áudio só com voz, sem música de fundo, de até ${LIMITE} segundos. Pode ser uma narração gerada na aba Voz.`} />
    <select id="fala-avatar" value="" disabled={subindo} onChange={e => falaDaGaleria(e.target.value)}>
      <option value="">Escolher uma voz da galeria…</option>
      {itens.filter(i => i.modelo === 'voz').map(i =>
        <option key={i.id} value={i.id}>{(i.rotulo ? `${i.rotulo} — ` : '') + i.prompt.slice(0, 60)}</option>)}
    </select>
    <input type="file" accept="audio/*,.wav,.mp3,.flac,.ogg" aria-label="Ou enviar um áudio" disabled={subindo} onChange={e => {
      const f = e.target.files?.[0]; if (!f) return
      setFala(''); setDuracao(null)
      subir(async () => setFala((await api.enviarAudio(f)).nome))
    }} />
    {fala && <audio key={fala} controls preload="metadata" aria-label="Ouvir a fala" src={urlEntrada(fala)}
      onLoadedMetadata={e => setDuracao(e.currentTarget.duration)}
      onError={() => aoErro('Não foi possível ler o áudio. Tente WAV, FLAC ou MP3.')} />}
    {duracao !== null && (longa
      ? <p className="aviso-atencao">A fala tem {duracao.toFixed(1)} s. O limite é {LIMITE} s — corte o áudio ou divida o texto.</p>
      : <p className="nota">{duracao.toFixed(1)} s de fala · geração estimada em {formatarMinutos(duracao * SEGUNDOS_POR_SEGUNDO)}</p>)}

    <RotuloAjuda campo="cena-avatar" rotulo="Descrição da cena (opcional)" ajuda="Em inglês funciona melhor. Descreva a pessoa e o ambiente como estão na foto. A câmera fixa é acrescentada sempre." />
    <textarea id="cena-avatar" rows={3} maxLength={600} value={cena} onChange={e => setCena(e.target.value)}
      placeholder="Ex.: A woman in a leather jacket speaks to the camera in a woodworking workshop" />

    <button className="principal" disabled={!pronto || enviando || subindo} onClick={gerar}>
      {enviando ? 'Enviando…' : 'Gerar avatar'}
    </button>
  </div>
}
