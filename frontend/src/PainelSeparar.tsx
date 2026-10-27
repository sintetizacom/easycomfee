import { useEffect, useState } from 'react'
import { api, urlEntrada, type ItemGaleria } from './api'
import RotuloAjuda from './RotuloAjuda'

// Teste de 08/10/2026: 3,5 min de musica em 11 s (6 faixas) e 30 s (4 faixas).
type Modo = { id: string; rotulo: string }

export default function PainelSeparar({ motorVivo, aoErro, galeria }: {
  motorVivo: boolean; aoErro: (s: string) => void; galeria: ItemGaleria[]
}) {
  const [caps, setCaps] = useState<{ disponivel: boolean; motivo: string; modos?: Modo[] } | null>(null)
  const [item, setItem] = useState(0)
  const [enviado, setEnviado] = useState('')
  const [modo, setModo] = useState('4')
  const [formato, setFormato] = useState<'flac' | 'mp3'>('flac')
  const [subindo, setSubindo] = useState(false)
  const [enviando, setEnviando] = useState(false)

  // A galeria da tela traz so as 60 mais recentes; aqui interessam todas as musicas.
  const [acervo, setAcervo] = useState<ItemGaleria[]>([])
  useEffect(() => { api.galeria(2000).then(setAcervo).catch(() => {}) }, [galeria])
  const musicas = (acervo.length ? acervo : galeria).filter(i => i.modelo === 'musica')

  useEffect(() => {
    fetch('/api/separar').then(r => r.json()).then(setCaps)
      .catch(() => setCaps({ disponivel: false, motivo: 'Não foi possível consultar o separador.' }))
  }, [])

  const escolhido = musicas.find(i => i.id === item)
  const pronto = (!!item || !!enviado) && !!caps?.disponivel && motorVivo

  const separar = async () => {
    setEnviando(true); aoErro('')
    try {
      const r = await fetch('/api/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ modelo: 'separar', prompt: '', modo_separar: modo, formato_separar: formato,
          separar_item: item || 0, referencia_separar: item ? '' : enviado }) })
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail ?? 'Falha ao separar') }
    } catch (e) { aoErro(String(e)) } finally { setEnviando(false) }
  }

  return <div className="painel-voz">
    <h2>Separar faixas</h2>
    <p className="nota">Divide uma música em faixas — voz, bateria, baixo e outros instrumentos. Cada faixa entra na galeria como um áudio.</p>
    {caps && !caps.disponivel && <p className="aviso-atencao">{caps.motivo}</p>}

    <RotuloAjuda campo="musica-separar" rotulo="Música" ajuda="Escolha uma música da galeria ou envie um arquivo seu (WAV, MP3, FLAC ou OGG)." />
    <select id="musica-separar" value={item || ''} disabled={subindo} onChange={e => { setItem(Number(e.target.value)); setEnviado('') }}>
      <option value="">Escolher uma música da galeria…</option>
      {musicas.map(i => <option key={i.id} value={i.id}>{(i.rotulo || i.prompt || i.arquivo).slice(0, 70)}</option>)}
    </select>
    <input type="file" accept="audio/*,.wav,.mp3,.flac,.ogg" aria-label="Ou enviar uma música" disabled={subindo} onChange={async e => {
      const f = e.target.files?.[0]; if (!f) return
      setSubindo(true); aoErro(''); setItem(0); setEnviado('')
      try { setEnviado((await api.enviarAudio(f)).nome) } catch (err) { aoErro(String(err)) } finally { setSubindo(false) }
    }} />
    {(escolhido || enviado) && <audio key={item || enviado} controls preload="metadata" aria-label="Ouvir a música"
      src={escolhido ? `/api/imagem?nome=${encodeURIComponent(escolhido.arquivo)}&subpasta=${encodeURIComponent(escolhido.subpasta)}` : urlEntrada(enviado)} />}

    <RotuloAjuda campo="modo-separar" rotulo="Como separar" ajuda="4 faixas é o mais limpo. 6 faixas acrescenta guitarra e piano, mas o piano costuma sair fraco — teclados podem ir para “outros”. Voz e instrumental usa o modelo mais preciso para voz." />
    <select id="modo-separar" value={modo} onChange={e => setModo(e.target.value)}>
      {(caps?.modos ?? []).map(m => <option key={m.id} value={m.id}>{m.rotulo}</option>)}
    </select>

    <RotuloAjuda campo="formato-separar" rotulo="Formato das faixas" ajuda="FLAC é sem perda, o melhor para mixar. MP3 (320 kbps) ocupa cerca de um terço e abre em qualquer lugar." />
    <div className="opcoes segmentado" id="formato-separar">
      <button data-ativo={formato === 'flac'} onClick={() => setFormato('flac')}>FLAC</button>
      <button data-ativo={formato === 'mp3'} onClick={() => setFormato('mp3')}>MP3</button>
    </div>

    <button className="principal" disabled={!pronto || enviando || subindo} onClick={separar}>
      {enviando ? 'Enviando…' : 'Separar faixas'}
    </button>
  </div>
}
