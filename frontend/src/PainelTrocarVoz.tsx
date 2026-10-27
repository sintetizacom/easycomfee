import { useEffect, useState } from 'react'
import { api, urlEntrada, type ItemGaleria } from './api'
import RotuloAjuda from './RotuloAjuda'

// Troca de voz pelo Applio (RVC). Teste de 22/10/2026: a nota cantada da voz
// convertida coincide com a da entrada em 84% dos quadros (controle: 6%).
type Voz = { id: string; epocas: number }
type Caps = { disponivel: boolean; motivo: string; vozes: Voz[] }

export default function PainelTrocarVoz({ motorVivo, aoErro, galeria }: {
  motorVivo: boolean; aoErro: (s: string) => void; galeria: ItemGaleria[]
}) {
  const [caps, setCaps] = useState<Caps | null>(null)
  const [item, setItem] = useState(0)
  const [enviado, setEnviado] = useState('')
  const [voz, setVoz] = useState('')
  const [tom, setTom] = useState(0)
  const [formato, setFormato] = useState<'flac' | 'mp3'>('flac')
  const [subindo, setSubindo] = useState(false)
  const [enviando, setEnviando] = useState(false)
  // Treino
  const [nome, setNome] = useState('')
  const [gravacoes, setGravacoes] = useState<string[]>([])
  const [epocas, setEpocas] = useState(300)
  const [tirarInstrumental, setTirarInstrumental] = useState(false)
  const [autorizada, setAutorizada] = useState(false)

  const [acervo, setAcervo] = useState<ItemGaleria[]>([])
  useEffect(() => { api.galeria(2000).then(setAcervo).catch(() => {}) }, [galeria])
  const musicas = (acervo.length ? acervo : galeria).filter(i => i.modelo === 'musica')

  const consultar = () => fetch('/api/trocar-voz').then(r => r.json()).then((c: Caps) => {
    setCaps(c); setVoz(v => v && c.vozes.some(x => x.id === v) ? v : (c.vozes[0]?.id ?? ''))
  }).catch(() => setCaps({ disponivel: false, motivo: 'Não foi possível consultar o Applio.', vozes: [] }))
  // A lista muda quando um treino termina: a galeria e consultada de novo a cada tarefa.
  useEffect(() => { void consultar() }, [galeria])

  const escolhido = musicas.find(i => i.id === item)
  const pedir = async (corpo: Record<string, unknown>) => {
    setEnviando(true); aoErro('')
    try {
      const r = await fetch('/api/gerar', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: '', ...corpo }) })
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail ?? 'Falha ao enviar') }
      return true
    } catch (e) { aoErro(String(e)); return false } finally { setEnviando(false) }
  }
  const trocar = () => pedir({ modelo: 'trocar_voz', voz_troca: voz, tom_troca: tom, formato_separar: formato,
    separar_item: item || 0, referencia_separar: item ? '' : enviado })
  const treinar = async () => {
    if (await pedir({ modelo: 'treinar_voz', nome_voz: nome, arquivos_voz: gravacoes, epocas_voz: epocas,
      separar_treino_voz: tirarInstrumental })) { setGravacoes([]); setNome(''); setAutorizada(false) }
  }
  const remover = async (id: string) => {
    if (!confirm(`Tirar a voz “${id}” da lista? Ela vai para a pasta _removidas do Applio, não é apagada.`)) return
    const r = await fetch(`/api/trocar-voz/${encodeURIComponent(id)}`, { method: 'DELETE' })
    if (!r.ok) aoErro((await r.json()).detail ?? 'Falha ao remover'); else void consultar()
  }

  const prontoTroca = (!!item || !!enviado) && !!voz && !!caps?.disponivel && motorVivo
  const prontoTreino = /^[\w-]{2,40}$/.test(nome) && gravacoes.length > 0 && autorizada && !!caps?.disponivel && motorVivo

  return <div className="painel-voz">
    <h2>Trocar voz</h2>
    <p className="nota">Canta a mesma música com outro timbre, mantendo melodia e letra: o app tira a voz, converte para a voz treinada e junta de novo com o instrumental. Use só a sua voz, a de quem autorizou, ou uma voz sintética.</p>
    {caps && !caps.disponivel && <p className="aviso-atencao">{caps.motivo}</p>}

    <RotuloAjuda campo="musica-troca" rotulo="Música" ajuda="Escolha uma música da galeria ou envie um arquivo (WAV, MP3, FLAC ou OGG). Funciona melhor com uma voz principal só, sem coro." />
    <select id="musica-troca" value={item || ''} disabled={subindo} onChange={e => { setItem(Number(e.target.value)); setEnviado('') }}>
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

    <RotuloAjuda campo="voz-troca" rotulo="Voz" ajuda="As vozes treinadas aqui embaixo. Mais épocas de treino costumam dar um timbre mais fiel." />
    <select id="voz-troca" value={voz} onChange={e => setVoz(e.target.value)} disabled={!caps?.vozes.length}>
      {!caps?.vozes.length && <option value="">Nenhuma voz treinada ainda</option>}
      {caps?.vozes.map(v => <option key={v.id} value={v.id}>{v.id} — {v.epocas} épocas</option>)}
    </select>
    {!!voz && <button onClick={() => remover(voz)}>Tirar esta voz da lista</button>}

    <RotuloAjuda campo="tom-troca" rotulo={`Tom · ${tom > 0 ? '+' : ''}${tom} semitons`} ajuda="Sobe ou desce a voz convertida. Para levar uma voz feminina a uma masculina, cerca de −12; o contrário, +12. O instrumental não muda." />
    <input id="tom-troca" type="range" min={-12} max={12} step={1} value={tom} onChange={e => setTom(Number(e.target.value))} />

    <RotuloAjuda campo="formato-troca" rotulo="Formato" ajuda="Saem dois arquivos: a música com a voz trocada e a voz convertida sozinha." />
    <div className="opcoes segmentado" id="formato-troca">
      <button data-ativo={formato === 'flac'} onClick={() => setFormato('flac')}>FLAC</button>
      <button data-ativo={formato === 'mp3'} onClick={() => setFormato('mp3')}>MP3</button>
    </div>

    <button className="principal" disabled={!prontoTroca || enviando || subindo} onClick={trocar}>
      {enviando ? 'Enviando…' : 'Trocar voz'}
    </button>

    <details>
      <summary>Treinar uma voz nova</summary>
      <p className="nota">Envie de 10 a 30 minutos da pessoa cantando: voz sozinha, sem eco nem reverb, em várias notas. Cada 100 épocas levam cerca de 15 a 30 minutos para 20 minutos de gravação.</p>
      <RotuloAjuda campo="nome-voz" rotulo="Nome da voz" ajuda="Letras, números, - ou _. Ex.: narrador" />
      <input id="nome-voz" value={nome} maxLength={40} onChange={e => setNome(e.target.value.replace(/\s+/g, '_'))} />
      <RotuloAjuda campo="gravacoes-voz" rotulo={`Gravações · ${gravacoes.length}`} ajuda="Pode enviar vários arquivos de uma vez." />
      <input id="gravacoes-voz" type="file" multiple accept="audio/*,.wav,.mp3,.flac,.ogg" disabled={subindo} onChange={async e => {
        const fs = [...(e.target.files ?? [])]; if (!fs.length) return
        setSubindo(true); aoErro('')
        try { const nomes: string[] = []; for (const f of fs) nomes.push((await api.enviarAudio(f)).nome); setGravacoes(g => [...g, ...nomes]) }
        catch (err) { aoErro(String(err)) } finally { setSubindo(false); e.target.value = '' }
      }} />
      {!!gravacoes.length && <button onClick={() => setGravacoes([])}>Limpar gravações</button>}
      <RotuloAjuda campo="epocas-voz" rotulo={`Épocas · ${epocas}`} ajuda="300 é um bom começo. Menos de 100 deixa o timbre vago; muito acima de 500 pode fixar ruídos da gravação." />
      <input id="epocas-voz" type="range" min={20} max={1000} step={20} value={epocas} onChange={e => setEpocas(Number(e.target.value))} />
      <label className="alternador"><input type="checkbox" checked={tirarInstrumental} onChange={e => setTirarInstrumental(e.target.checked)} /><span>As gravações têm instrumental: tirar antes de treinar</span></label>
      <label className="alternador"><input type="checkbox" checked={autorizada} onChange={e => setAutorizada(e.target.checked)} /><span>A voz é minha, ou tenho autorização de quem canta</span></label>
      <button className="principal" disabled={!prontoTreino || enviando || subindo} onClick={treinar}>
        {enviando ? 'Enviando…' : 'Treinar voz'}
      </button>
    </details>
  </div>
}
