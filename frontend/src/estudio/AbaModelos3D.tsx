import { useEffect, useMemo, useRef, useState, createElement } from 'react'
import { api, urlImagem, type Referencia, type Tarefa } from '../api'
import { BotaoNuvem } from './motor'
import { BotaoGerar, CartaoTarefa, SlotImagem, arquivos, mensagem, teclasRadio, useCusto, useTarefas, usarNaCaixa, TituloPagina } from './comum'

// 3D: uma imagem (ou um texto) vira um modelo 3D (arquivo GLB) por um modelo de API da Comfy Cloud
// (Tripo, Hunyuan, Rodin ou Meshy; creditos). Os modelos e os ajustes de cada um vem do servidor
// (/api/modelos3d). O resultado abre num palco grande, com luz, fundo, foto e historico.

type Ajuste = { id: string; rotulo: string; tipo: 'select' | 'toggle'; padrao: string | boolean; opcoes: [string, string][]; dica: string; grupo?: string }
type ModeloCat = { id: string; rotulo: string; modos: string[]; resumo: string; pontos: string[]; ajustes: Ajuste[] }
type Valores = Record<string, string | boolean>

const PONTO_DE_PARTIDA = [
  { id: 'imagem', icone: '🖼', rotulo: 'From an image', frase: 'A picture of one object becomes a 3D model.' },
  { id: 'vistas', icone: '◫', rotulo: 'From several views', frase: 'Front, left, back and right: a more faithful shape.' },
  { id: 'texto', icone: '✍', rotulo: 'From text', frase: 'Describe the object. No image needed.' },
]

// As vistas extras (a frente e a imagem principal): o nome que o servidor espera e o rotulo na tela.
const VISTAS = [
  { id: 'esquerda', rotulo: 'Left' },
  { id: 'costas', rotulo: 'Back' },
  { id: 'direita', rotulo: 'Right' },
] as const
type Modo = 'imagem' | 'vistas' | 'texto'

// ---- historico (o que cada modelo gerado usou), guardado no navegador ----
type Meta = { modelo: string; modo: string; texto?: string; imagem?: string; vistas?: number; textura: boolean; ajustes: Valores; criado: number }
const CHAVE_META = 'm3d.meta'
function lerMeta(): Record<string, Meta> {
  try { return JSON.parse(localStorage.getItem(CHAVE_META) || '{}') } catch { return {} }
}
function gravarMeta(id: string, m: Meta) {
  try {
    const todos = { ...lerMeta(), [id]: m }
    const ids = Object.keys(todos).sort((a, b) => todos[b].criado - todos[a].criado).slice(0, 80)
    localStorage.setItem(CHAVE_META, JSON.stringify(Object.fromEntries(ids.map((i) => [i, todos[i]]))))
  } catch { /* sem armazenamento: o historico fica so sem detalhes */ }
}

/** O <model-viewer> e carregado so quando esta aba abre (e uma biblioteca grande). */
function useVisualizador3D() {
  const [pronto, setPronto] = useState(false)
  useEffect(() => { import('@google/model-viewer').then(() => setPronto(true)).catch(() => setPronto(false)) }, [])
  return pronto
}

const FUNDOS = { escuro: '#0b0d12', cinza: '#3a3d45', claro: '#e7eaf0' } as const
type Fundo = keyof typeof FUNDOS

function baixar(blob: Blob | string, nome: string) {
  const url = typeof blob === 'string' ? blob : URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = nome; document.body.appendChild(a); a.click(); a.remove()
  if (typeof blob !== 'string') setTimeout(() => URL.revokeObjectURL(url), 4000)
}

/** O palco: o modelo grande, com os controles de luz e fundo e as acoes (foto, baixar). */
function Palco({ nome, subpasta, titulo }: { nome: string; subpasta: string; titulo: string }) {
  const pronto = useVisualizador3D()
  const url = urlImagem({ nome, subpasta })
  const visor = useRef<HTMLElement | null>(null)
  const [girar, setGirar] = useState(true)
  const [fundo, setFundo] = useState<Fundo>('escuro')
  const [luz, setLuz] = useState<'neutral' | 'legacy'>('neutral')
  const [exposicao, setExposicao] = useState(1)
  const [sombra, setSombra] = useState(true)
  const [carregado, setCarregado] = useState(false)
  const [aviso, setAviso] = useState('')
  const [animacoes, setAnimacoes] = useState<string[]>([])
  const [animacao, setAnimacao] = useState('')
  useEffect(() => { setCarregado(false); setAnimacoes([]); setAnimacao('') }, [url])
  useEffect(() => {
    const v = visor.current
    if (!v) return
    const ao = () => {
      setCarregado(true)
      // Modelo com esqueleto e movimento: a lista de animacoes que vieram no arquivo.
      const lista = (v as unknown as { availableAnimations?: string[] }).availableAnimations ?? []
      setAnimacoes(lista); setAnimacao(lista[0] ?? '')
    }
    v.addEventListener('load', ao)
    return () => v.removeEventListener('load', ao)
  }, [pronto, url])

  const avisar = (t: string) => { setAviso(t); setTimeout(() => setAviso(''), 2600) }
  const foto = async (): Promise<Blob | null> => {
    const v = visor.current as unknown as { toBlob?: (o: object) => Promise<Blob> } | null
    if (!v?.toBlob) { avisar('The viewer is still loading'); return null }
    try { return await v.toBlob({ mimeType: 'image/png', idealAspect: false }) } catch { avisar('Could not take the picture'); return null }
  }
  const baixarFoto = async () => { const b = await foto(); if (b) baixar(b, nome.replace(/\.glb$/i, '') + '.png') }
  const comoReferencia = async () => {
    const b = await foto()
    if (!b) return
    const arq = new File([b], '3d-snapshot.png', { type: 'image/png' })
    location.hash = '#image'
    // A tela da Image leva um instante para abrir; o arquivo vai para o primeiro espaco de imagem vazio.
    setTimeout(() => { if (!usarNaCaixa(arq)) baixar(b, '3d-snapshot.png') }, 1100)
  }

  return (
    <div className="hf-m3d-palco-visor" data-fundo={fundo}>
      {pronto
        ? createElement('model-viewer', {
            ref: visor, src: url, 'camera-controls': true, 'auto-rotate': girar ? true : undefined, 'shadow-intensity': sombra ? '1' : '0',
            'environment-image': luz, exposure: String(exposicao), 'touch-action': 'pan-y', alt: titulo,
            autoplay: true, 'animation-name': animacao || undefined,
            style: { width: '100%', height: '100%', background: FUNDOS[fundo] } })
        : <p className="hf-dica hf-m3d-carregando">Loading the 3D viewer…</p>}
      {pronto && !carregado && <p className="hf-m3d-carregando">Opening the model… large files take a few seconds.</p>}
      <div className="hf-m3d-barra" role="toolbar" aria-label="Viewer controls">
        <button type="button" data-ativo={girar} onClick={() => setGirar((g) => !g)} title="Spin the model on its own">⟳ Spin</button>
        <button type="button" data-ativo={sombra} onClick={() => setSombra((s) => !s)} title="Shadow under the model">◐ Shadow</button>
        <span className="hf-m3d-grupo" role="group" aria-label="Background">
          {(Object.keys(FUNDOS) as Fundo[]).map((f) => (
            <button key={f} type="button" data-ativo={fundo === f} onClick={() => setFundo(f)} title={`${f} background`}
              style={{ background: FUNDOS[f] }} className="hf-m3d-amostra" aria-label={`${f} background`} />
          ))}
        </span>
        <button type="button" data-ativo={luz === 'neutral'} onClick={() => setLuz((l) => (l === 'neutral' ? 'legacy' : 'neutral'))}
          title="Soft studio light, or the basic light">☀ {luz === 'neutral' ? 'Studio' : 'Basic'} light</button>
        {animacoes.length > 0 && (
          <label className="hf-m3d-exposicao" title="Animation in the file">▶
            <select value={animacao} onChange={(e) => setAnimacao(e.target.value)} aria-label="Animation">
              {animacoes.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </label>
        )}
        <label className="hf-m3d-exposicao" title="Brightness">☼
          <input type="range" min={0.3} max={2.5} step={0.1} value={exposicao} onChange={(e) => setExposicao(Number(e.target.value))} aria-label="Brightness" />
        </label>
      </div>
      <div className="hf-m3d-acoes">
        <button type="button" onClick={baixarFoto} title="Save a picture of what you see now">📷 Picture</button>
        <button type="button" onClick={comoReferencia} title="Open the Image tab with this picture as a reference">🖼 Use in Image</button>
        <a href={url} download={nome}>⬇ Download GLB</a>
      </div>
      {aviso && <p className="hf-m3d-aviso" role="status">{aviso}</p>}
    </div>
  )
}

/** Um ajuste do modelo: lista (menu) ou chave (liga/desliga). */
function CampoAjuste({ a, valor, aoMudar }: { a: Ajuste; valor: string | boolean; aoMudar: (v: string | boolean) => void }) {
  if (a.tipo === 'toggle') {
    return (
      <label className="hf-m3d-chave" title={a.dica || undefined}>
        <input type="checkbox" checked={!!valor} onChange={(e) => aoMudar(e.target.checked)} />
        <span>{a.rotulo}</span>{a.dica && <small>{a.dica}</small>}
      </label>
    )
  }
  return (
    <label className="hf-m3d-menu" title={a.dica || undefined}>
      <span>{a.rotulo}</span>
      <select className="hf-select" value={String(valor)} onChange={(e) => aoMudar(e.target.value)} aria-label={a.rotulo}>
        {a.opcoes.map(([v, r]) => <option key={v} value={v}>{r}</option>)}
      </select>
    </label>
  )
}

export default function AbaModelos3D({ naNuvem }: { naNuvem: boolean }) {
  const tarefas = useTarefas()
  const [catalogo, setCatalogo] = useState<ModeloCat[]>([])
  const [modo, setModo] = useState<Modo>('imagem')
  const [escolha, setEscolha] = useState<Record<string, string>>({ imagem: 'tripo', vistas: 'tripo', texto: 'tripo_texto' })
  const [imagem, setImagem] = useState<Referencia | null>(null)
  const [outrasVistas, setOutrasVistas] = useState<Record<string, Referencia | null>>({})
  const [texto, setTexto] = useState('')
  const [textura, setTextura] = useState(true)
  const [ajustes, setAjustes] = useState<Record<string, Valores>>({})
  const [aberto, setAberto] = useState(false)
  const [depois, setDepois] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [selecionada, setSelecionada] = useState<string | null>(null)
  const [meta, setMeta] = useState<Record<string, Meta>>(() => lerMeta())

  useEffect(() => { fetch('/api/modelos3d').then((r) => r.json()).then(setCatalogo).catch(() => setCatalogo([])) }, [])

  const modelo = escolha[modo]
  const cfg = catalogo.find((m) => m.id === modelo)
  const doModo = catalogo.filter((m) => m.modos.includes(modo))
  const valores = (id: string): Valores => {
    const c = catalogo.find((m) => m.id === id)
    return Object.fromEntries((c?.ajustes ?? []).map((a) => [a.id, ajustes[id]?.[a.id] ?? a.padrao]))
  }
  const mudarAjuste = (id: string, chave: string, v: string | boolean) => setAjustes((x) => ({ ...x, [id]: { ...x[id], [chave]: v } }))
  const depoisAtivo = !!cfg && cfg.ajustes.some((a) => a.grupo === 'depois' && (ajustes[modelo]?.[a.id] ?? a.padrao) !== a.padrao)
  const mudouAlgum = !!cfg && cfg.ajustes.some((a) => (ajustes[modelo]?.[a.id] ?? a.padrao) !== a.padrao)

  const porTexto = modo === 'texto'
  const porVistas = modo === 'vistas'
  const vistasEnviadas = Object.fromEntries(VISTAS.filter((v) => outrasVistas[v.id]).map((v) => [v.id, outrasVistas[v.id]!.nome]))
  const pedido = { modelo: 'modelo3d', modelo_3d: modelo, textura_3d: textura, ajustes_3d: valores(modelo),
    prompt: porTexto ? texto.trim() : '', proporcao: '1:1', referencias: !porTexto && imagem ? [imagem.nome] : [],
    ...(porVistas ? { vistas_3d: vistasEnviadas } : {}) }
  const pronto = naNuvem && !!cfg && (porTexto ? !!texto.trim() : !!imagem)
  const custo = useCusto(pronto ? pedido : null)

  const gerar = async () => {
    setErro(null)
    try {
      const t = await api.gerar(pedido as Parameters<typeof api.gerar>[0])
      const m: Meta = { modelo, modo, texto: porTexto ? texto.trim() : undefined, imagem: !porTexto ? imagem?.url : undefined,
        vistas: porVistas ? 1 + Object.keys(vistasEnviadas).length : undefined, textura, ajustes: valores(modelo), criado: Date.now() }
      gravarMeta(t.id, m); setMeta(lerMeta()); setSelecionada(t.id)
    } catch (e) { setErro(mensagem(e)) }
  }

  const historico = useMemo(
    () => tarefas.filter((t) => t.modelo === 'modelo3d').sort((a, b) => b.criada_em - a.criada_em),
    [tarefas])
  const atual: Tarefa | undefined = historico.find((t) => t.id === selecionada) ?? historico[0]
  const arqs = atual?.estado === 'pronto' ? arquivos(atual) : []
  // O arquivo principal e o GLB do "salva"; o formato extra tem o formato no nome (modelo3d_fbx_...).
  const ehExtra = (n: string) => /modelo3d_(fbx|obj|stl|usdz|3mf)_/i.test(n)
  const arq = arqs.find((a) => /\.glb$/i.test(a.nome) && !ehExtra(a.nome))
  const extras = arqs.filter((a) => ehExtra(a.nome))
  const mAtual = atual ? meta[atual.id] : undefined
  const catAtual = mAtual ? catalogo.find((m) => m.id === mAtual.modelo) : undefined

  const reusar = () => {
    if (!mAtual) return
    setModo(mAtual.modo as Modo); setEscolha((e) => ({ ...e, [mAtual.modo]: mAtual.modelo }))
    setTextura(mAtual.textura); setAjustes((x) => ({ ...x, [mAtual.modelo]: mAtual.ajustes }))
    if (mAtual.texto) setTexto(mAtual.texto)
    if (mAtual.imagem && mAtual.modo !== 'texto') setImagem({ nome: mAtual.imagem.split('nome=')[1]?.split('&')[0] ?? '', url: mAtual.imagem })
  }
  const rotuloDoAjuste = (id: string, chave: string, v: string | boolean) => {
    const a = catalogo.find((m) => m.id === id)?.ajustes.find((x) => x.id === chave)
    if (!a) return null
    if (a.tipo === 'toggle') return v ? a.rotulo : null
    return `${a.rotulo}: ${a.opcoes.find(([o]) => o === String(v))?.[1] ?? v}`
  }

  return (
    <div className="hf-aba hf-img hf-vzn hf-m3d">
      <TituloPagina antes="Build in" destaque="3D" selo={cfg ? cfg.rotulo : undefined}
        sub="A picture or a sentence becomes a textured 3D model you can spin, download and use in Blender or a game engine." />

      <div className="hf-vz-modos hf-m3d-partida" role="radiogroup" aria-label="Start from" onKeyDown={teclasRadio}>
        {PONTO_DE_PARTIDA.map((p) => (
          <button key={p.id} type="button" role="radio" aria-checked={modo === p.id} tabIndex={modo === p.id ? 0 : -1} className="hf-vz-modo"
            data-ativo={modo === p.id} onClick={() => setModo(p.id as Modo)}>
            <span aria-hidden>{p.icone}</span><b>{p.rotulo}</b><small>{p.frase}</small>
          </button>
        ))}
      </div>

      <div className="hf-barra-prompt">
        <div className="hf-vz-corpo">
          <section className="hf-vz-coluna">
            <span className="hf-grupo-rotulo">{porTexto ? 'Describe it' : porVistas ? 'Your views' : 'Your image'}</span>
            {porTexto
              ? <textarea aria-label="Describe the object" className="hf-vz-caixa" rows={8} maxLength={600} value={texto} onChange={(e) => setTexto(e.target.value)}
                  placeholder="A small wooden chair with a red cushion, cartoon style" />
              : porVistas
                ? <div className="hf-m3d-vistas">
                    <SlotImagem rotulo="Front" valor={imagem} aoMudar={setImagem} />
                    {VISTAS.map((v) => <SlotImagem key={v.id} rotulo={v.rotulo} valor={outrasVistas[v.id] ?? null}
                      aoMudar={(r) => setOutrasVistas((x) => ({ ...x, [v.id]: r }))} />)}
                  </div>
                : <SlotImagem rotulo="Image" valor={imagem} aoMudar={setImagem} />}
            <p className="hf-dica">{porTexto ? 'Say what it is, the material and the style. One object works best.'
              : porVistas ? 'The front is required. Add the other sides you have: each one makes the back and sides less guessed.'
              : 'One object on a plain background works best.'}</p>
          </section>

          <section className="hf-vz-coluna">
            <span className="hf-grupo-rotulo">Model</span>
            <div className="hf-m3d-modelos" role="radiogroup" aria-label="Model" onKeyDown={teclasRadio}>
              {doModo.map((m) => (
                <button key={m.id} type="button" role="radio" aria-checked={modelo === m.id} tabIndex={modelo === m.id ? 0 : -1} className="hf-m3d-modelo"
                  data-ativo={modelo === m.id} onClick={() => setEscolha((e) => ({ ...e, [modo]: m.id }))}>
                  <b>{m.rotulo}</b>
                  <small>{m.resumo}</small>
                  <span>{m.pontos.map((p) => <i key={p}>{p}</i>)}</span>
                </button>
              ))}
              {catalogo.length === 0 && <p className="hf-dica">Loading the models…</p>}
            </div>
          </section>

          <aside className="hf-vz-coluna hf-vzn-dir" aria-label="Settings">
            <span className="hf-grupo-rotulo">Settings</span>
            <label className="hf-m3d-chave hf-m3d-chave-grande">
              <input type="checkbox" checked={textura} onChange={(e) => setTextura(e.target.checked)} />
              <span>Textures and colors</span><small>Off gives only the bare shape (grey).</small>
            </label>
            <details className="hf-m3d-avancado" open={aberto} onToggle={(e) => setAberto((e.currentTarget as HTMLDetailsElement).open)}>
              <summary>{cfg?.rotulo ?? 'Model'} settings{mudouAlgum && <em> · changed</em>}</summary>
              <div className="hf-m3d-ajustes">
                {cfg?.ajustes.filter((a) => a.grupo !== 'depois').map((a) => (
                  <CampoAjuste key={a.id} a={a} valor={ajustes[modelo]?.[a.id] ?? a.padrao} aoMudar={(v) => mudarAjuste(modelo, a.id, v)} />
                ))}
                {mudouAlgum && <button type="button" className="hf-botao-sec" onClick={() => setAjustes((x) => ({ ...x, [modelo]: {} }))}>Back to the defaults</button>}
              </div>
            </details>
            {cfg?.ajustes.some((a) => a.grupo === 'depois') && (
              <details className="hf-m3d-avancado" open={depois} onToggle={(e) => setDepois((e.currentTarget as HTMLDetailsElement).open)}>
                <summary>After building <small>(Tripo)</small>{depoisAtivo && <em> · on</em>}</summary>
                <div className="hf-m3d-ajustes">
                  {cfg.ajustes.filter((a) => a.grupo === 'depois').map((a) => (
                    <CampoAjuste key={a.id} a={a} valor={ajustes[modelo]?.[a.id] ?? a.padrao} aoMudar={(v) => mudarAjuste(modelo, a.id, v)} />
                  ))}
                  <p className="hf-dica">Each step runs in the same job and adds to the cost on the button.</p>
                </div>
              </details>
            )}
            {!naNuvem && <p className="hf-dica">The 3D models run on Comfy Cloud (credits). <BotaoNuvem /></p>}
            <BotaoGerar rotulo="Generate 3D ✦" est={custo} desligado={!pronto} aoClicar={gerar} />
            {erro && <p className="hf-erro" role="alert">{erro}</p>}
          </aside>
        </div>
      </div>

      <section className="hf-m3d-resultado" aria-label="Your 3D model">
        <span className="hf-img-titulo">Your 3D model</span>
        <div className="hf-m3d-palco">
          {arq
            ? <Palco key={atual!.id} nome={arq.nome} subpasta={arq.subpasta} titulo={catAtual?.rotulo ?? '3D model'} />
            : atual
              ? <div className="hf-m3d-vazio"><CartaoTarefa t={atual} /></div>
              : <div className="hf-m3d-vazio">
                  <b>Nothing built yet</b>
                  <p>Pick an image or write a description, choose a model and press <em>Generate 3D</em>.
                    The model opens here: spin it, change the light and the background, take a picture of it and download the GLB.</p>
                </div>}
        </div>

        {atual && (
          <div className="hf-m3d-detalhes">
            <div className="hf-m3d-fonte">
              {mAtual?.imagem && <img src={mAtual.imagem} alt="Source image" />}
              <div>
                <b>{catAtual?.rotulo ?? '3D model'}{mAtual?.modo === 'texto' ? ' · from text' : mAtual?.vistas ? ` · ${mAtual.vistas} views` : ''}</b>
                {mAtual?.texto && <p>“{mAtual.texto}”</p>}
                <small>{atual.estado === 'pronto' ? `Built in ${Math.round(atual.duracao)} s` : atual.estado === 'erro' ? 'Failed' : 'Building…'}
                  {mAtual ? ` · ${mAtual.textura ? 'textured' : 'shape only'}` : ''}</small>
              </div>
            </div>
            {mAtual && (
              <div className="hf-m3d-lista-ajustes">
                {Object.entries(mAtual.ajustes).map(([k, v]) => rotuloDoAjuste(mAtual.modelo, k, v)).filter(Boolean)
                  .map((t) => <i key={t}>{t}</i>)}
              </div>
            )}
            {extras.map((e) => <a key={e.nome} className="hf-botao-sec hf-m3d-extra" href={urlImagem({ nome: e.nome, subpasta: e.subpasta })} download={e.nome}>⬇ {(e.nome.match(/modelo3d_(\w+?)_/i)?.[1] ?? 'file').toUpperCase()}</a>)}
            {mAtual && <button type="button" className="hf-botao-sec" onClick={reusar}>Reuse these settings</button>}
          </div>
        )}

        {historico.length > 1 && (
          <div className="hf-m3d-historico" aria-label="Earlier 3D models">
            <div>
              {historico.map((t) => {
                const m = meta[t.id]
                const c = m ? catalogo.find((x) => x.id === m.modelo) : undefined
                return (
                  <button key={t.id} type="button" data-ativo={atual?.id === t.id} data-estado={t.estado} onClick={() => setSelecionada(t.id)}
                    title={m?.texto ?? undefined}>
                    {m?.imagem ? <img src={m.imagem} alt="" /> : <span aria-hidden className="hf-m3d-icone">{m?.modo === 'texto' ? '✍' : '▣'}</span>}
                    <b>{c?.rotulo ?? '3D model'}</b>
                    <small>{t.estado === 'pronto' ? new Date(t.criada_em * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : t.estado === 'erro' ? 'failed' : `${Math.round((t.progresso ?? 0) * 100)}%`}</small>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </section>
    </div>
  )
}
