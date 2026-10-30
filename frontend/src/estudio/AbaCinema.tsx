import { useEffect, useState, type ReactNode } from 'react'
import { useReusarPrompt } from './Visualizador'
import { api, type GeradorVideo, type Modelo, type ModeloNuvem, type Referencia } from '../api'
import {
  ABERTURAS, CAMERAS, ENQUADRAMENTOS, FILMES, FOCAIS, GENEROS, GRADES, LENTES, LUZES, MOVIMENTOS,
  montarPrompt, texto, visualDe, type Cor, type Direcao, type Opcao,
} from './cinema'
import { BotaoGerar, CartaoTarefa, SlotImagem, mensagem, useCusto, useTarefas, vezes, useLembrado, MAX_PROMPT , AJUSTES_VAZIOS, Avancado, camposAjustes, type Ajustes } from './comum'
import { IconeCamera } from './IconesCamera'
import { AvisoInstalar, GruposAbertos, useEscolha, useFaltaInstalar, useValor } from './motor'

// Cinema Studio, one box. The Image | Video switch changes the whole box: the
// model menu (image models or video models) and the controls at the bottom.
// Image makes stills; Video makes each shot straight from the text, with its
// camera move. The look (camera icons, picture cards for light, film, genre
// and grade) and the shot list are the same in both.

// Tested 24/10/2026 with the same scene and two opposite rigs: Z-Image Turbo and
// Krea 2 Turbo drew the character HOLDING a camera, Ideogram 4 made a poster with
// an "ARRI" logo. Only models that read the rig as the look of the shot stay.
const MODELOS_CINEMA = ['flux3', 'klein', 'kroma', 'qwen21', 'mage']

// How each model takes a reference image (same table as the Image tab). On
// Comfy Cloud the reference modes go through Qwen Image Edit.
const REF: Record<string, string> = { flux3: 'flux3ref', klein: 'trocar', kroma: 'kroma', qwen21: 'qwen21edit', mage: 'instrucao' }
const REF_NUVEM: Record<string, string> = { klein: 'trocar', mage: 'instrucao' }
// How many images each open model takes (same as the Image tab); on Comfy Cloud they go through Qwen Image Edit (3).
const MAX_REF: Record<string, number> = { flux3: 10, qwen21: 8, klein: 4, kroma: 3, mage: 3 }

const PROPORCOES_IMAGEM = ['16:9', '9:16', '1:1', '4:5', '3:2']

type Grupo = 'camera' | 'luz' | 'filme' | 'genero' | 'grade'
// duracao: segundos so deste plano (modo Video); sem ela vale o Length do rodape.
type Plano = { id: number; enquadramento: string; acao: string; movimento: string; duracao?: number; tarefa?: string }

// Bump when the card pictures change: the browser keeps a 404 for a picture
// asked for before it existed.
const VERSAO_FOTOS = 3
const foto = (grupo: string, id: string) => `/cinema/${grupo}/${id}.webp?v=${VERSAO_FOTOS}`

/** A picture card; without its picture it falls back to the colors or the name. */
function Cartao({ grupo, o, ativo, aoEscolher }: { grupo: string; o: Cor; ativo: boolean; aoEscolher: () => void }) {
  const [semFoto, setSemFoto] = useState(false)
  return (
    <button type="button" className="hf-cartao-op" data-ativo={ativo} aria-pressed={ativo} onClick={aoEscolher}>
      {semFoto && o.cores ? <span className="hf-paleta">{o.cores.map((c) => <i key={c} style={{ background: c }} />)}</span>
        : semFoto ? <span className="hf-cartao-vazio">{o.rotulo}</span>
          : <img src={foto(grupo, o.id)} alt="" loading="lazy" onError={() => setSemFoto(true)} />}
      <b>{o.rotulo}</b>
    </button>
  )
}

function Linha({ rotulo, valor, miniatura, aberto, aoAbrir }: {
  rotulo: string; valor: string; miniatura: ReactNode; aberto: boolean; aoAbrir: () => void
}) {
  return (
    <button type="button" className="hf-linha-dir" data-aberto={aberto} onClick={aoAbrir}>
      <span className="hf-linha-mini">{miniatura}</span>
      <span>{rotulo}</span><b>{valor}</b><i>{aberto ? '‹' : '›'}</i>
    </button>
  )
}

const escolherDe = (lista: string[] | undefined, quero: string) => (!lista?.length ? quero : lista.includes(quero) ? quero : lista[0])

/** One setting of the footer: a small titled dropdown. */
export function Controle({ icone, rotulo, valor, opcoes, aoMudar }: {
  icone: string; rotulo: string; valor: string; opcoes: { id: string; rotulo: string }[]; aoMudar: (v: string) => void
}) {
  return (
    <label className="hf-ctrl">
      <small>{rotulo}</small>
      <span><i aria-hidden>{icone}</i>
        <select value={valor} onChange={(e) => aoMudar(e.target.value)} aria-label={rotulo}>
          {opcoes.map((o) => <option key={o.id} value={o.id}>{o.rotulo}</option>)}
        </select>
      </span>
    </label>
  )
}

let proximoPlano = 4

export default function AbaCinema({ modelos: todos, apiModelos = [], apiGeradores = [], naNuvem = false }: {
  modelos: Modelo[]; apiModelos?: ModeloNuvem[]; apiGeradores?: GeradorVideo[]; naNuvem?: boolean
}) {
  const modelos = MODELOS_CINEMA.flatMap((id) => todos.filter((m) => m.id === id))
  const tarefas = useTarefas()
  const [tipo, setTipo] = useState<'imagem' | 'video'>(() => location.hash === '#cinema/ltx-video' ? 'video' : 'imagem')
  const video = tipo === 'video'
  const [cena, setCena] = useLembrado('cinema.cena', '')
  // "Reuse prompt" in the viewer fills this tab's text.
  useReusarPrompt(setCena)
  // Cast: people, objects and places, called @image1, @image2… in the scene.
  const [cast, setCast] = useState<Referencia[]>([])
  const [diretor, setDiretor] = useState(true)
  const [d, setD] = useState<Direcao>({ camera: 'alexa', lente: 'esferica', focal: '35', abertura: '2.8',
    luz: 'auto', filme: 'auto', genero: 'auto', grade: 'auto' })
  const [aberto, setAberto] = useState<Grupo | null>(null)
  const [enqAberto, setEnqAberto] = useState<number | null>(null)
  const [planos, setPlanos] = useState<Plano[]>([
    { id: 1, enquadramento: 'aberto', acao: '', movimento: 'dolly_in' },
    { id: 2, enquadramento: 'medio', acao: '', movimento: 'estatica' },
    { id: 3, enquadramento: 'close', acao: '', movimento: 'dolly_in' },
  ])
  const [proporcao, setProporcao] = useState('16:9')
  const [lote, setLote] = useState(1)
  const [resolucao, setResolucao] = useState('720p')
  const [duracao, setDuracao] = useState(5)
  const [audio, setAudio] = useState(true)
  const [trabalhando, setTrabalhando] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  // One seed for the whole shot list: same cast and light from shot to shot.
  // Sorteada uma vez, ao montar (useState com funcao: fora do desenho, como o React pede).
  const [seedSorteada] = useState(() => Math.floor(Math.random() * 2 ** 31))
  // "Advanced" (so modelos locais): a seed digitada vale para a lista toda.
  const [ajustes, setAjustes] = useState<Ajustes>(AJUSTES_VAZIOS)

  // ---- image model: never default to one that cannot run where we are
  const roda = (m: Modelo) => !(naNuvem && m.nuvem === false)
  const [modelo, setModelo] = useState(() => (modelos.find(roda) ?? modelos[0])?.id ?? 'flux3')
  useEffect(() => {
    const m = modelos.find((x) => x.id === modelo)
    if (m && !roda(m)) { const outro = modelos.find(roda); if (outro) setModelo(outro.id) }
  }, [naNuvem, todos])
  const escolherImg = useEscolha(setModelo)
  const apiAtual = apiModelos.find((m) => m.id === modelo)
  const valorImg = useValor(modelo, !!apiAtual)
  const modoRef = apiAtual ? modelo : naNuvem ? (REF_NUVEM[modelo] ?? 'qwen') : REF[modelo]
  const extraApi = apiAtual ? { resolucao_nuvem: (apiAtual.resolucoes ?? apiAtual.niveis ?? ['1K'])[0] } : {}

  // ---- video model: open LTX / MiniMax (your GPU or Comfy Cloud) or an API generator that writes from text
  const geradores = apiGeradores.filter((g) => g.modos.includes('texto') || g.modos.includes('referencia'))
  const [motorVideo, setMotorVideo] = useState('ltx')
  const escolherVid = useEscolha(setMotorVideo)
  const gApi = geradores.find((g) => g.id === motorVideo)
  const valorVid = useValor(motorVideo, !!gApi)
  const faltaInstalar = useFaltaInstalar()
  // Rotulo do modelo escolhido que falta instalar neste computador ('' se nada falta).
  const naoInstalado = video
    ? (faltaInstalar(motorVideo, !!gApi) ? (motorVideo === 'ltx' ? 'LTX 2.5' : 'MiniMax H3') : '')
    : (faltaInstalar(modelo, !!apiAtual) ? (modelos.find((m) => m.id === modelo)?.rotulo ?? modelo) : '')
  const proporcoesVideo = gApi ? (gApi.proporcoes ?? ['16:9']).filter((x) => x !== 'adaptive') : ['16:9', '9:16', '1:1']
  const resolucoesVideo = gApi ? (gApi.resolucoes ?? ['720p']) : motorVideo === 'minimax' ? ['480p', '720p'] : ['480p', '720p', '1080p']
  // Every whole second the model takes (the open LTX goes to 15 s, as in the Video tab).
  const dMin = gApi?.duracao_min ?? 2, dMax = gApi?.duracao_max ?? (motorVideo === 'ltx' ? 15 : 10)
  const duracoes = Array.from({ length: dMax - dMin + 1 }, (_, i) => dMin + i)
  // The cast goes in only where the video model takes reference images.
  const maxVideo = gApi ? (gApi.modos.includes('referencia') ? (gApi.max_referencias ?? 1) : 0) : motorVideo === 'ltx' && !naNuvem ? 4 : 0
  const maxImagem = apiAtual ? (apiAtual.max_referencias ?? 0) : naNuvem ? 3 : (MAX_REF[modelo] ?? 1)
  const maxCast = video ? maxVideo : maxImagem
  const castOk = cast.slice(0, maxCast)
  const refVideo = video && castOk.length > 0
  const local = video ? !gApi : !apiAtual
  const seed = local && ajustes.seed ? Number(ajustes.seed) : seedSorteada
  const duracaoDe = (p: Plano) => Math.max(dMin, Math.min(dMax, p.duracao ?? duracao))
  const pedidoVideo = {
    modelo: 'video', modelo_video: motorVideo, modo_video: refVideo ? 'referencia' : 'texto', proporcao: '1:1',
    proporcao_video: escolherDe(proporcoesVideo, proporcao), resolucao_video: escolherDe(resolucoesVideo, resolucao),
    duracao_video: Math.max(dMin, Math.min(dMax, duracao)), com_audio: audio,
    referencias: refVideo ? castOk.map((r) => r.nome) : [],
    ...(gApi ? {} : { ...camposAjustes(ajustes, false), seed }),
  }
  const pedidoImagem = {
    modelo: castOk.length ? modoRef : modelo, proporcao: escolherDe(PROPORCOES_IMAGEM, proporcao), lote,
    referencias: castOk.map((r) => r.nome), seed, ...extraApi,
    ...(apiAtual ? {} : { ...camposAjustes(ajustes, true), seed }),
  }

  const custo = useCusto(video ? { ...pedidoVideo, prompt: 'x' } : { ...pedidoImagem, prompt: 'x' })
  // Um pedido por plano (gerarTodos): o botao mostra o total. Antes so o usd (GPU)
  // era multiplicado, e um modelo de API (faixa min/max) mostrava o preco de 1.
  const custoTotal = vezes(custo, planos.length)

  const mudar = (campo: keyof Direcao) => (v: string) => setD((a) => ({ ...a, [campo]: v }))
  const mudarPlano = (id: number, c: Partial<Plano>) => setPlanos((a) => a.map((p) => (p.id === id ? { ...p, ...c } : p)))
  const tarefa = (id?: string) => tarefas.find((t) => t.id === id)

  /** Director mode asks the local language model; if it fails, the plain prompt goes. */
  const promptDo = async (p: Plano) => {
    const cenaPlano = [cena.trim(), p.acao.trim()].filter(Boolean).join('. ')
    let base: string
    if (!diretor) base = montarPrompt(cenaPlano, d, p.enquadramento)
    else {
      try {
        base = (await api.cinemaDiretor(cenaPlano, texto(ENQUADRAMENTOS, p.enquadramento), visualDe(d), seed)).prompt
      } catch { base = montarPrompt(cenaPlano, d, p.enquadramento) }
    }
    return video ? `${base} ${texto(MOVIMENTOS, p.movimento)}` : base
  }

  const gerarPlano = async (p: Plano) => {
    const prompt = await promptDo(p)
    // With one image and no @ in the text, say who it is; with several, the scene names them (@image1, @image2…).
    const comCast = castOk.length === 1 && !cena.includes('@') ? `The same subject from @image1. ${prompt}` : prompt
    const pedido = video ? { ...pedidoVideo, duracao_video: duracaoDe(p) } : pedidoImagem
    const t = await api.gerar({ ...pedido, prompt: comCast } as Parameters<typeof api.gerar>[0])
    mudarPlano(p.id, { tarefa: t.id })
  }

  const gerarTodos = async () => {
    setErro(null)
    try {
      for (const [i, p] of planos.entries()) {
        setTrabalhando(diretor ? `Directing shot ${i + 1}…` : `Sending shot ${i + 1}…`)
        await gerarPlano(p)
      }
    } catch (e) { setErro(mensagem(e)) } finally { setTrabalhando('') }
  }

  const rot = (l: Opcao[], id: string) => l.find((o) => o.id === id)?.rotulo ?? ''
  const camResumo = [rot(CAMERAS, d.camera), rot(LENTES, d.lente), rot(FOCAIS, d.focal), rot(ABERTURAS, d.abertura)].join(' · ')
  const painel: Record<Exclude<Grupo, 'camera'>, { rotulo: string; lista: Cor[]; campo: keyof Direcao }> = {
    luz: { rotulo: 'Light', lista: LUZES, campo: 'luz' }, filme: { rotulo: 'Film', lista: FILMES, campo: 'filme' },
    genero: { rotulo: 'Look', lista: GENEROS, campo: 'genero' }, grade: { rotulo: 'Grade', lista: GRADES, campo: 'grade' },
  }
  const abrir = (g: Grupo) => setAberto((a) => (a === g ? null : g))
  const mini = (g: string, id: string) => <img src={foto(g, id)} alt="" onError={(e) => { e.currentTarget.style.visibility = 'hidden' }} />
  const proporcoes = video ? proporcoesVideo : PROPORCOES_IMAGEM

  return (
    <div className="hf-aba">
      <div className="hf-heroi hf-heroi-compacto">
        <span className="hf-sobretitulo">CINEMA STUDIO</span>
        <h1>Direct your scene, <em>shot by shot</em></h1>
      </div>

      {/* Como usar, recolhido (mesmo estilo das dicas do 3D render -> Video). */}
      <details className="hf-experimental hf-dicas hf-dicas-cinema">
        <summary><b>How it works</b> · Tips for better shots</summary>
        <ul>
          <li><b>1. Write the scene</b>: who, where and what is happening, in a sentence or two. Any language works with Director mode on.</li>
          <li><b>2. Add your cast</b> (optional): pictures of people, objects or places. Call them <b>@image1</b>, <b>@image2</b>… in the scene, so every shot keeps the same faces and things.</li>
          <li><b>3. Set the look</b>: camera, light, film, look and grade. <b>Director mode</b> turns these choices into how the frame looks, without drawing any camera gear.</li>
          <li><b>4. Plan the shots</b>: pick the framing of each shot (wide, medium, close-up…) and, if you want, what happens in it. Then <b>Shoot this one</b>, or <b>Shoot all</b> at the bottom.</li>
          <li><b>Reshoot</b> any shot until it looks right; with <b>Takes per shot</b> above 1 you get several versions to pick from.</li>
        </ul>
        <b className="hf-dicas-sub">Image or Video</b>
        <ul>
          <li><b>Image</b> makes a still for each shot. <b>Video</b> makes a clip for each shot, from the text, with its own camera move and length.</li>
          <li>In Video, the cast pictures are <b>references</b> (LTX 2.5 on your GPU takes up to 4): they are not animated as the first frame.</li>
          <li><b>To animate a still you like</b>: shoot it in Image mode, then click <b>▶ Animate</b> on the result. It opens the Video tab in Image → Video with that picture.</li>
          <li>The small picture in each shot is just an example of the framing; it is replaced by your result.</li>
        </ul>
      </details>

      <div className="hf-barra-prompt hf-cinema">
        <div className="hf-linha-controles hf-cinema-topo">
          <div className="hf-tipo" role="tablist">
            <button role="tab" data-ativo={!video} aria-selected={!video} onClick={() => setTipo('imagem')}>Image</button>
            <button role="tab" data-ativo={video} aria-selected={video} onClick={() => setTipo('video')}>Video</button>
          </div>
          <label className="hf-chave-dir" title="A local language model rewrites the scene as one film frame, turning the gear into how the image looks">
            <input type="checkbox" checked={diretor} onChange={(e) => setDiretor(e.target.checked)} /> Director mode
          </label>
        </div>

        <textarea aria-label="Scene description" maxLength={MAX_PROMPT} className="hf-cinema-texto" value={cena} onChange={(e) => setCena(e.target.value)} rows={3}
          placeholder={castOk.length > 1 ? 'e.g. @image1 and @image2 argue in a rain-soaked neon alley at night…'
            : 'Who, where, what is happening: a detective in a rain-soaked neon alley at night…'} />
        {maxCast > 0 ? (
          <div className="hf-cast">
            {castOk.map((r, i) => (
              <SlotImagem key={r.nome + i} rotulo={`@image${i + 1}`} valor={r}
                aoMudar={(n) => setCast((a) => (n ? a.map((x, j) => (j === i ? n : x)) : a.filter((_, j) => j !== i)))} />
            ))}
            {castOk.length < maxCast && (
              <SlotImagem key={`novo${castOk.length}`} rotulo={castOk.length ? `@image${castOk.length + 1}` : 'Cast'} valor={null}
                aoMudar={(n) => n && setCast((a) => [...a.slice(0, maxCast), n])} />
            )}
            <p className="hf-dica">Cast: up to {maxCast} {maxCast === 1 ? 'image' : 'images'} with this model (people, objects, places).{castOk.length > 1 && ' Name them in the scene as @image1, @image2…'}</p>
          </div>
        ) : (
          <p className="hf-dica">{video ? 'This video model makes each shot from the text only; it takes no cast images. Seedance, Kling or LTX on your GPU do.' : 'This model takes no cast images.'}</p>
        )}
        {cast.length > castOk.length && <p className="hf-dica">{cast.length - castOk.length} cast image(s) are kept but not sent: this model takes {maxCast}.</p>}

        <div className="hf-direcao">
          <Linha rotulo="Camera" miniatura={<IconeCamera grupo="camera" id={d.camera} />} valor={camResumo}
            aberto={aberto === 'camera'} aoAbrir={() => abrir('camera')} />
          {aberto === 'camera' && (
            <div className="hf-painel-op hf-painel-camera">
              {([['Body', CAMERAS, 'camera'], ['Lens', LENTES, 'lente'], ['Focal length', FOCAIS, 'focal'], ['Aperture', ABERTURAS, 'abertura']] as const).map(([r, l, c]) => (
                <div key={c}>
                  <span className="hf-grupo-rotulo">{r}</span>
                  {l.map((o) => (
                    <button key={o.id} type="button" className="hf-cartao-op hf-cartao-icone" data-ativo={d[c] === o.id} aria-pressed={d[c] === o.id}
                      onClick={() => mudar(c)(o.id)} title={o.texto}>
                      <IconeCamera grupo={c} id={o.id} /><b>{o.rotulo}</b>
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
          {(['luz', 'filme', 'genero', 'grade'] as const).map((g) => (
            <div key={g}>
              <Linha rotulo={painel[g].rotulo} miniatura={mini(g, d[painel[g].campo])}
                valor={rot(painel[g].lista, d[painel[g].campo])} aberto={aberto === g} aoAbrir={() => abrir(g)} />
              {aberto === g && (
                <div className="hf-painel-op">
                  {painel[g].lista.map((o) => <Cartao key={o.id} grupo={g} o={o} ativo={d[painel[g].campo] === o.id}
                    aoEscolher={() => { mudar(painel[g].campo)(o.id); setAberto(null) }} />)}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Segunda caixa: o modelo e a lista de planos, com o rodape de geracao (30/10/2026). */}
      <div className="hf-barra-prompt hf-cinema hf-cinema-planos">
        <span className="hf-passo">Shot list</span>
        <p className="hf-dica">Every shot keeps the same cast, light and color.{video && ' Each shot is a clip with its own camera move.'}</p>
        <div className="hf-cinema-modelo">
            {video ? (
              <label className="hf-campo"><span>Model</span><select className="hf-select" value={valorVid} onChange={(e) => escolherVid(e.target.value)} aria-label="Video model">
                <GruposAbertos itens={[{ id: 'ltx', rotulo: 'LTX 2.5' }, { id: 'minimax', rotulo: 'MiniMax H3' }]} api={geradores} />
              </select></label>
            ) : (
              <label className="hf-campo"><span>Model</span><select className="hf-select" value={valorImg} onChange={(e) => escolherImg(e.target.value)} aria-label="Image model">
                <GruposAbertos itens={modelos.map((m) => ({ id: m.id, rotulo: m.rotulo, nuvem: m.nuvem }))} api={apiModelos} />
              </select></label>
            )}
        </div>
        {planos.map((p, i) => {
          const t = tarefa(p.tarefa)
          return (
            <div key={p.id} className="hf-plano">
              <div className="hf-plano-quadro">
                {t ? <CartaoTarefa t={t} /> : <img src={foto('enquadramento', p.enquadramento)} alt={`Shot ${i + 1}: ${rot(ENQUADRAMENTOS, p.enquadramento)}`} />}
              </div>
              <div className="hf-plano-campos">
                <div className="hf-linha-controles">
                  <b>Shot {i + 1}</b>
                  <button type="button" className="hf-enq" data-aberto={enqAberto === p.id}
                    onClick={() => setEnqAberto((a) => (a === p.id ? null : p.id))}>
                    <img src={foto('enquadramento', p.enquadramento)} alt="" />
                    <span>{rot(ENQUADRAMENTOS, p.enquadramento)}</span><i>▾</i>
                  </button>
                  {planos.length > 1 && <button type="button" className="hf-botao-sec hf-x" aria-label={`Remove shot ${i + 1}`} title={`Remove shot ${i + 1}`}
                    onClick={() => setPlanos((a) => a.filter((x) => x.id !== p.id))}>×</button>}
                </div>
                {enqAberto === p.id && (
                  <div className="hf-painel-op hf-painel-enq">
                    {ENQUADRAMENTOS.map((o) => <Cartao key={o.id} grupo="enquadramento" o={o} ativo={p.enquadramento === o.id}
                      aoEscolher={() => { mudarPlano(p.id, { enquadramento: o.id }); setEnqAberto(null) }} />)}
                  </div>
                )}
                {video && (
                  <div className="hf-plano-video">
                    <label className="hf-campo-linha"><span>Camera move</span>
                      <select className="hf-select" value={p.movimento} onChange={(e) => mudarPlano(p.id, { movimento: e.target.value })} aria-label={`Camera move, shot ${i + 1}`}>
                        {MOVIMENTOS.map((o) => <option key={o.id} value={o.id}>{o.rotulo}</option>)}
                      </select></label>
                    <label className="hf-campo-linha"><span>Length</span>
                      <select className="hf-select" value={duracaoDe(p)} onChange={(e) => mudarPlano(p.id, { duracao: Number(e.target.value) })} aria-label={`Length, shot ${i + 1}`}>
                        {Array.from({ length: dMax - dMin + 1 }, (_, k) => dMin + k).map((n) => <option key={n} value={n}>{n} s</option>)}
                      </select></label>
                  </div>
                )}
                {/* A acao do plano e o botao na mesma linha: o botao fica a direita da caixa. */}
                <div className="hf-plano-acao">
                  <input className="hf-campo" value={p.acao} onChange={(e) => mudarPlano(p.id, { acao: e.target.value })}
                    placeholder="What happens in this shot (optional): he lights a cigarette…" />
                  <button type="button" className="hf-gerar hf-shoot-plano" disabled={!cena.trim() || !!trabalhando || !!naoInstalado}
                    onClick={async () => { setErro(null); try { await gerarPlano(p) } catch (e) { setErro(mensagem(e)) } }}>
                    {t ? '↻ Reshoot' : '✦ Shoot this one'}
                  </button>
                </div>
              </div>
            </div>
          )
        })}
        {/* Teto de 8 planos: o botao da lugar a uma nota (antes sumia sem dizer por que). */}
        {planos.length < 8 ? (
          <button type="button" className="hf-botao-sec hf-mais-plano"
            onClick={() => setPlanos((a) => [...a, { id: proximoPlano++, enquadramento: 'medio', acao: '', movimento: 'estatica' }])}>+ Add shot</button>
        ) : <p className="hf-dica">Up to 8 shots per scene. Remove one to add another.</p>}

        <div className="hf-cinema-rodape">
          <Controle icone="▭" rotulo="Aspect" valor={escolherDe(proporcoes, proporcao)} aoMudar={setProporcao}
            opcoes={proporcoes.map((x) => ({ id: x, rotulo: x }))} />
          {video ? <>
            <Controle icone="⛶" rotulo="Resolution" valor={escolherDe(resolucoesVideo, resolucao)} aoMudar={setResolucao}
              opcoes={resolucoesVideo.map((x) => ({ id: x, rotulo: x }))} />
            <Controle icone="◷" rotulo="Length" valor={String(Math.max(dMin, Math.min(dMax, duracao)))} aoMudar={(v) => setDuracao(Number(v))}
              opcoes={duracoes.map((x) => ({ id: String(x), rotulo: `${x} s` }))} />
            {(gApi as { sem_audio?: boolean } | undefined)?.sem_audio ? (
              <span className="hf-ctrl hf-ctrl-fixo" title="This model makes silent video"><small>Sound</small><b>🔇 None</b></span>
            ) : (
              <button type="button" className="hf-ctrl hf-ctrl-som" data-ativo={audio} aria-pressed={audio} onClick={() => setAudio((a) => !a)}
                title="Generate sound with the video (ambience, effects, speech)">
                <small>Sound</small><b>{audio ? '🔊 On' : '🔇 Off'}</b>
              </button>
            )}
          </> : (
            <Controle icone="▦" rotulo="Takes per shot" valor={String(lote)} aoMudar={(v) => setLote(Number(v))}
              opcoes={[1, 2, 4].map((n) => ({ id: String(n), rotulo: `${n}` }))} />
          )}
          <BotaoGerar rotulo={trabalhando || `Shoot ${planos.length} ${video ? 'clip' : 'still'}${planos.length === 1 ? '' : 's'} ✦`}
            est={custoTotal} desligado={!!naoInstalado || !cena.trim() || !!trabalhando} aoClicar={gerarTodos} />
        </div>
        {local && <Avancado valor={ajustes} aoMudar={setAjustes} comPassos={!video}
          nota="Applies to every shot in the list, so light and cast stay the same." />}
        {naoInstalado && <AvisoInstalar rotulo={naoInstalado} />}
        {erro && <p className="hf-erro">{erro}</p>}
      </div>
    </div>
  )
}
