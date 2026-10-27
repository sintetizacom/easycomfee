import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  api, ouvirTarefas, referenciaDaGaleria, urlEntrada, urlImagem, urlMiniatura,
  type Caption, type Elemento, type ItemGaleria, type Modelo,
  type ModeloNuvem, type ModeloVideo, type ModoEdicao,
  type Zonas,
  type Referencia, type Tarefa,
} from './api'
import EditorCaixas from './EditorCaixas'
import PainelEdicao from './PainelEdicao'
import PainelInfo, { type Acao } from './PainelInfo'
import Palco from './Palco'
import Ajuda from './Ajuda'
import TelaModelos from './TelaModelos'
import SeletorMotor from './SeletorMotor'
import PainelVideo from './PainelVideo'
import PainelVoz from './PainelVoz'
import PainelMusica from './PainelMusica'
import PainelAvatar from './PainelAvatar'
import PainelSeparar from './PainelSeparar'
import PainelTrocarVoz from './PainelTrocarVoz'
import PainelAndamento from './PainelAndamento'
import Seletor from './Seletor'
import GaleriaCentral, { type LayoutGaleria } from './GaleriaCentral'
import { FILTROS_GALERIA, type FiltroGaleria } from './filtrosGaleria'

const TINTAS = [
  { nome: 'Branco quente', cor: '#F2EBDC' },
  { nome: 'Branco puro', cor: '#FFFFFF' },
  { nome: 'Preto', cor: '#111111' },
  { nome: 'Areia', cor: '#C8A87C' },
  { nome: 'Vermelho', cor: '#C8342B' },
]

type Vista = { nome: string; subpasta: string }

function tipoDoItem(item: ItemGaleria): Exclude<FiltroGaleria, 'tudo'> {
  if (item.modelo === 'voz') return 'voz'
  if (item.modelo === 'musica') return 'musica'
  return item.duracao_video ? 'video' : 'imagem'
}

const EM_ANDAMENTO = ['na_fila', 'preparando', 'submetendo', 'executando']

export default function App() {
  // Dois niveis. O de cima e o MEIO — imagem ou video —, porque e a
  // primeira decisao de quem chega: o que voce vai fazer. Gerar e editar
  // sao tarefas DENTRO de imagem, no mesmo padrao de Criar/Ampliar no
  // video. Antes os tres ficavam lado a lado, misturando meio com tarefa.
  const [meio, setMeio] = useState<'imagem' | 'video' | 'voz' | 'musica' | 'avatar'>(() =>
    location.hash.startsWith('#advanced/ltx-') ? 'video' : 'imagem')
  const [reusoMusica, setReusoMusica] = useState<ItemGaleria | null>(null)
  const [reusoVideo, setReusoVideo] = useState<{ item: ItemGaleria; versao: number } | null>(null)
  const [reusoVoz, setReusoVoz] = useState<ItemGaleria | null>(null)
  const [aba, setAba] = useState<'gerar' | 'editar'>('gerar')
  const [abaMusica, setAbaMusica] = useState<'gerar' | 'separar' | 'trocar'>('gerar')
  const [cfgVideo, setCfgVideo] = useState<ModeloVideo | undefined>()
  const [cfgTransformarVideo, setCfgTransformarVideo] = useState<{
        id: string
        segundos_por_segundo: number
        max_segundos: number
        efeitos: { id: string; rotulo: string; nota: string; imagem_estilo?: boolean; quadros_chave?: boolean; max_segundos?: number; rotulo_imagem?: string | null; controles?: { id: string; rotulo: string }[]; imagem_opcional?: boolean; mapa_pronto?: boolean }[]
      } | null>(null)
  const [cfgAmpliarVideo, setCfgAmpliarVideo] = useState<
    | {
        metodos: { id: string; rotulo: string; nota: string; segundos: number }[]
        maior_lado: number
        alinhamento_temporal?: number
        alinhamento_espacial?: number
      }
    | undefined
  >()
  const [modelos, setModelos] = useState<Modelo[]>([])
  const [nuvem, setNuvem] = useState<ModeloNuvem[]>([])
  const [nuvemPronta, setNuvemPronta] = useState(true)
  const [resolucaoNuvem, setResolucaoNuvem] = useState('1K')
  const [qualidadeNuvem, setQualidadeNuvem] = useState('medium')
  const [fundoNuvem, setFundoNuvem] = useState('auto')
  const [mostrarModelos, setMostrarModelos] = useState(false)
  // Muda quando o motor troca (local/nuvem): o catalogo e relido, porque na
  // nuvem cada modelo vem marcado com o que roda la.
  const [versaoMotor, setVersaoMotor] = useState(0)
  const [saldo, setSaldo] = useState<{
    ok: boolean
    usd?: number
    motivo?: string
    gasto?: { imagens: number; usd: number }
  } | null>(null)
  const [gruposEdicao, setGruposEdicao] = useState<{ id: string; rotulo: string }[]>([])
  const [modosEdicao, setModosEdicao] = useState<ModoEdicao[]>([])
  const [niveisPele, setNiveisPele] = useState<{ id: string; rotulo: string }[]>([])
  const [tiposImagem, setTiposImagem] =
    useState<{ id: string; rotulo: string; nota: string }[]>([])
  const [proporcoes, setProporcoes] = useState<string[]>([])
  const [motorVivo, setMotorVivo] = useState(false)
  // Qual família de modelo está na GPU. Só cabe uma; trocar custa carregar
  // do disco, e é isso que fazia a estimativa errar por minutos.
  const [motorCarregado, setMotorCarregado] = useState<string | null>(null)
  const [liberando, setLiberando] = useState(false)
  const [avisoMemoria, setAvisoMemoria] = useState('')
  // Parâmetros a repor no painel de edição quando se reusa uma imagem dele.
  const [reuso, setReuso] = useState<Record<string, unknown> | null>(null)

  const [modelo, setModelo] = useState('krea')
  // Ate 3 personagens (Krea/Kroma): o backend encadeia uma passada por personagem.
  const [refsPersonagem, setRefsPersonagem] = useState<Referencia[]>([])
  const [posicoesPersonagem, setPosicoesPersonagem] = useState<string[]>([])
  const [forcaReferencia, setForcaReferencia] = useState(1)
  const [enviandoPersonagem, setEnviandoPersonagem] = useState(false)
  const entradaPersonagem = useRef<HTMLInputElement>(null)
  const [prompt, setPrompt] = useState('')
  const [negativo, setNegativo] = useState('')
  const [proporcao, setProporcao] = useState('1:1')
  const [escala, setEscala] = useState(1)
  const [nativo4k, setNativo4k] = useState(false)
  const [lote, setLote] = useState(1)
  const [seed, setSeed] = useState('')
  const [steps, setSteps] = useState('')
  const [cfg, setCfg] = useState('')
  const [qualidade, setQualidade] = useState('padrao')
  // Desmarcada por padrão. Em cinco prompts medidos no Krea, a expansão Fiel
  // acrescentou luz e material mas perdeu composição, e o resultado sem
  // expansão foi igual ou melhor nos três casos comparados lado a lado. Quem
  // escreve um prompt específico é melhor servido sem ela; quem quer clima de
  // gênero liga e escolhe Livre.
  const [expandir, setExpandir] = useState(false)
  // "fiel" é o padrão porque, nos testes, a expansão livre mexeu em algo que o
  // usuário não pediu em três de quatro casos — enquadramento, gênero do
  // sujeito e qual elemento domina o quadro.
  const [modoExpansao, setModoExpansao] = useState('fiel')
  const [modosExpansao, setModosExpansao] =
    useState<{ id: string; rotulo: string; nota: string }[]>([])
  const [estilo, setEstilo] = useState('livre')
  const [estiloManual, setEstiloManual] = useState('')
  const [estilos, setEstilos] = useState<{ id: string; rotulo: string; nota: string }[]>([])

  // Layout do Ideogram 4.
  const [usarCaixas, setUsarCaixas] = useState(false)
  const [descricao, setDescricao] = useState('')
  const [fundo, setFundo] = useState('')
  const [elementos, setElementos] = useState<Elemento[]>([])
  const [pensando, setPensando] = useState(false)

  const [tarefas, setTarefas] = useState<Tarefa[]>([])
  const [galeria, setGaleria] = useState<ItemGaleria[]>([])
  // As comparações de teste ficam guardadas, mas fora da vista por padrão.
  const [mostrarTestes, setMostrarTestes] = useState(false)
  const [quantosTestes, setQuantosTestes] = useState(0)
  const [vista, setVista] = useState<Vista | null>(null)
  const [mostrarInfo, setMostrarInfo] = useState(true)
  const [modoCentral, setModoCentral] = useState<'palco' | 'galeria'>(() => {
    try {
      return localStorage.getItem('modoCentral') === 'galeria' ? 'galeria' : 'palco'
    } catch {
      return 'palco'
    }
  })
  const [layoutGaleria, setLayoutGaleria] = useState<LayoutGaleria>(() => {
    try {
      return localStorage.getItem('layoutGaleria') === 'lista' ? 'lista' : 'grade'
    } catch {
      return 'grade'
    }
  })
  const [itemModal, setItemModal] = useState<ItemGaleria | null>(null)
  // A escolha de recolher a galeria é uma conveniência de quem está na frente
  // da tela, então mora no navegador e não no banco.
  const [galeriaAberta, setGaleriaAberta] = useState(() => {
    try {
      return localStorage.getItem('galeriaAberta') !== 'nao'
    } catch {
      return true
    }
  })
  const [filtroGaleria, setFiltroGaleria] = useState<FiltroGaleria>(() => {
    try {
      const salvo = localStorage.getItem('filtroGaleria')
      return FILTROS_GALERIA.some(({ id }) => id === salvo)
        ? salvo as FiltroGaleria
        : 'tudo'
    } catch {
      return 'tudo'
    }
  })

  const alternarGaleria = () => {
    setGaleriaAberta((v) => {
      try {
        localStorage.setItem('galeriaAberta', v ? 'nao' : 'sim')
      } catch {
        // Janela privada ou armazenamento bloqueado: segue sem lembrar.
      }
      return !v
    })
  }

  const mudarFiltroGaleria = (filtro: FiltroGaleria) => {
    setFiltroGaleria(filtro)
    try {
      localStorage.setItem('filtroGaleria', filtro)
    } catch {
      // Janela privada ou armazenamento bloqueado: segue sem lembrar.
    }
  }

  const mudarModoCentral = (modo: 'palco' | 'galeria') => {
    setModoCentral(modo)
    try { localStorage.setItem('modoCentral', modo) } catch { /* segue sem lembrar */ }
  }

  const mudarLayoutGaleria = (layout: LayoutGaleria) => {
    setLayoutGaleria(layout)
    try { localStorage.setItem('layoutGaleria', layout) } catch { /* segue sem lembrar */ }
  }
  // Estado do formulário de edição, aqui em cima para que as ações rápidas do
  // painel de informações possam preenchê-lo.
  const [modoEdicao, setModoEdicao] = useState('trocar')
  const [referenciasEdicao, setReferenciasEdicao] = useState<Referencia[]>([])
  const [erro, setErro] = useState('')
  const [aviso, setAviso] = useState('')

  // Fundo do Ideogram: a foto nao passa pelo modelo. A peca sai branca
  // sobre preto e so as letras sao compostas sobre ela.
  const [fundoIdeogram, setFundoIdeogram] = useState<Referencia | null>(null)
  // Referencias do modo nuvem. Lista, e nao uma so: o no aceita ate 14,
  // e e isso que permite manter personagem entre pecas.
  const [refsNuvem, setRefsNuvem] = useState<Referencia[]>([])
  const [enviandoRefNuvem, setEnviandoRefNuvem] = useState(false)
  const entradaRefNuvem = useRef<HTMLInputElement>(null)
  const [tinta, setTinta] = useState('#F2EBDC')
  const [enviandoFundo, setEnviandoFundo] = useState(false)
  const [zonas, setZonas] = useState<Zonas | null>(null)
  const entradaFundo = useRef<HTMLInputElement>(null)

  const ehIdeogram = modelo === 'ideogram'
  const modeloAtual = modelos.find((m) => m.id === modelo)
  const comPersonagem = !!modeloAtual?.referencia_personagem && refsPersonagem.length > 0
  const usarPersonagem = (ref: Referencia | null) => { setRefsPersonagem(ref ? [ref] : []); setPosicoesPersonagem([]) }
  const enviarPersonagem = async (arquivo?: File) => {
    if (!arquivo || enviandoPersonagem) return
    setEnviandoPersonagem(true)
    try {
      const ref = await api.enviarReferencia(arquivo)
      setRefsPersonagem((rs) => [...rs, ref].slice(0, 3))
    } catch (e) { setErro(String(e)) }
    finally { setEnviandoPersonagem(false) }
  }
  // Modelo por nuvem escolhido, se for o caso. Governa tudo que so vale
  // para eles: resolucao propria, custo na tela e ausencia de steps/cfg.
  const nuvemAtual = nuvem.find((m) => m.id === modelo)
  const orientacaoNuvem = (() => {
    const [l, a] = proporcao.split(':').map(Number)
    return l === a ? 'quadrado' : l > a ? 'paisagem' : 'retrato'
  })()
  const tamanhoNuvemEfetivo = nuvemAtual?.familia === 'openai'
    ? nuvemAtual.tamanhos_por_nivel?.[resolucaoNuvem]?.[orientacaoNuvem]
    : resolucaoNuvem
  // As duas familias indexam o preco de formas diferentes. Uma funcao so,
  // para o numero no botao e o do bloco nunca divergirem.
  const precoNuvem = (m: ModeloNuvem | undefined, tam: string, qual: string) => {
    if (!m) return 0
    const tabela = m.preco_usd
    if (m.familia === 'openai') {
      const porTamanho = tabela[qual] as Record<string, number> | undefined
      return porTamanho?.[tam] ?? 0
    }
    return (tabela[tam] as number) ?? 0
  }
  const custoDaPeca = precoNuvem(
    nuvemAtual, tamanhoNuvemEfetivo ?? resolucaoNuvem, qualidadeNuvem,
  )

  // Trocar de familia invalida a escolha anterior. Ambas agora mostram
  // 1K/2K/4K, mas a validacao continua sendo do catalogo vivo do backend.
  useEffect(() => {
    if (!nuvemAtual) return
    const validos = nuvemAtual.niveis ?? nuvemAtual.resolucoes ?? []
    if (validos.length && !validos.includes(resolucaoNuvem)) {
      setResolucaoNuvem(validos[0])
    }
  }, [nuvemAtual, resolucaoNuvem])

  const enviarFundo = async (arquivos: FileList | File[]) => {
    const f = Array.from(arquivos).find((a) => a.type.startsWith('image/'))
    if (!f) return
    setEnviandoFundo(true)
    try {
      setFundoIdeogram(await api.enviarReferencia(f))
      setZonas(null)
    } catch (e) {
      setErro(String(e))
    } finally {
      setEnviandoFundo(false)
    }
  }

  const enviarRefsNuvem = async (arquivos: FileList | File[]) => {
    const fotos = Array.from(arquivos).filter((a) => a.type.startsWith('image/'))
    if (!fotos.length) return
    const teto = nuvemAtual?.max_referencias ?? 14
    const cabem = fotos.slice(0, Math.max(0, teto - refsNuvem.length))
    if (!cabem.length) {
      setErro(`Este modelo aceita no maximo ${teto} imagens de referencia.`)
      return
    }
    setEnviandoRefNuvem(true)
    try {
      const enviadas = await Promise.all(cabem.map((f) => api.enviarReferencia(f)))
      setRefsNuvem((atuais) => [...atuais, ...enviadas])
    } catch (e) {
      setErro(String(e))
    } finally {
      setEnviandoRefNuvem(false)
    }
  }

  const recarregarGaleria = useCallback(() => {
    api.galeria(60, undefined, mostrarTestes).then(setGaleria).catch(() => {})
    api.contarTestes().then((d) => setQuantosTestes(d.testes)).catch(() => {})
  }, [mostrarTestes])

  useEffect(() => {
    api.modelos().then((d) => {
      setModelos(d.modelos)
      setModosEdicao(d.edicao)
      setGruposEdicao(d.grupos_edicao ?? [])
      setModosExpansao(d.modos_expansao ?? [])
      setNiveisPele(d.niveis_pele ?? [])
      setTiposImagem(d.tipos_imagem ?? [])
      setEstilos(d.estilos ?? [])
      setProporcoes(d.proporcoes)
      setNuvem(d.nuvem ?? [])
      setNuvemPronta(d.nuvem_pronta ?? false)
      setCfgVideo(d.video)
      setCfgAmpliarVideo(d.ampliar_video)
      setCfgTransformarVideo(d.transformar_video ?? null)
    }).catch((e) => setErro(String(e)))
    recarregarGaleria()
    api.tarefas().then(iniciais => setTarefas(atuais => [
      ...atuais, ...iniciais.filter(t => !atuais.some(a => a.id === t.id)),
    ])).catch(() => {})

    const verificar = () =>
      api.saude()
        .then((s) => { setMotorVivo(s.motor); setMotorCarregado(s.motor_carregado) })
        .catch(() => setMotorVivo(false))
    verificar()
    const pulso = setInterval(verificar, 4000)

    const pararEscuta = ouvirTarefas((t) => {
      setTarefas((antes) => [t, ...antes.filter((x) => x.id !== t.id)].slice(0, 40))
      if (t.estado === 'pronto' && t.imagens.length) {
        setVista(JSON.parse(t.imagens[0]))
        recarregarGaleria()
      }
      if (t.estado === 'erro') setErro(t.erro)
      if (t.estado === 'pronto') setAviso(t.aviso ?? '')
    })

    return () => {
      clearInterval(pulso)
      pararEscuta()
    }
  }, [recarregarGaleria])

  // Trocou entre local e Comfy Cloud: rele o catalogo, que no modo nuvem vem
  // marcado com o que roda la.
  useEffect(() => {
    if (versaoMotor === 0) return
    api.modelos().then((d) => {
      setModelos(d.modelos)
      setCfgTransformarVideo(d.transformar_video ?? null)
    }).catch((e) => setErro(String(e)))
  }, [versaoMotor])

  // O painel lateral le os dados da galeria, que ja tem tudo o que foi gravado.
  const itemVisivel = useMemo(
    () => galeria.find((i) => i.arquivo === vista?.nome && i.subpasta === vista?.subpasta) ?? null,
    [galeria, vista],
  )

  const galeriaFiltrada = useMemo(
    () => filtroGaleria === 'tudo'
      ? galeria
      : galeria.filter((item) => tipoDoItem(item) === filtroGaleria),
    [filtroGaleria, galeria],
  )

  const abrirVisualizador = useCallback((item: ItemGaleria) => {
    setVista({ nome: item.arquivo, subpasta: item.subpasta })
    setItemModal(item)
  }, [])

  const navegarVisualizador = useCallback((passo: number) => {
    setItemModal((atual) => {
      if (!atual || galeriaFiltrada.length < 2) return atual
      const posicao = galeriaFiltrada.findIndex((item) => item.id === atual.id)
      const proxima = galeriaFiltrada[
        (Math.max(0, posicao) + passo + galeriaFiltrada.length) % galeriaFiltrada.length
      ]
      setVista({ nome: proxima.arquivo, subpasta: proxima.subpasta })
      return proxima
    })
  }, [galeriaFiltrada])

  useEffect(() => {
    if (!itemModal) return
    const aoTeclar = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setItemModal(null)
      if (e.key === 'ArrowLeft') navegarVisualizador(-1)
      if (e.key === 'ArrowRight') navegarVisualizador(1)
    }
    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  }, [itemModal, navegarVisualizador])

  const tarefaAtiva = useMemo(
    () => tarefas.find(t => t.estado === 'executando' || t.estado === 'preparando')
      ?? tarefas.find((t) => EM_ANDAMENTO.includes(t.estado)),
    [tarefas],
  )
  const [falhaRecente, setFalhaRecente] = useState<Tarefa | null>(null)
  const ultimaAtiva = useRef<string | null>(null)
  useEffect(() => {
    if (tarefaAtiva) {
      ultimaAtiva.current = tarefaAtiva.id
      setFalhaRecente(null)
    } else if (ultimaAtiva.current) {
      setFalhaRecente(tarefas.find(t => t.id === ultimaAtiva.current && t.estado === 'erro') ?? null)
      ultimaAtiva.current = null
    }
  }, [tarefaAtiva, tarefas])
  const tarefaNoTopo = tarefaAtiva ?? falhaRecente

  // Também reconciliar por HTTP: uma desconexão do WebSocket não pode
  // deixar um pedido concluído parecendo eternamente em execução.
  useEffect(() => {
    if (!tarefaAtiva) return
    let ativo = true
    let consultando = false
    const id = tarefaAtiva.id
    const verificar = async () => {
      if (consultando) return
      consultando = true
      try {
        const novas = await api.tarefas()
        if (!ativo) return
        setTarefas(atuais => novas.map(nova => {
          const anterior = atuais.find(t => t.id === nova.id)
          if (anterior && (anterior.estado === 'pronto' || anterior.estado === 'erro')
            && EM_ANDAMENTO.includes(nova.estado)) return anterior
          if ((anterior?.ultimo_avanco_em || 0) > (nova.ultimo_avanco_em || 0)) return anterior!
          return nova
        }))
        const concluida = novas.find(t => t.id === id && t.estado === 'pronto')
        if (concluida) {
          if (concluida.imagens.length) setVista(JSON.parse(concluida.imagens[0]))
          setAviso(concluida.aviso || '')
          recarregarGaleria()
        }
        const falhou = novas.find(t => t.id === id && t.estado === 'erro')
        if (falhou) setErro(falhou.erro)
      } catch { /* A próxima consulta ou o WebSocket pode reconectar. */ }
      finally { consultando = false }
    }
    verificar()
    const pulso = window.setInterval(verificar, 5000)
    return () => { ativo = false; clearInterval(pulso) }
  }, [tarefaAtiva?.id, recarregarGaleria])

  const montarCaption = (): Caption => ({
    aspect_ratio: proporcao,
    high_level_description: descricao || prompt,
    compositional_deconstruction: {
      background: fundo || 'A clean, uncluttered background.',
      elements: elementos.map((e) => ({
        type: e.tipo,
        bbox: e.bbox.map(Math.round),
        desc: e.desc,
        ...(e.tipo === 'text' ? { text: e.texto ?? '' } : {}),
      })),
    },
  })

  const gerar = async () => {
    setErro('')
    try {
      await api.gerar({
        modelo,
        prompt,
        negativo,
        proporcao,
        escala: comPersonagem ? 1 : escala,
        nativo_4k: nativo4k && !!(modeloAtual as { nativo_4k?: unknown } | undefined)?.nativo_4k,
        lote: comPersonagem ? 1 : lote,
        seed: seed.trim() === '' ? null : Number(seed),
        steps: steps.trim() === '' ? null : Number(steps),
        cfg: cfg.trim() === '' ? null : Number(cfg),
        qualidade,
        resolucao_nuvem: resolucaoNuvem,
        qualidade_nuvem: qualidadeNuvem,
        fundo_nuvem: fundoNuvem,
        caption: ehIdeogram && usarCaixas ? montarCaption() : null,
        referencias: nuvemAtual
          ? refsNuvem.map((r) => r.nome)
          : ehIdeogram && fundoIdeogram
            ? [fundoIdeogram.nome]
            : comPersonagem ? refsPersonagem.map((r) => r.nome) : [],
        forca_referencia: forcaReferencia,
        posicoes_referencia: comPersonagem && refsPersonagem.length > 1
          ? refsPersonagem.map((_, i) => posicoesPersonagem[i] ?? '') : [],
        tinta: ehIdeogram && fundoIdeogram ? tinta : null,
        expandir_prompt: expandir && !ehIdeogram,
        modo_expansao: modoExpansao,
        estilo,
        estilo_manual: estiloManual,
      })
    } catch (e) {
      setErro(String(e))
    }
  }

  /** Pede ao modelo local que escreva o layout, e abre no editor de caixas. */
  const sugerirLayout = async () => {
    setErro('')
    setPensando(true)
    try {
      const r = await api.caption(prompt, proporcao, fundoIdeogram?.nome)
      const c = r.caption
      setZonas(r.zonas)
      setDescricao(c.high_level_description)
      setFundo(c.compositional_deconstruction.background)
      setElementos(
        (c.compositional_deconstruction.elements as Record<string, never>[])
          .filter((e) => Array.isArray(e.bbox))
          .map((e) => ({
            tipo: e.type === 'text' ? 'text' : 'obj',
            bbox: e.bbox as unknown as Elemento['bbox'],
            texto: (e.text as unknown as string) ?? '',
            desc: (e.desc as unknown as string) ?? '',
          })),
      )
      setUsarCaixas(true)
    } catch (e) {
      setErro(String(e))
    } finally {
      setPensando(false)
    }
  }

  /** Botões do painel de informações: agem sobre a imagem em foco. */
  const agir = async (acao: Acao, item: ItemGaleria) => {
    setErro('')
    try {
      if (acao === 'variar') {
        const p = item.parametros as Record<string, string | number | null>
        await api.gerar({
          modelo: item.modelo,
          prompt: item.prompt,
          negativo: String(p.negativo ?? ''),
          proporcao: String(p.proporcao ?? '1:1'),
          escala: Number(p.escala ?? 1),
          qualidade: String(p.qualidade ?? 'padrao'),
          caption: item.caption,
          referencias: (item.parametros?.referencias_usadas as string[] | undefined) ?? [],
          forca_referencia: Number(item.parametros?.forca_referencia ?? 1),
          posicoes_referencia: (item.parametros?.posicoes_referencia as string[] | undefined) ?? [],
          seed: null,
        })
        return
      }

      const ref = await referenciaDaGaleria(item)
      if (acao === 'personagem') {
        usarPersonagem(ref)
        if (!modeloAtual?.referencia_personagem) setModelo('krea')
        setMeio('imagem')
        setAba('gerar')
        return
      }
      if (acao === 'referencia') {
        // Acrescenta à lista atual, sem descartar o que já estava lá.
        setModoEdicao((m) => (m === 'ampliar' || m === 'controle' ? 'trocar' : m))
        setReferenciasEdicao((lista) => [...lista, ref])
      } else {
        setModoEdicao(acao === 'ampliar' ? 'ampliar' : 'instrucao')
        setReferenciasEdicao(() => [ref])
      }
      setMeio('imagem')
      setAba('editar')
    } catch (e) {
      setErro(String(e))
    }
  }

  const reusar = (item: ItemGaleria) => {
    setErro('')
    if (item.modelo === 'video') {
      setReusoVideo((anterior) => ({ item, versao: (anterior?.versao ?? 0) + 1 }))
      setMeio('video')
      return
    }
    if (item.modelo === 'musica') { setMeio('musica'); setReusoMusica({ ...item }); return }
    if (item.modelo === 'voz') {
      setMeio('voz'); setReusoVoz({ ...item }); return
    }
    const p = item.parametros as Record<string, string | number | null>
    // O botão não sabia que existe aba de edição: ele mandava o id do modo
    // para o seletor de GERAÇÃO, que não o conhece, e o formulário ficava num
    // estado impossível. Agora cada modo vai para a aba a que pertence.
    const ehEdicao = modosEdicao.some((m) => m.id === item.modelo)
    const ehGeracao = modelos.some((m) => m.id === item.modelo)
    if (!ehEdicao && !ehGeracao) {
      setErro('Esta imagem não guarda um modo reutilizável — é um recorte ou '
              + 'veio de fora do aplicativo.')
      return
    }
    if (ehEdicao) {
      setMeio('imagem')
      setAba('editar')
      setModoEdicao(item.modelo)
      setReuso({ ...p })           // o painel de edição aplica o que é dele
    } else {
      setMeio('imagem')
      setAba('gerar')
      setModelo(item.modelo)
      const refs = item.parametros?.referencias_usadas as string[] | undefined
      const doPersonagem = item.modelo === 'krea' || item.modelo === 'kroma' || item.modelo === 'kroma_foto'
      setRefsPersonagem(doPersonagem ? (refs ?? []).slice(0, 3).map((n) => ({ nome: n, url: urlEntrada(n) })) : [])
      setPosicoesPersonagem((item.parametros?.posicoes_referencia as string[] | undefined) ?? [])
      setForcaReferencia(Number(item.parametros?.forca_referencia ?? 1))
    }
    setPrompt(item.prompt)
    if (p.proporcao) setProporcao(String(p.proporcao))
    if (p.seed != null) setSeed(String(p.seed))
    if (p.negativo) setNegativo(String(p.negativo))
    if (item.caption) {
      setDescricao(item.caption.high_level_description)
      setFundo(item.caption.compositional_deconstruction.background)
      setElementos(
        (item.caption.compositional_deconstruction.elements as Record<string, never>[])
          .filter((e) => Array.isArray(e.bbox))
          .map((e) => ({
            tipo: e.type === 'text' ? 'text' : 'obj',
            bbox: e.bbox as unknown as Elemento['bbox'],
            texto: (e.text as unknown as string) ?? '',
            desc: (e.desc as unknown as string) ?? '',
          })),
      )
      setUsarCaixas(true)
    }
  }

  const ocupado = Boolean(tarefaAtiva)

  // O saldo e relido quando a fila esvazia: e o unico momento em que ele
  // pode ter mudado. Um cronometro fixo gastaria requisicao a toa, e ler
  // so na abertura deixaria o numero velho na tela depois de gerar.
  useEffect(() => {
    api.saldoNuvem(true).then(setSaldo).catch(() => setSaldo({ ok: false, motivo: 'sem resposta' }))
  }, [ocupado, nuvem.length])

  return (
    <div className="app">
      <aside className="lateral">
        <div className="abas">
          <button data-ativo={meio === 'imagem'} onClick={() => setMeio('imagem')}>
            Imagem
          </button>
          <button data-ativo={meio === 'video'} onClick={() => setMeio('video')}>
            Vídeo
          </button>
          <button data-ativo={meio === 'voz'} onClick={() => setMeio('voz')}>Voz</button>
          <button data-ativo={meio === 'musica'} onClick={() => setMeio('musica')}>Música</button>
          <button data-ativo={meio === 'avatar'} onClick={() => setMeio('avatar')}>Avatar</button>
        </div>

        {/* Tarefas de imagem, no mesmo padrao das do video. */}
        {meio === 'imagem' && (
          <div className="abas-internas">
            <button data-ativo={aba === 'gerar'} onClick={() => setAba('gerar')}>
              Gerar
            </button>
            <button data-ativo={aba === 'editar'} onClick={() => setAba('editar')}>
              Editar
            </button>
          </div>
        )}

        {meio === 'musica' && (
          <div className="abas-internas">
            <button data-ativo={abaMusica === 'gerar'} onClick={() => setAbaMusica('gerar')}>Gerar</button>
            <button data-ativo={abaMusica === 'separar'} onClick={() => setAbaMusica('separar')}>Separar faixas</button>
            <button data-ativo={abaMusica === 'trocar'} onClick={() => setAbaMusica('trocar')}>Trocar voz</button>
          </div>
        )}

        {erro && <div className="aviso-erro">{erro}</div>}
        {aviso && <div className="aviso-atencao">{aviso}</div>}

        {meio === 'avatar' ? (
          <PainelAvatar motorVivo={motorVivo} aoErro={setErro} galeria={galeria} />
        ) : meio === 'musica' && abaMusica === 'separar' ? (
          <PainelSeparar motorVivo={motorVivo} aoErro={setErro} galeria={galeria} />
        ) : meio === 'musica' && abaMusica === 'trocar' ? (
          <PainelTrocarVoz motorVivo={motorVivo} aoErro={setErro} galeria={galeria} />
        ) : meio === 'musica' ? (
          <PainelMusica motorVivo={motorVivo} aoErro={setErro} reuso={reusoMusica} />
        ) : meio === 'voz' ? (
          <PainelVoz motorVivo={motorVivo} aoErro={setErro} reuso={reusoVoz} galeria={galeria} />
        ) : meio === 'video' ? (
          <PainelVideo
            key={reusoVideo?.versao ?? 0}
            fluxoInicial={location.hash.startsWith('#advanced/ltx-') ? location.hash.slice('#advanced/ltx-'.length) : undefined}
            reuso={reusoVideo?.item}
            cfg={cfgVideo}
            ampliar={cfgAmpliarVideo}
            transformar={cfgTransformarVideo}
            galeria={galeria}
            ocupado={ocupado}
            motorVivo={motorVivo}
            aoErro={setErro}
          />
        ) : aba === 'editar' ? (
          <PainelEdicao
            modos={modosEdicao}
            gruposEdicao={gruposEdicao}
            proporcoes={proporcoes}
            galeria={galeria}
            motorVivo={motorVivo}
            motorCarregado={motorCarregado}
            reuso={reuso}
            aoAplicarReuso={() => setReuso(null)}
            aoErro={setErro}
            niveisPele={niveisPele}
            tiposImagem={tiposImagem}
            modo={modoEdicao}
            setModo={setModoEdicao}
            referencias={referenciasEdicao}
            setReferencias={setReferenciasEdicao}
          />
        ) : (
        <>
        <Seletor
          rotulo="Modelo"
          valor={modelo}
          aoEscolher={setModelo}
          grupos={[
            { id: 'local', rotulo: 'Na sua placa (sem custo)' },
            { id: 'nuvem', rotulo: 'Na nuvem (gasta credito por imagem)' },
          ]}
          opcoes={[
            ...modelos.map((m) => ({
              id: m.id,
              rotulo: m.rotulo,
              sufixo: m.nuvem === false ? 'só local' : m.nuvem ? 'Comfy Cloud' : 'local',
              descricao: m.descricao,
              segundos: m.segundos_estimados,
              grupo: 'local',
            })),
            // Os de nuvem vao no MESMO seletor, mas num grupo proprio: o
            // rotulo do grupo e que avisa do custo. Um controle separado
            // esconderia a escolha; misturar sem grupo esconderia o preco.
            ...nuvem.map((m) => ({
              id: m.id,
              rotulo: m.rotulo,
              // Mesma regra da aba Video: o NOME primeiro, onde roda em
              // italico depois. O prefixo do grupo empurrava o nome do modelo
              // para o fim da linha fechada.
              sufixo: 'nuvem',
              descricao: m.descricao,
              segundos: m.segundos_estimados,
              grupo: 'nuvem',
            })),
          ]}
        />

        {modeloAtual?.referencia_personagem && (
          <div className="campo">
            <label>Personagens de referência <span className="opcional">opcional · até 3</span></label>
            <p className="dica">Uma imagem por personagem, com um único personagem em cada. Descreva a cena no prompt. Com 2 ou 3, o primeiro entra na cena e cada um dos seguintes é adicionado numa passada própria (leva mais tempo); nesse caso descreva só o lugar e o clima, sem citar as pessoas (“os três amigos”), senão o modelo inventa figurantes. As referências permanecem para as próximas gerações.</p>
            {refsPersonagem.length > 0 && <div className="refs-nuvem">{refsPersonagem.map((r, i) => <div key={r.nome + i} className="ref-nuvem">
              <img src={r.url} alt={`Personagem ${i + 1}`} />
              <button className="mini" title="Remover este personagem" onClick={() => {
                setRefsPersonagem((rs) => rs.filter((_, j) => j !== i))
                setPosicoesPersonagem((ps) => ps.filter((_, j) => j !== i))
              }}>×</button>
              {refsPersonagem.length > 1 && <select aria-label={`Posição do personagem ${i + 1}`} value={posicoesPersonagem[i] ?? ''}
                onChange={(e) => setPosicoesPersonagem((ps) => { const n = [...ps]; n[i] = e.target.value; return n })}>
                <option value="">{i + 1}º · posição livre</option>
                <option value="esquerda">{i + 1}º · à esquerda</option>
                <option value="centro">{i + 1}º · no centro</option>
                <option value="direita">{i + 1}º · à direita</option>
              </select>}
            </div>)}</div>}
            <button type="button" className="area-solta" disabled={enviandoPersonagem || refsPersonagem.length >= 3}
                 onDragOver={(e) => e.preventDefault()}
                 onDrop={(e) => { e.preventDefault(); void enviarPersonagem(e.dataTransfer.files[0]) }}
                 onClick={() => entradaPersonagem.current?.click()}>
              {enviandoPersonagem ? 'Enviando…' : refsPersonagem.length >= 3 ? 'Limite de 3 personagens' : refsPersonagem.length ? 'Adicionar outro personagem' : 'Arraste a imagem ou clique para escolher'}
            </button>
            <input ref={entradaPersonagem} type="file" accept="image/*" hidden disabled={enviandoPersonagem}
                   onChange={(e) => { void enviarPersonagem(e.target.files?.[0]); e.target.value = '' }} />
            {comPersonagem && <>
              <label>Fidelidade à referência: {forcaReferencia.toFixed(1)}×</label>
              <input type="range" min={0.5} max={4} step={0.1} value={forcaReferencia}
                     onChange={(e) => setForcaReferencia(Number(e.target.value))} />
              <p className="dica">Valores maiores prendem mais a aparência e podem limitar a mudança de cena. Gera uma imagem por vez, na resolução padrão. Kroma: compatibilidade experimental.</p>
            </>}
          </div>
        )}

        {nuvemAtual && (
          <div className="aviso-nuvem">
            {nuvemPronta ? (
              <>
                {/* Na familia da OpenAI a qualidade vem ANTES do tamanho:
                    ela e quem move mais o preco — de US$ 0,008 a US$ 0,61,
                    setenta vezes. */}
                {nuvemAtual.familia === 'openai' && (
                  <>
                    <div className="campo">
                      <label>Qualidade</label>
                      <div className="linha-botoes">
                        {(nuvemAtual.qualidades ?? []).map((q) => (
                          <button
                            key={q}
                            type="button"
                            className={q === qualidadeNuvem ? 'escolhido' : ''}
                            onClick={() => setQualidadeNuvem(q)}
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="campo">
                      <label>Fundo</label>
                      <div className="linha-botoes">
                        {(nuvemAtual.fundos ?? []).map((f) => (
                          <button
                            key={f.id}
                            type="button"
                            className={f.id === fundoNuvem ? 'escolhido' : ''}
                            onClick={() => setFundoNuvem(f.id)}
                          >
                            {f.rotulo}
                          </button>
                        ))}
                      </div>
                    </div>
                  </>
                )}

                <div className="campo">
                  <label>Resolução</label>
                  <div className="linha-botoes">
                    {(nuvemAtual.niveis ?? nuvemAtual.resolucoes ?? []).map((r) => (
                      <button
                        key={r}
                        type="button"
                        className={r === resolucaoNuvem ? 'escolhido' : ''}
                        onClick={() => setResolucaoNuvem(r)}
                        disabled={nuvemAtual.familia === 'openai'
                          && orientacaoNuvem === 'quadrado' && r === '4K'}
                        title={nuvemAtual.familia === 'openai'
                          && orientacaoNuvem === 'quadrado' && r === '4K'
                          ? 'O GPT Image não oferece saída 4K quadrada.'
                          : undefined}
                      >
                        {r}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="campo">
                  <label>
                    Imagens de referencia{' '}
                    <span className="opcional">
                      opcional &middot; ate {nuvemAtual.max_referencias}
                    </span>
                  </label>
                  {/* O MESMO no gera do zero e edita: sem referencia ele cria,
                      com referencia ele edita ou mantem o personagem. Por isso
                      isto fica aqui dentro, e nao numa aba de edicao separada. */}
                  {refsNuvem.length > 0 && (
                    <div className="refs-nuvem">
                      {refsNuvem.map((r, i) => (
                        <div key={r.nome} className="ref-nuvem">
                          <img src={r.url} alt="" />
                          <button
                            className="mini"
                            title="Remover"
                            onClick={() =>
                              setRefsNuvem((a) => a.filter((_, j) => j !== i))
                            }
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {refsNuvem.length < nuvemAtual.max_referencias && (
                    <div
                      className="area-solta"
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault()
                        enviarRefsNuvem(e.dataTransfer.files)
                      }}
                      onClick={() => entradaRefNuvem.current?.click()}
                    >
                      {enviandoRefNuvem
                        ? 'Enviando…'
                        : refsNuvem.length
                          ? 'Acrescentar outra'
                          : 'Arraste fotos aqui para editar ou manter o personagem'}
                      <input
                        ref={entradaRefNuvem}
                        type="file"
                        accept="image/*"
                        multiple
                        hidden
                        onChange={(e) => {
                          if (e.target.files) enviarRefsNuvem(e.target.files)
                          e.target.value = ''
                        }}
                      />
                    </div>
                  )}
                  {refsNuvem.length > 0 && (
                    <p className="dica">
                      Com referencia, descreva a <strong>mudanca</strong>, e nao a
                      cena inteira: <em>troque o fundo por uma rua molhada a
                      noite</em>. A foto sai do seu computador e vai para o
                      servidor do provedor.
                    </p>
                  )}
                </div>

              </>
            ) : (
              <p className="custo alerta">
                Falta a chave de API. Cole-a em <code>backend/chaves.json</code> e
                recarregue a página. Sem ela este modelo não gera, e nada é cobrado.
              </p>
            )}
          </div>
        )}

        <div className="campo">
          <label>{ehIdeogram && usarCaixas ? 'Ideia geral' : 'Prompt'}</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={
              ehIdeogram
                ? 'Descreva a peça. Ponha entre aspas o texto que deve ser impresso.'
                : 'Descreva a imagem que você quer'
            }
          />
          {/* O contrato do Ideogram trata aspas como conteúdo literal e o resto
              como descrição. Sem aspas ele às vezes imprime a própria
              instrução — "CÓDIGO DE BARRAS NO RODAPÉ" saiu escrito na peça. */}
          {ehIdeogram && (
            <p className="dica">
              Ponha <strong>entre aspas</strong> o que deve aparecer escrito:{' '}
              <em>cartaz com o título "A TRAVESSIA DO SILÊNCIO"</em>. O que você
              descrever sem aspas vira instrução de layout, e o modelo inventa o
              conteúdo — às vezes ele erra e imprime a própria descrição.
            </p>
          )}
        </div>

        {!ehIdeogram && (
          <div className="campo">
            <label className="alternador">
              <input
                type="checkbox"
                checked={expandir}
                onChange={(e) => setExpandir(e.target.checked)}
              />
              <span>
            Enriquecer o prompt
            <Ajuda titulo="O que isto faz">
              Um modelo de linguagem local reescreve a sua frase, acrescentando
              material, luz e clima. Não custa crédito, mas leva alguns segundos
              e muda o que você escreveu.
            </Ajuda>
          </span>
            </label>
            {expandir && (
              <div className="opcoes segmentado" style={{ marginTop: 6 }}>
                {modosExpansao.map((o) => (
                  <button
                    key={o.id}
                    className="opcao"
                    data-ativo={modoExpansao === o.id}
                    onClick={() => setModoExpansao(o.id)}
                  >
                    <b>{o.rotulo}</b>
                    <small>{o.nota}</small>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="campo">
          <label>Estilo</label>
          <div className="opcoes">
            {estilos.map((e) => (
              <button key={e.id} data-ativo={estilo === e.id} title={e.nota}
                      onClick={() => setEstilo(e.id)}>
                {e.rotulo}
              </button>
            ))}
          </div>
          <p className="dica" style={{ marginTop: 6, marginBottom: 0 }}>
            {estilos.find((e) => e.id === estilo)?.nota}
          </p>

          {estilo === 'manual' && (
            <textarea
              style={{ marginTop: 8, minHeight: 62 }}
              value={estiloManual}
              onChange={(e) => setEstiloManual(e.target.value)}
              placeholder="O acréscimo de estilo, em inglês. Ex.: soft anamorphic lens flare, muted teal palette"
            />
          )}

          {estilo !== 'livre' && modeloAtual?.honra_negativo === false && (
            <p className="dica" style={{ marginTop: 6, marginBottom: 0 }}>
              Neste modelo o <strong>negativo do estilo não é aplicado</strong>:
              ele roda em CFG 1, onde o prompt negativo é ignorado pelo próprio
              método. O acréscimo positivo vale normalmente.
            </p>
          )}
        </div>

        <div className="campo">
          <label>Proporção</label>
          <div className="opcoes segmentado">
            {proporcoes.map((p) => (
              <button
                key={p}
                data-ativo={proporcao === p}
                onClick={() => {
                  setProporcao(p)
                  if (nuvemAtual?.familia === 'openai' && p === '1:1') {
                    setResolucaoNuvem((r) => r === '4K' ? '2K' : r)
                  }
                }}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        {ehIdeogram && (
          <>
            <div className="campo">
              <label>Qualidade</label>
              <div className="opcoes segmentado">
                {(modeloAtual?.qualidades ?? []).map((q) => (
                  <button key={q} data-ativo={qualidade === q} onClick={() => setQualidade(q)}>
                    {q}
                  </button>
                ))}
              </div>
            </div>

            <div className="campo">
              <label>Imagem de fundo</label>
              {fundoIdeogram ? (
                <div className="fundo-escolhido">
                  <img src={fundoIdeogram.url} alt="" />
                  <div>
                    <p>A foto não passa pelo modelo. Só as letras são aplicadas
                      sobre ela, e o resto fica idêntico ao original.</p>
                    <button className="mini" onClick={() => { setFundoIdeogram(null); setZonas(null) }}>
                      Remover
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  className="area-solta"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault()
                    enviarFundo(e.dataTransfer.files)
                  }}
                  onClick={() => entradaFundo.current?.click()}
                >
                  {enviandoFundo
                    ? 'Enviando…'
                    : 'Arraste uma foto aqui, ou clique para escolher'}
                  <input
                    ref={entradaFundo}
                    type="file"
                    accept="image/*"
                    hidden
                    onChange={(e) => {
                      if (e.target.files) enviarFundo(e.target.files)
                      e.target.value = ''
                    }}
                  />
                </div>
              )}
            </div>

            {fundoIdeogram && (
              <div className="campo">
                <label>Cor da tipografia</label>
                <div className="tintas">
                  {TINTAS.map((t) => (
                    <button
                      key={t.cor}
                      className="tinta"
                      data-ativo={tinta === t.cor}
                      title={t.nome}
                      style={{ background: t.cor }}
                      onClick={() => setTinta(t.cor)}
                    />
                  ))}
                  <input
                    type="color"
                    value={tinta}
                    onChange={(e) => setTinta(e.target.value)}
                    title="Outra cor"
                  />
                </div>
              </div>
            )}

            <div className="campo">
              <label className="alternador">
                <input
                  type="checkbox"
                  checked={usarCaixas}
                  onChange={(e) => setUsarCaixas(e.target.checked)}
                />
                <span>Definir o layout à mão</span>
              </label>
            </div>

            {!usarCaixas && (
              <p className="dica">
                Sem layout manual, o modelo local escreve a composição a partir da
                sua ideia — leva alguns segundos a mais.
              </p>
            )}

            {usarCaixas && (
              <>
                <button
                  onClick={sugerirLayout}
                  disabled={pensando || !prompt.trim()}
                  style={{ width: '100%', marginBottom: 12 }}
                >
                  {pensando ? 'Escrevendo o layout…' : 'Sugerir layout a partir da ideia'}
                </button>
                <div className="campo">
                  <label>Descrição geral</label>
                  <textarea
                    value={descricao}
                    onChange={(e) => setDescricao(e.target.value)}
                    placeholder="Resumo do que a imagem mostra"
                  />
                </div>
                <div className="campo">
                  <label>Fundo</label>
                  <textarea
                    value={fundo}
                    onChange={(e) => setFundo(e.target.value)}
                    placeholder="Como é o fundo da peça"
                  />
                </div>
                <div className="campo">
                  <label>Elementos</label>
                  <EditorCaixas
                    proporcao={proporcao}
                    elementos={elementos}
                    aoMudar={setElementos}
                    fundo={fundoIdeogram?.url}
                    zonas={zonas}
                  />
                </div>
              </>
            )}
          </>
        )}

        <details className="avancado">
          <summary>Avançado</summary>
          {!ehIdeogram && (
            <div className="campo">
              <label>Prompt negativo</label>
              <textarea
                value={negativo}
                onChange={(e) => setNegativo(e.target.value)}
                placeholder="Deixe vazio para usar o padrão do modelo"
                style={{ minHeight: 60 }}
              />
            </div>
          )}
          <div className="linha" style={{ marginBottom: 12 }}>
            <div>
              <label style={{ fontSize: 12, color: 'var(--apagado)' }}>Seed</label>
              <input
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                placeholder="aleatória"
              />
            </div>
            {/* O no de nuvem devolve UMA imagem por chamada: nao existe
                entrada de lote nele. Mostrar o campo faria o numero ser
                ignorado sem aviso, e o custo na tela mentiria. */}
            {!nuvemAtual && (
              <div>
                <label style={{ fontSize: 12, color: 'var(--apagado)' }}>Imagens</label>
                <input
                  type="number"
                  min={1}
                  max={8}
                  value={comPersonagem ? 1 : lote}
                  disabled={comPersonagem}
                  onChange={(e) => setLote(Number(e.target.value))}
                />
              </div>
            )}
          </div>
          {!ehIdeogram && !nuvemAtual && (
            <div className="linha" style={{ marginBottom: 12 }}>
              <div>
                <label style={{ fontSize: 12, color: 'var(--apagado)' }}>Steps</label>
                <input
                  value={steps}
                  onChange={(e) => setSteps(e.target.value)}
                  placeholder={String(modeloAtual?.steps ?? '')}
                />
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--apagado)' }}>CFG</label>
                <input
                  value={cfg}
                  onChange={(e) => setCfg(e.target.value)}
                  placeholder={String(modeloAtual?.cfg ?? '')}
                />
              </div>
            </div>
          )}
          {(modeloAtual as { nativo_4k?: { segundos: number } } | undefined)?.nativo_4k && (
            <label className="alternador">
              <input type="checkbox" checked={nativo4k} onChange={(e) => setNativo4k(e.target.checked)} />
              <span>
                4K nativo
                <Ajuda titulo="Sobre o 4K nativo">
                  Gera direto em cerca de 3840×2160, na proporção escolhida: detalhe
                  de verdade (poros, fios, texturas), e não só tamanho. Leva uns{' '}
                  {Math.round(((modeloAtual as { nativo_4k?: { segundos: number } }).nativo_4k?.segundos ?? 450) / 60)}{' '}
                  minutos por imagem e usa a placa inteira — feche o que estiver
                  usando a GPU. Para iterar, gere menor e amplie com o RTX.
                </Ajuda>
              </span>
            </label>
          )}
          <div>
            <label style={{ fontSize: 12, color: 'var(--apagado)' }}>
              Escala da resolução: {(comPersonagem ? 1 : escala).toFixed(2)}×
            </label>
            <input
              type="range"
              min={0.5}
              max={2}
              step={0.05}
              value={comPersonagem ? 1 : escala}
              disabled={comPersonagem || (nativo4k && !!(modeloAtual as { nativo_4k?: unknown } | undefined)?.nativo_4k)}
              onChange={(e) => setEscala(Number(e.target.value))}
            />
          </div>
        </details>

        <button
          className="principal"
          style={{ width: '100%' }}
          onClick={gerar}
          disabled={
            !motorVivo ||
            enviandoPersonagem ||
            (!prompt.trim() && !elementos.length) ||
            // Sem chave o pedido so voltaria como erro do provedor.
            (!!nuvemAtual && !nuvemPronta)
          }
        >
          {ocupado ? 'Adicionar à fila' : 'Gerar'}
          {/* O preco vai TAMBEM no botao, e nao so no bloco la em cima: o
              formulario e longo, e na hora do clique o aviso do topo costuma
              estar fora da tela. O numero tem de estar onde a mao esta. */}
          {nuvemAtual && nuvemPronta && ` · US$ ${custoDaPeca.toFixed(3)}`}
        </button>
        </>
        )}

        {ocupado && (
          <button style={{ width: '100%', marginTop: 8 }} title="Para a geração atual e cancela todas as que estão na fila" onClick={() => api.cancelar()}>
            Interromper tudo
          </button>
        )}
      </aside>

      <main className="centro">
        <div className="barra-topo">
          <div className="marca">
            <img className="marca-simbolo" src="/brand/easycomfee-symbol.svg" alt="" />
            <div className="marca-texto">
              <span>Estúdio criativo</span>
              <h1>EasyComfee</h1>
            </div>
          </div>
          <div className="espaco" />
          <span className="selo">
            <i className="ponto" data-vivo={motorVivo} />
            {motorVivo ? 'motor ativo' : 'motor desligado'}
          </span>
          {/* Desativado durante uma geracao: descarregar o modelo em uso a
              derrubaria. O backend recusa de novo, para o caso de a tela
              estar desatualizada. */}
          <button
            type="button"
            className="mini"
            disabled={!motorVivo || !!tarefaAtiva || liberando}
            title={tarefaAtiva
              ? 'Espere a geração terminar'
              : 'Descarrega os modelos e esvazia a memória da placa'}
            onClick={async () => {
              setLiberando(true)
              setAvisoMemoria('')
              try {
                const r = await api.liberarMemoria()
                setMotorCarregado(null)
                setAvisoMemoria(r.depois_gib != null
                  ? `placa com ${r.depois_gib.toFixed(1)} GiB em uso`
                  : 'memória liberada')
                setTimeout(() => setAvisoMemoria(''), 5000)
              } catch (e) {
                // O backend devolve {"detail": "..."}; a pessoa le a frase,
                // nao o JSON.
                const bruto = e instanceof Error ? e.message : String(e)
                let frase = bruto
                try { frase = JSON.parse(bruto).detail ?? bruto } catch { /* texto puro */ }
                setErro(frase)
              } finally {
                setLiberando(false)
              }
            }}
          >
            {liberando ? 'liberando…' : 'liberar memória'}
          </button>
          {avisoMemoria && <span className="selo">{avisoMemoria}</span>}
          <button className="mini" onClick={() => setMostrarModelos(true)}>Modelos</button>
          <SeletorMotor aoTrocar={() => setVersaoMotor((v) => v + 1)} />
          {mostrarModelos && <TelaModelos fechar={() => setMostrarModelos(false)} />}
          {/* O saldo fica na barra de topo, e nao so dentro do bloco de nuvem:
              assim ele continua visivel enquanto se trabalha nos modelos
              locais, que e quando se esquece que ele existe. */}
          {tarefaNoTopo && <PainelAndamento key={tarefaNoTopo.id} tarefa={tarefaNoTopo}
            naFila={tarefas.filter(t => t.estado === 'na_fila' && t.id !== tarefaNoTopo.id).length} />}
          {saldo && (
            <span className="selo" title={
              saldo.ok
                ? `Creditos do ComfyUI. Ja gastos aqui: US$ ${(saldo.gasto?.usd ?? 0).toFixed(4)} em ${saldo.gasto?.imagens ?? 0} imagens.`
                : `Nao foi possivel ler o saldo: ${saldo.motivo ?? 'motivo desconhecido'}`
            }>
              {saldo.ok ? `US$ ${(saldo.usd ?? 0).toFixed(2)}` : 'saldo ?'}
            </span>
          )}
          <div className="modo-central" role="group" aria-label="Conteúdo do painel central">
            <button
              type="button"
              data-ativo={modoCentral === 'palco'}
              aria-pressed={modoCentral === 'palco'}
              onClick={() => mudarModoCentral('palco')}
            >
              Visualizar
            </button>
            <button
              type="button"
              data-ativo={modoCentral === 'galeria'}
              aria-pressed={modoCentral === 'galeria'}
              onClick={() => mudarModoCentral('galeria')}
            >
              Galeria
            </button>
          </div>
          {modoCentral === 'palco' && (
            <button
              className="mini"
              data-ativo={mostrarInfo}
              onClick={() => setMostrarInfo((v) => !v)}
            >
              Informações
            </button>
          )}
        </div>

        {modoCentral === 'palco' ? (
          <div className="area-central">
            <Palco
              src={vista ? urlImagem(vista) : null}
              vazio={
                motorVivo
                  ? (meio === 'musica' ? 'Descreva uma música para gerar e ouvir aqui.' : meio === 'voz' ? 'Escreva o texto e gere uma narração para ouvir aqui.' : meio === 'video' ? 'Crie um vídeo para visualizar aqui.' : 'Escreva um prompt e gere a primeira imagem.')
                  : 'O ComfyUI não está respondendo em 127.0.0.1:8188. Inicie o motor e esta mensagem some sozinha.'
              }
            />
            {mostrarInfo && (
              <PainelInfo
                item={itemVisivel}
                estilos={estilos}
                geradoresVideo={cfgVideo?.geradores}
                aoFechar={() => setMostrarInfo(false)}
                aoReusar={reusar}
                aoAgir={agir}
                ocupado={ocupado}
              />
            )}
          </div>
        ) : (
          <GaleriaCentral
            itens={galeriaFiltrada}
            total={galeria.length}
            layout={layoutGaleria}
            selecionado={itemVisivel?.id ?? null}
            filtro={filtroGaleria}
            aoMudarLayout={mudarLayoutGaleria}
            aoMudarFiltro={mudarFiltroGaleria}
            aoSelecionar={(item) => setVista({ nome: item.arquivo, subpasta: item.subpasta })}
            aoAbrir={abrirVisualizador}
            aoAgir={agir}
            aoReusar={reusar}
            aoApagar={async (item) => {
              // So o registro sai; o arquivo fica no disco e pode ser reimportado.
              if (!confirm('Remover esta criação da galeria? O arquivo continua na pasta de saída.')) return
              try {
                await api.apagar(item.id)
                await recarregarGaleria()
              } catch (e) {
                setErro(String(e))
              }
            }}
          />
        )}

        <div
          className="galeria"
          data-aberta={galeriaAberta}
          hidden={modoCentral === 'galeria'}
        >
          <button className="cabecalho-galeria" onClick={alternarGaleria}>
            <span className="seta">{galeriaAberta ? '▾' : '▸'}</span>
            Galeria
            <em>
              {galeria.length === 0
                ? 'vazia'
                : filtroGaleria === 'tudo'
                  ? `${galeria.length} itens`
                  : `${galeriaFiltrada.length} de ${galeria.length}`}
            </em>
          </button>

          {galeriaAberta && (
            <div className="filtros-tipo-galeria" role="group" aria-label="Filtrar galeria por tipo">
              {FILTROS_GALERIA.map((filtro) => (
                <button
                  key={filtro.id}
                  type="button"
                  data-ativo={filtroGaleria === filtro.id}
                  aria-pressed={filtroGaleria === filtro.id}
                  onClick={() => mudarFiltroGaleria(filtro.id)}
                >
                  {filtro.rotulo}
                </button>
              ))}
            </div>
          )}

          {galeriaAberta && quantosTestes > 0 && (
            <label className="alternador filtro-galeria">
              <input
                type="checkbox"
                checked={mostrarTestes}
                onChange={(e) => setMostrarTestes(e.target.checked)}
              />
              <span>Mostrar os {quantosTestes} itens de teste</span>
            </label>
          )}

          <div className="galeria-tiras" hidden={!galeriaAberta}>
            {galeria.length === 0 && (
              <span className="selo">Nada gerado ainda.</span>
            )}
            {galeria.length > 0 && galeriaFiltrada.length === 0 && (
              <span className="selo">Nenhum item deste tipo.</span>
            )}
            {galeriaFiltrada.map((item) => (
              <button
                key={item.id}
                className="miniatura"
                data-ativo={vista?.nome === item.arquivo}
                aria-label={`${item.rotulo ?? item.modelo} · ${item.prompt.slice(0, 120)}`}
                title={`${item.rotulo ?? item.modelo} · ${item.prompt.slice(0, 120)}`}
                onClick={() => setVista({ nome: item.arquivo, subpasta: item.subpasta })}
                onDoubleClick={() => abrirVisualizador(item)}
              >
                {['voz', 'musica'].includes(item.modelo) ? <span style={{ fontSize: 32 }}>♪</span> : <img
                  src={urlMiniatura({ nome: item.arquivo, subpasta: item.subpasta })}
                  loading="lazy"
                  alt=""
                />}
              </button>
            ))}
          </div>
        </div>

        {itemModal && (
          <div
            className="fundo-visualizador"
            role="dialog"
            aria-modal="true"
            aria-label={`Visualizando ${itemModal.rotulo ?? itemModal.arquivo}`}
            onMouseDown={(e) => {
              if (e.target === e.currentTarget) setItemModal(null)
            }}
          >
            <div className="janela-visualizador">
              <button
                type="button"
                className="fechar-visualizador"
                onClick={() => setItemModal(null)}
                aria-label="Fechar visualizador"
                title="Fechar (Esc)"
              >
                ×
              </button>
              {galeriaFiltrada.length > 1 && (
                <>
                  <button
                    type="button"
                    className="navegar-visualizador anterior"
                    onClick={() => navegarVisualizador(-1)}
                    aria-label="Criação anterior"
                    title="Anterior (seta esquerda)"
                  >
                    ‹
                  </button>
                  <button
                    type="button"
                    className="navegar-visualizador proxima"
                    onClick={() => navegarVisualizador(1)}
                    aria-label="Próxima criação"
                    title="Próxima (seta direita)"
                  >
                    ›
                  </button>
                </>
              )}
              <div className="corpo-visualizador">
                <Palco
                  src={urlImagem({ nome: itemModal.arquivo, subpasta: itemModal.subpasta })}
                  vazio="Arquivo indisponível."
                />
                <PainelInfo
                  item={itemModal}
                  estilos={estilos}
                  geradoresVideo={cfgVideo?.geradores}
                  aoFechar={() => setItemModal(null)}
                  aoReusar={reusar}
                  aoAgir={agir}
                  ocupado={ocupado}
                />
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
