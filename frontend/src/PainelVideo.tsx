import { useEffect, useRef, useState } from 'react'

import Ajuda from './Ajuda'
import PreviaLatente from './PreviaLatente'
import Seletor from './Seletor'
import {
  api, referenciaDaGaleria, urlEntrada, urlImagem, urlMiniatura, type ItemGaleria, type ModeloVideo,
  type Referencia,
} from './api'

// Painel do gerador de video local (LTX 2.5).
//
// Aba PROPRIA, e nao um modelo dentro de "Gerar": os controles nao se parecem
// com os de imagem (duracao, fps, audio) e a saida nem imagem e. Enfiar isso
// no painel de geracao faria metade dos campos aparecer e sumir conforme a
// escolha, que e exatamente o tipo de tela que confunde.

type MetodoAmpliar = { id: string; rotulo: string; nota: string; segundos: number }

// Espelha presets.tamanho_de_video. O "p" e o LADO MENOR, como se usa em
// video: um clipe em pe a 720p e 720x1280. O alinhamento de 32 e o mesmo do
// ResolutionSelector — e dele que vem o 704 quando se pede 720.
const ALTURA_P: Record<string, number> = { '480p': 480, '720p': 720, '768p': 768, '1080p': 1080 }

function pixelsDe(res: string, prop: string, mult: number): [number, number] {
  // O LTX gera em meia resolução e exige saída múltipla de 64. Em 1080p,
  // 1088 é o bloco mais próximo; truncar pela regra geral cairia para 1024.
  const menor = res.toLowerCase() === '1080p' && mult === 64
    ? 1088
    : (ALTURA_P[res.toLowerCase()] ?? 720)
  const [a, b] = prop.split(':').map(Number)
  const [larg, alt] = a >= b ? [menor * (a / b), menor] : [menor, menor * (b / a)]
  // TRUNCA, como o backend e como o modelo. Arredondar daria 736 onde a saida
  // tem 704 — e round(22.5) ainda difere entre JS (23) e Python (22), o que
  // faria a tela e o servidor discordarem.
  const ajusta = (v: number) => Math.max(mult, Math.floor(v / mult) * mult)
  return [ajusta(larg), ajusta(alt)]
}

// Mesma conta do backend (presets.alvo_de_ampliacao). Duplicada de
// proposito: o usuario precisa ver o alvo ANTES de clicar, e uma ida ao
// servidor a cada clique numa miniatura seria pior. O backend continua
// mandando, porque a tela nao decide nada sozinha.
/* Multiplo de 32, e PARA CIMA — o mesmo que o backend faz, porque e o que o
   no faz. Com 8 e para baixo a tela prometia 2560x1456 e o arquivo saia
   2560x1472. O alinhamento vem do backend para a regra nao viver em dois
   lugares com dois valores. */
function alvo(l: number, a: number, teto: number, k: number): [number, number] | null {
  if (!l || !a) return null
  if (Math.max(l, a) >= teto) return null // ja no limite: sem ganho
  const [dl, da] = [l * 2, a * 2]
  if (Math.max(dl, da) <= teto) {
    // Alinhar aqui tambem: dobrar 794 da 1588, que nao e multiplo de 32, e o
    // no arredondaria para 1600. So nao alinha se isso estourasse o teto.
    const subiu: [number, number] = [Math.ceil(dl / k) * k, Math.ceil(da / k) * k]
    return Math.max(...subiu) <= teto ? subiu : [dl, da]
  }
  const f = teto / Math.max(dl, da)
  return [Math.ceil(Math.trunc(dl * f) / k) * k, Math.ceil(Math.trunc(da * f) / k) * k]
}

type Props = {
  reuso?: ItemGaleria
  fluxoInicial?: string
  cfg: ModeloVideo | undefined
  /** Metodos de ampliacao; vazio enquanto a lista nao chegou. */
  ampliar:
    | {
        metodos: MetodoAmpliar[]
        maior_lado: number
        alinhamento_temporal?: number
        alinhamento_espacial?: number
      }
    | undefined
  /** LTX 2.5 Creative Lab; null quando o segundo motor nao esta instalado. */
  transformar: {
        id: string
        segundos_por_segundo: number
        max_segundos: number
        efeitos: { id: string; rotulo: string; nota: string; nuvem?: boolean; imagem_estilo?: boolean; quadros_chave?: boolean; max_segundos?: number; rotulo_imagem?: string | null; controles?: { id: string; rotulo: string }[]; imagem_opcional?: boolean; mapa_pronto?: boolean; formatos?: string[] }[]
      } | null
  galeria: ItemGaleria[]
  ocupado: boolean
  motorVivo: boolean
  aoErro: (e: string) => void
}

export default function PainelVideo({
  cfg, ampliar, transformar, galeria, ocupado, motorVivo, aoErro, reuso, fluxoInicial,
}: Props) {
  // App remonta o painel a cada reuso, inclusive ao repetir o mesmo item.
  // Assim os controles e as referencias anteriores nao vazam para o pedido.
  const p = reuso?.parametros ?? {}
  const texto = (k: string, padrao: string) => typeof p[k] === 'string' ? p[k] as string : padrao
  const numero = (k: string, padrao: number) => typeof p[k] === 'number' ? p[k] as number : padrao
  const booleano = (k: string, padrao: boolean) => typeof p[k] === 'boolean' ? p[k] as boolean : padrao
  const lista = (k: string): string[] => Array.isArray(p[k])
    ? (p[k] as unknown[]).filter((v): v is string => typeof v === 'string') : []
  const referencia = (nome: string): Referencia => ({ nome, url: urlEntrada(nome) })
  const preservarReusoInicial = useRef<string | null>(reuso ? texto('modelo_video', 'ltx') : null)

  // Duas tarefas diferentes na mesma aba: CRIAR um video e AMPLIAR um que
  // ja existe. Sao fluxos distintos — criar parte de texto ou foto,
  // ampliar parte de um video da galeria — entao a escolha vem antes de
  // tudo, e cada um mostra so os seus controles.
  const [tarefa, setTarefa] = useState<'criar' | 'ampliar' | 'transformar'>(() =>
    fluxoInicial === 'ampliar' ? 'ampliar' : fluxoInicial === 'profundidade' ? 'transformar' : 'criar')
  const [efeito, setEfeito] = useState(fluxoInicial === 'profundidade' ? 'profundidade' : 'noite')
  const maxSegEfeito = transformar?.efeitos.find((f) => f.id === efeito)?.max_segundos ?? transformar?.max_segundos ?? 8
  const [velocidade, setVelocidade] = useState(1)
  const [textoEfeito, setTextoEfeito] = useState('')
  const [seedTransf, setSeedTransf] = useState('')
  const [controleTroca, setControleTroca] = useState('pose')
  const [mapaPronto, setMapaPronto] = useState(fluxoInicial === 'profundidade')
  const [formatoSaida, setFormatoSaida] = useState('16:9')
  // Video enviado do computador (ex.: animacao do Blender), em vez da galeria.
  const [videoEnviado, setVideoEnviado] = useState<{ nome: string; rotulo: string } | null>(null)
  const [estilo, setEstilo] = useState<{ nome: string; rotulo: string } | null>(null)
  // Quadros-chave da maquete, cada um com o momento (s) em que entra.
  const [chaves, setChaves] = useState<{ id: number; img: { nome: string; rotulo: string } | null; quadro: number }[]>([])
  const proximoIdChave = useRef(1)
  // Sempre pela ordem do video; a ordem na tela nao muda o resultado.
  const ordenarChaves = () => setChaves((a) => [...a].sort((x, y) => x.quadro - y.quadro))
  const [enviandoTransf, setEnviandoTransf] = useState(false)
  const enviarParaTransformar = async (f: File, alvo: 'video') => {
    setEnviandoTransf(true); aoErro('')
    try {
      const r = await api.enviarReferencia(f)
      if (alvo === 'video') { setVideoEnviado({ nome: r.nome, rotulo: f.name }); setVideoEscolhido(null) }
    } catch (e) { aoErro(String(e)) } finally { setEnviandoTransf(false) }
  }
  // Nao fixa mais 'ltx' aqui: o padrao e do backend, que hoje manda
  // 'seedvr'. Fixar na tela fazia a escolha divergir do que o backend
  // considera a melhor primeira opcao.
  const [metodoAmpliar, setMetodoAmpliar] = useState(fluxoInicial === 'ampliar' ? 'ltx' : 'seedvr')
  const [verPerda, setVerPerda] = useState(false)
  const [videoEscolhido, setVideoEscolhido] = useState<ItemGaleria | null>(null)
  // Ampliar: video enviado do computador vira um item "de mentira", com as
  // medidas lidas pelo navegador; a subpasta marca a origem. O fps real o
  // backend mede no arquivo.
  const [enviandoAmpliar, setEnviandoAmpliar] = useState(false)
  const refDoVideo = (v: ItemGaleria) =>
    v.subpasta === 'entrada:' ? `entrada:${v.arquivo}` : `${v.subpasta}/${v.arquivo}`
  const enviarParaAmpliar = async (f: File) => {
    setEnviandoAmpliar(true); aoErro('')
    try {
      const r = await api.enviarReferencia(f)
      const medidas = await new Promise<{ l: number; a: number; d: number }>((ok, falha) => {
        const v = document.createElement('video')
        v.preload = 'metadata'
        v.onloadedmetadata = () => ok({ l: v.videoWidth, a: v.videoHeight, d: v.duration })
        v.onerror = () => falha(new Error('o navegador não conseguiu ler esse vídeo'))
        v.src = urlEntrada(r.nome)
      })
      setVideoEscolhido({
        id: -1, criada_em: Date.now() / 1000, modelo: 'enviado', prompt: '', prompt_final: '',
        arquivo: r.nome, subpasta: 'entrada:', parametros: {}, caption: null,
        largura: medidas.l, altura: medidas.a, duracao: 0, bytes: f.size,
        duracao_video: medidas.d, rotulo: f.name,
      } as ItemGaleria)
    } catch (e) { aoErro(String(e)) } finally { setEnviandoAmpliar(false) }
  }
  /* Videos de referencia vem da GALERIA, nao de upload: o carregador le
     do disco por caminho. Guardamos "subpasta/arquivo", que e o que o
     backend resolve. */
  const [refsVideo, setRefsVideo] = useState<string[]>(() => lista('referencias_video'))
  /* Um texto por plano. Comeca com dois vazios porque dois e o minimo: uma
     lista de um plano seria o FastH3 normal com passos a mais. */
  const [planos, setPlanos] = useState<string[]>(() => lista('planos').length ? lista('planos') : ['', ''])
  const [refsAudio, setRefsAudio] = useState<{ nome: string; rotulo: string }[]>(() => lista('referencias_audio').map((nome) => ({ nome, rotulo: nome })))
  const [forcaAudioReferencia, setForcaAudioReferencia] = useState(() => numero('forca_audio_referencia', 3))
  const [tamanhoReferencia, setTamanhoReferencia] = useState(() => texto('tamanho_referencia', 'match'))
  const [enviandoAudio, setEnviandoAudio] = useState(false)
  /* O quinto slot do MSR. Guardamos a Referencia inteira (nome + url)
     para poder mostrar a miniatura, como nas demais. */
  const [fundo, setFundo] = useState<Referencia | null>(() => typeof p.fundo_referencia === 'string' && p.fundo_referencia ? referencia(p.fundo_referencia) : null)
  const [enviandoFundo, setEnviandoFundo] = useState(false)
  const [gerador, setGerador] = useState(() => texto('modelo_video', 'ltx'))
  const [turbo, setTurbo] = useState(() => booleano('turbo', true))
  const [proporcao, setProporcao] = useState(() => texto('proporcao_video', '16:9'))
  const [resolucaoNuvem, setResolucaoNuvem] = useState(() => texto('resolucao_video', '480p'))
  const [variante, setVariante] = useState(() => texto('variante_video', 'wan3.0-video'))
  const [melhorarPrompt, setMelhorarPrompt] = useState(() => booleano('melhorar_prompt', true))
  const [modo, setModo] = useState(() => texto('modo_video', fluxoInicial === 'ingredientes' || fluxoInicial === 'chaves' ? fluxoInicial : 'imagem'))
  const [prompt, setPrompt] = useState(reuso?.prompt ?? '')
  const [duracao, setDuracao] = useState(() => numero('duracao_video', 5))
  const [comAudio, setComAudio] = useState(() => booleano('com_audio', true))
  const [promptAuto, setPromptAuto] = useState(() => booleano('prompt_automatico', false))
  const [seed, setSeed] = useState(() => p.seed == null ? '' : String(p.seed))
  const [refs, setRefs] = useState<Referencia[]>(() => lista('referencias_usadas').map(referencia))
  const [enviando, setEnviando] = useState(false)
  const entrada = useRef<HTMLInputElement>(null)
  // Entrada de arquivo propria: a do fundo nao pode compartilhar a das
  // referencias, senao escolher uma abriria o seletor da outra.
  const entradaFundo = useRef<HTMLInputElement>(null)
  const entradaAudio = useRef<HTMLInputElement>(null)

  const ger = cfg?.geradores.find((g) => g.id === gerador) ?? cfg?.geradores[0]

  // Cada gerador tem as SUAS duracoes e tamanhos — o MiniMax alinha os quadros
  // de 17 em 17 e nao aceita os mesmos valores do LTX. Trocar de modelo sem
  // reajustar deixaria a tela pedindo algo que o backend ia ignorar em
  // silencio.
  useEffect(() => {
    if (!ger) return
    // Tambem preserva os valores se React repetir o efeito em StrictMode.
    if (preservarReusoInicial.current === ger.id) return
    preservarReusoInicial.current = null
    // Prende na faixa do modelo novo: 15 s escolhidos no Wan nao existem no
    // MiniMax local, que para em 8.
    setDuracao((d) => Math.min(ger.duracao_max, Math.max(ger.duracao_min, d)))
    if (ger.proporcao_padrao) setProporcao(ger.proporcao_padrao)
    if (ger.resolucao_padrao) setResolucaoNuvem(ger.resolucao_padrao)
    if (ger.variante_padrao) setVariante(ger.variante_padrao)
    if (ger.forca_audio_referencia_padrao != null) {
      setForcaAudioReferencia(ger.forca_audio_referencia_padrao)
    }
    // O gerador pode nao fazer o modo escolhido: o Wan nao faz texto puro.
    // Trocar para o primeiro que ele faz e melhor que deixar a tela pedindo
    // algo que voltaria como erro.
    if (ger.modos && !ger.modos.includes(modo)) setModo(ger.modos[0])
  }, [ger])

  const modoAtual = cfg?.modos.find((m) => m.id === modo)
  const precisa = modoAtual?.imagens ?? 0
  // Teto de imagens. O gerador manda o seu (4 no LTX, 9 no MiniMax, 10 no
  // Wan); sem isso, cabe o mesmo que se exige.
  // Nos quadros-chave o teto e do modo (8), nao das referencias do gerador.
  const cabeAte = modo === 'chaves' ? (modoAtual?.imagens_max ?? 8) : Math.min(
    modoAtual?.imagens_max ?? precisa,
    ger?.max_referencias ?? modoAtual?.imagens_max ?? precisa,
  )
  const porChaves = modo === 'chaves'
  useEffect(() => {
    if (porChaves) setDuracao((d) => Math.min(d, 15))
  }, [porChaves])
  // Numero do quadro (de 1) de cada imagem, pelo nome; sem numero, espalha.
  const [quadroDe, setQuadroDe] = useState<Record<string, number>>({})
  const [forcaChaves, setForcaChaves] = useState(0.7)
  const ultimoQuadro = Math.min(361, Math.floor(Math.max(duracao * 24, 8) / 8) * 8 + 1)
  const quadroDaRef = (nome: string, i: number) =>
    quadroDe[nome] ?? 1 + Math.round(i * (ultimoQuadro - 1) / Math.max(1, refs.length - 1))
  const porReferencia = modo === 'referencia'
  // Capacidade declarada, nao id. Ver o comentario em api.ts.
  const encadeia = (ger?.max_planos ?? 0) > 0
  const minPlanos = ger?.min_planos ?? 2
  const maxPlanos = ger?.max_planos ?? 0
  const planosPreenchidos = planos.filter((t) => t.trim()).length
  const lentaDisponivel = !!ger?.camera_lenta && (ger.modos_camera_lenta ?? []).includes(modo)
  const audioDeIdentidade = (ger?.max_audios_identidade ?? 0) > 0
  const audioDeTrilha = (ger?.max_audios_trilha ?? 0) > 0
  const tetoAudio = audioDeTrilha
    ? (ger?.max_audios_trilha ?? 0)
    : audioDeIdentidade
      ? (ger?.max_audios_identidade ?? 0)
      : (porReferencia ? (ger?.max_audios_referencia ?? 0) : 0)
  // No Hailuo a lista de resolucoes depende da variante escolhida; nos demais
  // e uma so. Sem isto a tela ofereceria 2K na variante que nao faz 2K, e o
  // backend trocaria por outra em silencio.
  const resolucoes =
    ger?.resolucoes_por_variante?.[variante] ?? ger?.resolucoes ?? []
  // Trocar de variante pode tirar do ar a resolucao escolhida (2K so existe
  // na Padrao). Sem isto o pedido sairia com uma que o no nao aceita.
  useEffect(() => {
    if (resolucoes.length && !resolucoes.includes(resolucaoNuvem)) {
      setResolucaoNuvem(ger?.resolucao_padrao && resolucoes.includes(ger.resolucao_padrao)
        ? ger.resolucao_padrao
        : resolucoes[0])
    }
  }, [resolucoes.join('|')])
  const naNuvem = !!ger?.nuvem
  // O alinhamento e do GERADOR: o LTX precisa de multiplos de 64 porque
  // gera em meia resolucao; o MiniMax se contenta com 32.
  const alinhamento = ger?.alinhamento ?? 32
  // Preco EXATO, ao contrario do MiniMax por nuvem: aqui e por segundo
  // de video gerado, entao da para calcular antes do clique.
  const custoWan =
    ger?.preco_por_segundo?.[variante]?.[resolucaoNuvem] != null
      ? ger.preco_por_segundo[variante][resolucaoNuvem] * duracao
      : null
  const tarifaMultiRef = ger?.preco_multiref?.[variante]
  const custoMultiRef = (() => {
    if (!tarifaMultiRef) return null
    const porSegundo = tarifaMultiRef.usd_por_segundo?.[resolucaoNuvem]
    if (porSegundo != null) {
      const extras = Math.max(0, refs.length - (tarifaMultiRef.imagens_inclusas ?? 0))
      const valor = duracao * porSegundo
        + extras * (tarifaMultiRef.usd_por_imagem_extra ?? 0)
      return { minimo: valor, maximo: valor }
    }
    const unidadesSegundo = tarifaMultiRef.unidades_por_segundo?.[resolucaoNuvem]
    const maxPorImagem = tarifaMultiRef.tokens_max_por_imagem?.standard
    if (unidadesSegundo == null || maxPorImagem == null) return null
    const base = duracao * unidadesSegundo
    const emUsd = (tokens: number) => {
      const extras = Math.max(0, tokens - (tarifaMultiRef.tokens_gratis ?? 0))
      return (base + extras * (tarifaMultiRef.unidades_por_token_extra ?? 0))
        * (tarifaMultiRef.usd_por_unidade ?? 0)
    }
    return {
      minimo: emUsd(refs.length * (tarifaMultiRef.tokens_min_por_imagem ?? 0)),
      maximo: emUsd(refs.length * maxPorImagem),
    }
  })()

  // Corta o excesso ao trocar para um modo que aceita menos imagens: sem isto
  // a terceira foto ficaria escondida no estado e iria junto no pedido.
  useEffect(() => {
    if (!cfg) return
    setRefs((a) => (a.length > cabeAte ? a.slice(0, cabeAte) : a))
  }, [cabeAte, cfg])
  useEffect(() => {
    if (!cfg) return
    setRefsAudio((a) => (a.length > tetoAudio ? a.slice(0, tetoAudio) : a))
  }, [tetoAudio, cfg])

  /* Envio proprio: o fundo entra pelo MESMO caminho das outras imagens,
     e e justamente por isso que ele precisa de campo separado — pelo tipo
     de arquivo nao ha como dizer que esta e a imagem do cenario. */
  const enviarFundo = async (arquivos: FileList | File[]) => {
    const foto = Array.from(arquivos).find((f) => f.type.startsWith('image/'))
    if (!foto) return
    setEnviandoFundo(true)
    try {
      setFundo(await api.enviarReferencia(foto))
    } catch (e) {
      aoErro(String(e))
    } finally {
      setEnviandoFundo(false)
    }
  }

  const enviar = async (arquivos: FileList | File[]) => {
    const fotos = Array.from(arquivos).filter((f) => f.type.startsWith('image/'))
    const cabem = fotos.slice(0, Math.max(0, cabeAte - refs.length))
    if (!cabem.length) return
    setEnviando(true)
    try {
      const novas = await Promise.all(cabem.map((f) => api.enviarReferencia(f)))
      setRefs((a) => [...a, ...novas])
    } catch (e) {
      aoErro(String(e))
    } finally {
      setEnviando(false)
    }
  }

  const enviarAudio = async (arquivos: FileList | File[]) => {
    const audios = Array.from(arquivos).filter((f) =>
      f.type.startsWith('audio/') || /\.(wav|mp3|flac|m4a|ogg)$/i.test(f.name))
    const cabem = audios.slice(0, Math.max(0, tetoAudio - refsAudio.length))
    if (!cabem.length) return
    setEnviandoAudio(true)
    try {
      const novos = await Promise.all(cabem.map(async (arquivo) => ({
        ...(await api.enviarAudio(arquivo)), rotulo: arquivo.name,
      })))
      setRefsAudio((atuais) => [...atuais, ...novos])
    } catch (e) {
      aoErro(String(e))
    } finally {
      setEnviandoAudio(false)
    }
  }

  const gerar = async () => {
    try {
      await api.gerar({
        modelo: 'video',
        modo_video: modo,
        prompt,
        proporcao: '1:1', // ignorado no video; o tamanho manda
        modelo_video: gerador,
        turbo,
        proporcao_video: proporcao,
        resolucao_video: resolucaoNuvem,
        variante_video: variante,
        melhorar_prompt: melhorarPrompt,
        duracao_video: duracao,
        com_audio: comAudio,
        velocidade_video: lentaDisponivel ? velocidade : 1,
        prompt_automatico: promptAuto,
        seed: seed.trim() === '' ? null : Number(seed),
        referencias: refs.map((r) => r.nome),
        ...(modo === 'chaves' ? {
          quadros_referencias: refs.map((r, i) => quadroDaRef(r.nome, i)),
          forca_chaves: forcaChaves,
        } : {}),
        referencias_video: refsVideo,
        planos: encadeia ? planos.map((t) => t.trim()).filter(Boolean) : [],
        referencias_audio: comAudio ? refsAudio.map((r) => r.nome) : [],
        forca_audio_referencia: forcaAudioReferencia,
        tamanho_referencia: tamanhoReferencia,
        fundo_referencia: fundo?.nome ?? null,
      })
    } catch (e) {
      aoErro(String(e))
    }
  }

  // So video pode ser ampliado, e a duracao gravada e o que distingue um
  // video de uma imagem na galeria.
  const videos = galeria.filter((g) => !!g.duracao_video)

  const ampliarVideo = async () => {
    if (!videoEscolhido) return
    aoErro('')
    try {
      await api.gerar({
        modelo: 'limpar_video',
        prompt: prompt.trim(),
        proporcao: '1:1',
        metodo_video: metodoAmpliar,
        // So o SeedVR2 usa isto; o LTX tira o alvo das dimensoes do arquivo.
        resolucao_limpeza: Math.min(2160, Math.round((videoEscolhido.altura || 720) * 2)),
        referencias: [refDoVideo(videoEscolhido)],
      })
    } catch (e) {
      aoErro(String(e))
    }
  }

  if (!cfg) return <p className="dica">Carregando…</p>

  // No ref2va a referencia pode ser imagem, video OU audio. A regra antiga
  // exigia uma imagem e deixava o novo upload de audio incapaz de liberar o
  // botao, embora o backend e o no aceitassem audio sozinho.
  const aceitaReferenciaAlternativa = porReferencia &&
    ((ger?.max_videos_referencia ?? 0) > 0 || (ger?.max_audios_referencia ?? 0) > 0)
  const faltamImagens = aceitaReferenciaAlternativa
    ? refs.length + refsVideo.length + refsAudio.length < 1
    : refs.length < precisa
  // O texto so e obrigatorio quando nao ha imagem de onde tirar a descricao.
  // No encadeado o texto nunca e opcional: cada plano PRECISA do seu, senao
  // nao ha o que distinguir um trecho do seguinte.
  const faltaTexto = encadeia
    ? planosPreenchidos < minPlanos
    : modo === 'texto' && !prompt.trim()
  /* O tempo NAO cresce linear com a duracao: a atencao custa mais que o
     dobro quando o clipe dobra. Medido, para 15 s no maior tamanho:

       FastH3 ......... linear previa 363 s, real 483 s   (k = 1,14)
       MiniMax turbo .. linear previa 627 s, real 1388 s  (k = 1,60)

     O MiniMax prometia 10 minutos num trabalho de 23. Sem expoente medido a
     conta segue linear, como era antes — 1 nao piora nada. */
  const k = ger?.expoente_duracao ?? 1
  // A orientação por áudio faz uma passada adicional sem referência para
  // aplicar o guidance. Em teste controlado, isso acrescentou cerca de 34%.
  const fatorReferenciaVocal = audioDeIdentidade && refsAudio.length > 0 ? 1.34 : 1
  // No encadeado a estimativa do gerador e POR PLANO, e o trabalho e a soma:
  // o modelo carrega uma vez, mas amostra uma vez por plano. Sem isto a tela
  // prometeria o tempo de um plano para um trabalho de quatro.
  const quantosPlanos = encadeia ? Math.max(planosPreenchidos, minPlanos) : 1
  const segundos = Math.round(
    (ger?.segundos_estimados ?? 130) * Math.pow(duracao / 5, k)
    * fatorReferenciaVocal * quantosPlanos)

  const metodoAtualAmpliar = ampliar?.metodos.find((m) => m.id === metodoAmpliar)
  /* O latente do LTX so representa 8k+1 quadros e trunca o resto — medido
     em tres clipes: 121 sai inteiro (ja e 8x15+1), 124 vira 121, 192 vira 185.
     A constante vem do backend para a regra nao viver em dois lugares. */
  const alinhamentoTemporal = ampliar?.alinhamento_temporal ?? 8
  const quadrosDoVideo = videoEscolhido
    ? Math.round((videoEscolhido.duracao_video ?? 0) * (videoEscolhido.fps ?? 24))
    : 0
  const quadrosQueSobram =
    quadrosDoVideo > 0
      ? Math.floor((quadrosDoVideo - 1) / alinhamentoTemporal) * alinhamentoTemporal + 1
      : 0
  const perdeQuadros = metodoAmpliar === 'ltx' && quadrosQueSobram < quadrosDoVideo

  // Suavizar movimento nao amplia: o alvo e o proprio tamanho do video.
  const alvoAmpliacao =
    videoEscolhido && ampliar && metodoAmpliar === 'rtx48'
      ? ([videoEscolhido.largura, videoEscolhido.altura] as [number, number])
      : videoEscolhido && ampliar
      ? alvo(videoEscolhido.largura, videoEscolhido.altura, ampliar.maior_lado,
             ampliar.alinhamento_espacial ?? 32)
      : null

  return (
    <>
      <div className="abas-internas">
        <button data-ativo={tarefa === 'criar'} onClick={() => setTarefa('criar')}>
          Criar
        </button>
        <button data-ativo={tarefa === 'ampliar'} onClick={() => setTarefa('ampliar')}>
          Ampliar
        </button>
        {transformar && (
          <button data-ativo={tarefa === 'transformar'} onClick={() => setTarefa('transformar')}>
            Transformar
          </button>
        )}
      </div>

      {tarefa === 'transformar' && transformar ? (
        <>
          <div className="campo">
            <label>
              Qual vídeo
              <span className="opcional"> {videos.length} na galeria</span>
            </label>
            {videos.length === 0 ? (
              <p className="dica">Nenhum vídeo ainda. Gere um na aba Criar.</p>
            ) : (
              <div className="galeria-tiras" style={{ maxHeight: 76, overflowY: 'auto' }}>
                {videos.map((v) => (
                  <button
                    key={v.id}
                    className="miniatura"
                    data-ativo={videoEscolhido?.id === v.id}
                    style={{ width: 62, height: 62 }}
                    title={`${v.largura}×${v.altura} · ${v.duracao_video?.toFixed(1)}s`}
                    onClick={() => { setVideoEscolhido(v); setVideoEnviado(null) }}
                  >
                    <img src={urlMiniatura({ nome: v.arquivo, subpasta: v.subpasta })} loading="lazy" alt="" />
                  </button>
                ))}
              </div>
            )}
            <AreaSolta
              rotulo={enviandoTransf ? 'Enviando…' : videoEnviado
                ? `Do computador: ${videoEnviado.rotulo} — arraste outro para trocar`
                : 'Ou arraste um vídeo aqui, ou clique para escolher'}
              aceita="video/*"
              desativada={enviandoTransf}
              aoEscolher={(f) => enviarParaTransformar(f, 'video')}
            />
            {(videoEnviado || videoEscolhido) && (
              <PlayerQuadros
                key={videoEnviado?.nome ?? videoEscolhido?.arquivo}
                src={videoEnviado ? urlEntrada(videoEnviado.nome)
                  : urlImagem({ nome: videoEscolhido!.arquivo, subpasta: videoEscolhido!.subpasta })}
                maxQuadros={Math.round(maxSegEfeito * 24) + 1}
                aoCapturar={transformar.efeitos.find((f) => f.id === efeito)?.quadros_chave
                  ? async (n) => {
                      aoErro('')
                      try {
                        await api.gerar({
                          modelo: 'quadros_maquete', prompt: '', proporcao: '1:1', quadros_extrair: [n],
                          referencias: [videoEnviado ? `entrada:${videoEnviado.nome}`
                            : `${videoEscolhido!.subpasta}/${videoEscolhido!.arquivo}`],
                        })
                        setChaves((a) => a.some((c) => c.quadro === n) ? a
                          : [...a, { id: proximoIdChave.current++, img: null, quadro: n }].sort((x, y) => x.quadro - y.quadro))
                      } catch (e) { aoErro(String(e)) }
                    }
                  : undefined}
              />
            )}
            {videoEscolhido && (videoEscolhido.duracao_video ?? 0) > maxSegEfeito && (
              <p className="dica alerta">
                Só os primeiros {maxSegEfeito} s serão transformados.
              </p>
            )}
          </div>

          <div className="campo">
            <label>
              Efeito
              <Ajuda titulo="Sobre os efeitos">
                LoRAs do LTX 2.5 Creative Lab, da Lightricks. Saem com o lado menor
                em 544 px (o tamanho em que foram treinados) e com o áudio original.
                Para mais resolução, amplie depois com o RTX.
              </Ajuda>
            </label>
            <select value={efeito} onChange={(e) => setEfeito(e.target.value)}>
              {transformar.efeitos.map((f) => (
                <option key={f.id} value={f.id} disabled={f.nuvem === false}>
                  {f.rotulo}{f.nuvem === false ? ' (só local)' : ''}
                </option>
              ))}
            </select>
            <p className="dica" style={{ margin: '8px 2px 4px' }}>{transformar.efeitos.find((f) => f.id === efeito)?.nota}</p>
          </div>

          {transformar.efeitos.find((f) => f.id === efeito)?.imagem_estilo && (
            <EscolhaImagem
              titulo={transformar.efeitos.find((f) => f.id === efeito)?.rotulo_imagem ?? 'Imagem de estilo'}
              ajuda={transformar.efeitos.find((f) => f.id === efeito)?.controles?.length
                ? 'O quadro 1 do vídeo, com o personagem já trocado. Faça no Flux 3 com referências: o quadro 1 (use "Capturar quadro" no player) como @imagem1 e a foto do personagem como @imagem2, pedindo a mesma pose e o mesmo enquadramento.'
                : 'Diz como a cena deve ficar: materiais, luz, cores. O movimento e a câmera vêm do vídeo; a aparência vem desta imagem. Faça a partir do PRIMEIRO quadro da maquete.'}
              valor={estilo} aoMudar={setEstilo} galeria={galeria} aoErro={aoErro}
            />
          )}

          {(transformar.efeitos.find((f) => f.id === efeito)?.controles?.length ?? 0) > 1 && (
            <div className="campo">
              <label>
                O que manter do vídeo original
                <Ajuda titulo="Qual escolher">
                  Pose: só o esqueleto do movimento (corpo, mãos e rosto); o melhor
                  para trocar a pessoa, porque não carrega o formato do corpo, da
                  roupa e do cabelo antigos. Profundidade: guarda a silhueta e o
                  volume. Contornos: guarda as linhas e bordas, inclusive de roupa
                  e cabelo do original.
                </Ajuda>
              </label>
              <div className="opcoes segmentado">
                {transformar.efeitos.find((f) => f.id === efeito)!.controles!.map((c) => (
                  <button key={c.id} data-ativo={controleTroca === c.id} onClick={() => setControleTroca(c.id)}>
                    {c.rotulo}
                  </button>
                ))}
              </div>
            </div>
          )}

          {(transformar.efeitos.find((f) => f.id === efeito)?.formatos?.length ?? 0) > 0 && (
            <div className="campo">
              <label>Formato do vídeo final</label>
              <div className="opcoes segmentado">
                {transformar.efeitos.find((f) => f.id === efeito)!.formatos!.map((f) => (
                  <button key={f} data-ativo={formatoSaida === f} onClick={() => setFormatoSaida(f)}>{f}</button>
                ))}
              </div>
            </div>
          )}

          {transformar.efeitos.find((f) => f.id === efeito)?.mapa_pronto && (
            <label className="alternador">
              <input type="checkbox" checked={mapaPronto} onChange={(e) => setMapaPronto(e.target.checked)} />
              <span>
                O vídeo já é um mapa de profundidade
                <Ajuda titulo="Quando marcar">
                  Marque se o vídeo for o passe de profundidade (Z) exportado do
                  Blender ou de outro programa 3D: o app usa os quadros direto, sem
                  estimar. Mais preciso que a estimativa. Convenção esperada: perto
                  claro, longe escuro.
                </Ajuda>
              </span>
            </label>
          )}

          {transformar.efeitos.find((f) => f.id === efeito)?.quadros_chave && (
            <>
              <div className="campo">
                <label>
                  Quadros-chave
                  <span className="opcional"> opcional</span>
                  <Ajuda titulo="Quando usar">
                    Para o personagem ou o objeto se manterem quando a câmera mostra
                    um ângulo novo (a lateral, a frente, de cima). Pare o player no
                    quadro, use "Capturar quadro", transforme a imagem no Flux 3 com
                    referências (o quadro cinza + a foto do personagem) e traga para
                    cá com o número do quadro (24 quadros = 1 s, contando do 1, como
                    no Blender). O modelo só aceita múltiplos de 8: o número é levado
                    ao mais próximo (1 → início, 48, 80…). Use poucos, onde o ângulo muda.
                  </Ajuda>
                </label>
              </div>
              {chaves.map((c) => {
                const mudar = (m: Partial<typeof c>) => setChaves((a) => a.map((x) => x.id === c.id ? { ...x, ...m } : x))
                const q = Math.round((c.quadro - 1) / 8) * 8
                return (
                  <div key={c.id}>
                    <div className="cartao-chave">
                      {c.img && <img src={urlEntrada(c.img.nome)} alt="" />}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                          <label style={{ margin: 0 }}>Quadro nº</label>
                          <input type="number" min={1} max={Math.round(maxSegEfeito * 24) + 1} step={1}
                            value={c.quadro} style={{ width: 72 }}
                            onChange={(e) => mudar({ quadro: Math.max(1, Math.round(Number(e.target.value))) })}
                            onBlur={ordenarChaves} />
                        </div>
                        <span className="opcional">
                          entra no {q + 1} · {(q / 24).toFixed(2).replace('.', ',')} s
                          {!c.img && ' · falta a imagem'}
                        </span>
                      </div>
                      {c.img && <button className="mini" title="Escolher outra imagem" onClick={() => mudar({ img: null })}>trocar</button>}
                      <button className="mini" title="Tirar este quadro-chave"
                        onClick={() => setChaves((a) => a.filter((x) => x.id !== c.id))}>×</button>
                    </div>
                    {!c.img && (
                      <EscolhaImagem titulo={`Imagem do quadro ${q + 1}`} valor={null}
                        aoMudar={(v) => mudar({ img: v })} galeria={galeria} aoErro={aoErro} />
                    )}
                  </div>
                )
              })}
              <button className="mini" onClick={() => setChaves((a) => [...a, { id: proximoIdChave.current++, img: null, quadro: 1 }])}>
                + Acrescentar quadro-chave
              </button>
            </>
          )}

          <div className="campo">
            <label>
              Descrição
              <span className="opcional"> opcional</span>
            </label>
            <textarea
              value={textoEfeito}
              onChange={(e) => setTextoEfeito(e.target.value)}
              placeholder="O que deve aparecer no resultado (em inglês funciona melhor)"
            />
          </div>

          <div className="campo">
            <label>
              Seed
              <span className="opcional"> opcional</span>
              <Ajuda titulo="Para que serve">
                Com a mesma seed, as mesmas entradas e o mesmo texto, o resultado se
                repete. Gostou de um vídeo mas quer corrigir um trecho? Copie a seed
                dele no painel Informações da galeria, cole aqui e mude só os
                quadros-chave. Em branco, sorteia uma nova a cada geração.
              </Ajuda>
            </label>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                value={seedTransf}
                inputMode="numeric"
                onChange={(e) => setSeedTransf(e.target.value.replace(/\D/g, ''))}
                placeholder="aleatória"
              />
              {seedTransf && <button className="mini" title="Voltar a sortear" onClick={() => setSeedTransf('')}>×</button>}
            </div>
          </div>

          <button
            className="principal"
            style={{ width: '100%' }}
            disabled={!motorVivo || (!videoEscolhido && !videoEnviado)
              || (!!transformar.efeitos.find((f) => f.id === efeito)?.imagem_estilo && !estilo
                  && !transformar.efeitos.find((f) => f.id === efeito)?.imagem_opcional)}
            onClick={async () => {
              if (!videoEscolhido && !videoEnviado) return
              aoErro('')
              const precisaEstilo = !!transformar.efeitos.find((f) => f.id === efeito)?.imagem_estilo
              try {
                await api.gerar({
                  modelo: 'transformar_video',
                  prompt: textoEfeito.trim(),
                  seed: seedTransf ? Number(seedTransf) : null,
                  proporcao: '1:1',
                  efeito_video: efeito,
                  controle_troca: controleTroca,
                  mapa_pronto: mapaPronto,
                  formato_saida: formatoSaida,
                  chaves_video: precisaEstilo
                    ? chaves.filter((c) => c.img).map((c) => ({ imagem: c.img!.nome, quadro: c.quadro }))
                    : [],
                  referencias: [
                    videoEnviado ? `entrada:${videoEnviado.nome}` : `${videoEscolhido!.subpasta}/${videoEscolhido!.arquivo}`,
                    ...(precisaEstilo && estilo ? [estilo.nome] : []),
                  ],
                })
              } catch (e) {
                aoErro(String(e))
              }
            }}
          >
            {ocupado ? 'Adicionar à fila' : 'Transformar'}
            {videoEscolhido && ` · ~${Math.max(1, Math.round(
              Math.min(videoEscolhido.duracao_video ?? 5, maxSegEfeito)
              * transformar.segundos_por_segundo / 60))} min`}
          </button>
          {!videoEscolhido && !videoEnviado && (
            <p className="dica">Escolha um vídeo acima ou envie um do computador.</p>
          )}
        </>
      ) : tarefa === 'ampliar' ? (
        <>
          <div className="campo">
            <label>
              Qual vídeo
              <span className="opcional"> {videos.length} na galeria</span>
            </label>
            {videos.length === 0 ? (
              <p className="dica">
                Nenhum vídeo na galeria. Gere um na aba Criar ou envie abaixo.
              </p>
            ) : (
              <div className="galeria-tiras" style={{ maxHeight: 190, overflowY: 'auto' }}>
                {videos.map((v) => (
                  <button
                    key={v.id}
                    className="miniatura"
                    data-ativo={videoEscolhido?.id === v.id}
                    style={{ width: 62, height: 62 }}
                    title={`${v.largura}×${v.altura} · ${v.duracao_video?.toFixed(1)}s`}
                    onClick={() => setVideoEscolhido(v)}
                  >
                    <img
                      src={urlMiniatura({ nome: v.arquivo, subpasta: v.subpasta })}
                      loading="lazy"
                      alt=""
                    />
                  </button>
                ))}
              </div>
            )}
            <AreaSolta
              rotulo={enviandoAmpliar ? 'Enviando…' : videoEscolhido?.subpasta === 'entrada:'
                ? `Do computador: ${videoEscolhido.rotulo} — arraste outro para trocar`
                : 'Ou arraste um vídeo feito fora daqui, ou clique para escolher'}
              aceita="video/*"
              desativada={enviandoAmpliar}
              aoEscolher={enviarParaAmpliar}
            />
            {videoEscolhido && (
              alvoAmpliacao ? (
                <p className="dica">
                  {videoEscolhido.largura}×{videoEscolhido.altura} →{' '}
                  <strong>
                    {alvoAmpliacao[0]}×{alvoAmpliacao[1]}
                  </strong>
                  {alvoAmpliacao[0] < videoEscolhido.largura * 2 && (
                    <Ajuda titulo="Por que não o dobro">
                      O dobro daria {videoEscolhido.largura * 2}×
                      {videoEscolhido.altura * 2}, acima do que a placa aguenta.
                      O alvo encolhe proporcionalmente em vez de estourar no meio
                      da rodada.
                    </Ajuda>
                  )}
                  {perdeQuadros && (
                    <>
                      {' · '}
                      <strong>{quadrosQueSobram}</strong> dos {quadrosDoVideo} quadros
                      <Ajuda titulo="Por que o vídeo encurta">
                        O latente do LTX guarda os quadros em blocos e só
                        representa <strong>8k+1</strong> deles: {quadrosDoVideo} não
                        é um desses números, então sobram {quadrosQueSobram} — o
                        clipe fica{' '}
                        {(((quadrosDoVideo - quadrosQueSobram) /
                           (videoEscolhido.fps ?? 24))).toFixed(2)} s mais curto.
                        Não é defeito a consertar, é aritmética do modelo. O
                        método <strong>em pixels</strong> não passa por esse
                        latente.
                      </Ajuda>
                    </>
                  )}
                </p>
              ) : (
                <p className="dica alerta">
                  Este vídeo já tem {videoEscolhido.largura}×{videoEscolhido.altura},
                  no limite do que a placa aguenta. Ampliar não traria ganho.
                </p>
              )
            )}
          </div>

          <div className="campo">
            <label>
              Método
              {metodoAtualAmpliar && (
                <Ajuda titulo="Sobre os métodos">{metodoAtualAmpliar.nota}</Ajuda>
              )}
            </label>
            <div className="opcoes segmentado">
              {(ampliar?.metodos ?? []).map((m) => (
                <button
                  key={m.id}
                  data-ativo={metodoAmpliar === m.id}
                  onClick={() => setMetodoAmpliar(m.id)}
                >
                  {m.rotulo} · ~{m.segundos < 60 ? `${m.segundos} s` : `${Math.round(m.segundos / 60)} min`}
                </button>
              ))}
            </div>
          </div>

          {/* So o metodo no latente destroi o que e pequeno no quadro, entao
              a previa so faz sentido com ele escolhido — e so quando ja ha um
              video para conferir. */}
          {metodoAmpliar === 'ltx' && videoEscolhido && (
            verPerda ? (
              <PreviaLatente
                referencia={refDoVideo(videoEscolhido)}
                aoFechar={() => setVerPerda(false)}
              />
            ) : (
              <button className="mini" onClick={() => setVerPerda(true)}>
                Ver o que o latente perde
              </button>
            )
          )}

          <div className="campo">
            <label>
              Descrição da cena
              <span className="opcional"> opcional</span>
              <Ajuda titulo="Para que serve">
                Só o método <strong>no latente</strong> usa isto: uma frase curta
                sobre a cena dá âncora ao refino. Sem ela o modelo melhora no
                vazio e inventa mais. O método em pixels ignora o texto.
              </Ajuda>
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Uma oficina de marcenaria, luz quente de tarde"
            />
          </div>

          <button
            className="principal"
            style={{ width: '100%' }}
            onClick={ampliarVideo}
            disabled={!motorVivo || !videoEscolhido || !alvoAmpliacao}
          >
            {ocupado ? 'Adicionar à fila' : 'Ampliar'}
            {metodoAtualAmpliar && ` · ~${metodoAtualAmpliar.segundos < 60 ? `${metodoAtualAmpliar.segundos} s` : `${Math.round(metodoAtualAmpliar.segundos / 60)} min`}`}
          </button>
          {!videoEscolhido && videos.length > 0 && (
            <p className="dica">Escolha um vídeo acima.</p>
          )}
        </>
      ) : (
        <>
      {/* O MODELO vem antes do modo: ele muda as durações, os tamanhos e a
          existência da chave turbo. E é caixa SUSPENSA, não botões lado a
          lado: com quatro geradores e descrições, a fila de botões ocupava
          três linhas e escondia o que cada um faz. Fechada mostra só o
          escolhido; aberta, todos com descrição e tempo. */}
      <Seletor
        rotulo="Modelo"
        valor={gerador}
        aoEscolher={setGerador}
        grupos={[
          { id: 'local', rotulo: 'Na sua placa (sem custo)' },
          { id: 'nuvem', rotulo: 'Na nuvem (gasta crédito)' },
        ]}
        opcoes={(cfg.geradores ?? []).map((g) => ({
          id: g.id,
          // O rotulo do preset ja traz "(nuvem)"; tirar evita "MiniMax H3
          // (nuvem) nuvem" na linha fechada.
          rotulo: g.rotulo.replace(/\s*\(nuvem\)\s*$/, ''),
          sufixo: g.nuvem ? 'nuvem' : 'local',
          descricao: g.descricao,
          segundos: g.segundos_estimados,
          grupo: g.nuvem ? 'nuvem' : 'local',
        }))}
      />

      {/* Variantes: so o Wan tem. A "prime" custa cerca de 40% mais. */}
      {(ger?.variantes?.length ?? 0) > 1 && (
        <div className="campo">
          <label>
            Variante
            <Ajuda titulo="Padrão ou Prime">
              A <strong>Prime</strong> custa cerca de 40% mais por segundo. Vale
              comparar numa peça curta antes de assumir que compensa.
            </Ajuda>
          </label>
          <div className="opcoes segmentado">
            {(ger?.variantes ?? []).map((x) => (
              <button key={x.id} data-ativo={variante === x.id} onClick={() => setVariante(x.id)}>
                {x.rotulo}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* A chave turbo so existe no MiniMax. Ela alterna DUAS coisas juntas:
          a LoRA entra e os passos caem. */}
      {ger?.turbo && (
        <label className="alternador">
          <input type="checkbox" checked={turbo} onChange={(e) => setTurbo(e.target.checked)} />
          <span>
            Turbo
            <Ajuda titulo="Sobre o turbo">
              Liga a LoRA rápida e baixa de <strong>{ger.turbo.passos_normal}</strong>{' '}
              para <strong>{ger.turbo.passos}</strong> passos. As duas coisas
              andam juntas: a LoRA com muitos passos queima a imagem, e poucos
              passos sem ela saem crus.
            </Ajuda>
          </span>
        </label>
      )}

      {/* Caixa suspensa tambem aqui: os rotulos sao longos ("Primeiro e
          ultimo quadro") e quebravam em duas linhas como botoes. */}
      <Seletor
        rotulo="Como gerar"
        valor={modo}
        aoEscolher={setModo}
        opcoes={cfg.modos
          .filter((m) => !ger?.modos || ger.modos.includes(m.id))
          .map((m) => ({ id: m.id, rotulo: m.rotulo, descricao: m.nota }))}
      />

      {precisa > 0 && (
        <div className="campo">
          <label>
            {porChaves
              ? 'Quadros-chave'
              : porReferencia
              ? 'Referências'
              : precisa === 2
                ? 'Primeiro e último quadro'
                : 'Imagem de partida'}{' '}
            <span className="opcional">
              {refs.length}/{cabeAte}
            </span>
          </label>
          {refs.length > 0 && (
            <div className="refs-nuvem">
              {refs.map((r, i) => (
                <div key={r.nome} className="ref-nuvem">
                  <img src={r.url} alt="" />
                  {precisa === 2 && !porChaves && <span className="ordem">{i === 0 ? '1º' : 'último'}</span>}
                  {porChaves && (
                    <input type="number" className="quadro-ref" min={1} max={ultimoQuadro} step={1}
                      title="Número do quadro (de 1, a 24 por segundo)"
                      value={quadroDaRef(r.nome, i)}
                      onChange={(e) => setQuadroDe((q) => ({ ...q, [r.nome]: Math.max(1, Math.min(ultimoQuadro, Math.round(Number(e.target.value)))) }))} />
                  )}
                  <button
                    className="mini"
                    title="Remover"
                    onClick={() => setRefs((a) => a.filter((_, j) => j !== i))}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          {refs.length < cabeAte && (
            <div
              className="area-solta"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                enviar(e.dataTransfer.files)
              }}
              onClick={() => entrada.current?.click()}
            >
              {enviando
                ? 'Enviando…'
                : precisa === 2 && refs.length === 1
                  ? 'Agora o último quadro'
                  : 'Arraste aqui, ou clique para escolher'}
              <input
                ref={entrada}
                type="file"
                accept="image/*"
                multiple={precisa > 1}
                hidden
                onChange={(e) => {
                  if (e.target.files) enviar(e.target.files)
                  e.target.value = ''
                }}
              />
            </div>
          )}
        </div>
      )}

      {encadeia ? (
      <div className="campo">
        <label>
          Os planos, na ordem
          <Ajuda>
            Cada plano vira um trecho do vídeo, e começa exatamente no último
            quadro do anterior — não há corte de câmera entre eles. Descreva
            cada um como <strong>continuação</strong>, não como cena nova.
            {ger?.segundos_por_plano
              ? ` Cada plano custa cerca de ${ger.segundos_por_plano}s.`
              : ''}
          </Ajuda>
        </label>
        {planos.map((texto, i) => (
          <div key={i} className="linha-plano">
            <textarea
              value={texto}
              onChange={(e) => setPlanos((a) =>
                a.map((t, j) => (j === i ? e.target.value : t)))}
              placeholder={i === 0
                ? 'Como começa — a cena e o que já está acontecendo'
                : 'O que muda a partir daqui'}
            />
            <div className="botoes-plano">
              <b>{i + 1}</b>
              <button
                className="mini"
                disabled={planos.length <= minPlanos}
                onClick={() => setPlanos((a) => a.filter((_, j) => j !== i))}
              >remover</button>
            </div>
          </div>
        ))}
        <button
          className="mini"
          disabled={planos.length >= maxPlanos}
          onClick={() => setPlanos((a) => [...a, ''])}
        >
          {planos.length >= maxPlanos
            ? `máximo de ${maxPlanos} planos`
            : 'acrescentar plano'}
        </button>
      </div>
      ) : (
      <div className="campo">
        <label>
          {modo === 'texto' ? 'Descreva a cena e o movimento' : 'O que deve acontecer'}
          {modo !== 'texto' && <span className="opcional"> opcional</span>}
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={
            modo === 'texto'
              ? 'Uma oficina de marcenaria ao entardecer, a câmera avança devagar'
              : 'A pessoa respira, a poeira flutua na luz'
          }
        />
      </div>
      )}

      {/* No modo de referencia o no automatico nao entra: ele le UMA imagem
          para descrever o movimento, e aqui ha ate quatro sujeitos. Mostrar a
          chave sem liga-la no grafo seria o mesmo defeito que acabamos de
          tirar dos outros geradores. */}
      {ger?.sugere_prompt && precisa > 0 && !porReferencia && (
        <label className="alternador">
          <input
            type="checkbox"
            checked={promptAuto}
            onChange={(e) => setPromptAuto(e.target.checked)}
          />
          <span>
            Sugestão de prompt
            <Ajuda titulo="O que isto faz">
              O modelo olha a imagem e escreve a descrição do movimento por
              você. Útil quando não se sabe o que pedir; atrapalha quando a
              frase já está do jeito que você quer.
            </Ajuda>
          </span>
        </label>
      )}

      {/* O quinto slot do MSR, so para o CENARIO. Separado das quatro
          referencias de propósito: as cinco imagens chegam pelo mesmo caminho,
          entao a unica forma de dizer "esta e o fundo" e o campo ser outro. */}
      {porReferencia && ger?.tem_fundo_referencia && (
        <div className="campo">
          <label>
            Fundo
            <span className="opcional"> opcional</span>
            <Ajuda titulo="O que este slot faz">
              Um quinto lugar, separado dos até quatro sujeitos, só para o
              <strong> cenário</strong>. O modelo trata sujeito e fundo de
              formas diferentes — por isso não adianta pôr o cenário junto das
              outras: ele entraria como mais um personagem.
            </Ajuda>
          </label>
          {fundo ? (
            <div className="refs-nuvem">
              <div className="ref-nuvem">
                <img src={fundo.url} alt="" />
                <button className="mini" title="Remover" onClick={() => setFundo(null)}>
                  ×
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
              {enviandoFundo ? 'Enviando…' : 'A imagem do cenário, se houver'}
              <input
                ref={entradaFundo}
                type="file"
                accept="image/*"
                hidden
                onChange={(e) => e.target.files && enviarFundo(e.target.files)}
              />
            </div>
          )}
        </div>
      )}

      {/* Videos de referencia: so o ref2va aceita, e so faz sentido no modo
          de referencia. Vem da galeria porque o carregador le do disco — por
          isso a lista aqui, e nao a area de arrastar das imagens. */}
      {porReferencia && (ger?.max_videos_referencia ?? 0) > 0 && (
        <div className="campo">
          <label>
            Vídeos de referência
            <span className="opcional">
              {' '}{refsVideo.length}/{ger?.max_videos_referencia} · opcional
            </span>
            <Ajuda titulo="O que muda com vídeo">
              Um vídeo de referência leva a <strong>cena e o movimento</strong>,
              não só a aparência. Medido: o clipe de origem chegou inteiro —
              mesma árvore, mesmo deserto, mesma pose.
              {' '}<strong>Custa cerca de 5× mais:</strong> 482 s contra ~90 s
              das referências por imagem, porque os quadros atravessam o VAE
              antes de virar condicionamento.
            </Ajuda>
          </label>
          {videos.length === 0 ? (
            <p className="dica">Nenhum vídeo na galeria ainda.</p>
          ) : (
            <div className="galeria-tiras" style={{ maxHeight: 140, overflowY: 'auto' }}>
              {videos.map((v) => {
                const chave = `${v.subpasta}/${v.arquivo}`
                const escolhido = refsVideo.includes(chave)
                const cheio = refsVideo.length >= (ger?.max_videos_referencia ?? 0)
                return (
                  <button
                    key={v.id}
                    className="miniatura"
                    data-ativo={escolhido}
                    disabled={!escolhido && cheio}
                    style={{ width: 62, height: 62 }}
                    title={`${v.largura}×${v.altura} · ${v.duracao_video?.toFixed(1)}s`}
                    onClick={() =>
                      setRefsVideo((a) =>
                        a.includes(chave) ? a.filter((x) => x !== chave) : [...a, chave])
                    }
                  >
                    <img
                      src={urlMiniatura({ nome: v.arquivo, subpasta: v.subpasta })}
                      loading="lazy"
                      alt=""
                    />
                  </button>
                )
              })}
            </div>
          )}
        </div>
      )}

      {comAudio && tetoAudio > 0 && (
        <div className="campo">
          <label>
            {audioDeTrilha ? 'Áudio do vídeo' : audioDeIdentidade ? 'Voz de referência' : 'Áudios de referência'}
            <span className="opcional">
              {' '}{refsAudio.length}/{tetoAudio} · opcional
            </span>
            <Ajuda titulo="O que o áudio transfere">
              {audioDeTrilha
                ? <>O arquivo vira o som do vídeo, sem alteração: uma fala faz a
                    pessoa da imagem falar com a boca sincronizada; uma música
                    guia o ritmo. Se o áudio for mais curto que a duração
                    escolhida, o vídeo encolhe para ele. Sem arquivo, o modelo
                    cria o som sozinho.</>
                : audioDeIdentidade
                ? <>O LTX usa a amostra para manter a identidade de quem fala.
                    Prefira cerca de cinco segundos, com uma só voz e pouco
                    ruído. O texto ainda precisa pedir fala no vídeo.</>
                : <>O MiniMax usa voz, ritmo e ambiente sonoro como referência.
                    É um arquivo separado: não precisa estar dentro de um vídeo.</>}
            </Ajuda>
          </label>
          {refsAudio.length > 0 && (
            <div className="refs-audio">
              {refsAudio.map((audio, i) => (
                <div className="ref-audio" key={audio.nome}>
                  <span title={audio.rotulo}>♪ {audio.rotulo}</span>
                  <button
                    className="mini"
                    title="Remover"
                    onClick={() => setRefsAudio((a) => a.filter((_, j) => j !== i))}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
          {refsAudio.length < tetoAudio && (
            <div
              className="area-solta"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                enviarAudio(e.dataTransfer.files)
              }}
              onClick={() => entradaAudio.current?.click()}
            >
              {enviandoAudio ? 'Enviando…' : 'Arraste WAV, MP3, FLAC, M4A ou OGG'}
              <input
                ref={entradaAudio}
                type="file"
                accept="audio/*,.wav,.mp3,.flac,.m4a,.ogg"
                multiple
                hidden
                onChange={(e) => {
                  if (e.target.files) enviarAudio(e.target.files)
                  e.target.value = ''
                }}
              />
            </div>
          )}
        </div>
      )}

      {lentaDisponivel && (
        <div className="campo">
          <label>
            Câmera lenta
            <Ajuda titulo="Como funciona">
              Um LoRA da Lightricks faz o modelo gerar como se filmasse em alta
              velocidade: o movimento sai mais lento e suave, e o vídeo continua
              a 24 fps, sem demorar mais para gerar. Num teste com 0,2×, o
              movimento ficou 2,4× menor que sem o efeito.
            </Ajuda>
          </label>
          <div className="opcoes segmentado">
            {(ger?.camera_lenta ?? []).map((v) => (
              <button key={v} data-ativo={velocidade === v} onClick={() => setVelocidade(v)}>
                {v === 1 ? 'Normal' : `${v}×`}
              </button>
            ))}
          </div>
        </div>
      )}

      {ger?.tem_audio && (
        <label className="alternador">
          <input
            type="checkbox"
            checked={comAudio}
            onChange={(e) => setComAudio(e.target.checked)}
          />
          <span>
            Gerar com som
            <Ajuda titulo="Sobre o som">
              O modelo compõe o áudio junto do vídeo, a partir do que o texto
              sugere. Desligar corta o ramo inteiro e deixa a geração um pouco
              mais leve.
            </Ajuda>
          </span>
        </label>
      )}

      {/* Os tres controles de prompt e som ficam juntos. `enriquece_prompt` e
          coisa do servidor do Wan e nao se confunde com a sugestao, que roda
          na sua placa e LE A IMAGEM para escrever a frase. */}
      {ger?.enriquece_prompt && (
        <label className="alternador">
          <input
            type="checkbox"
            checked={melhorarPrompt}
            onChange={(e) => setMelhorarPrompt(e.target.checked)}
          />
          <span>
            Deixar o serviço enriquecer o prompt
            <Ajuda titulo="Quando desligar">
              O próprio Wan reescreve a sua frase antes de gerar. Ajuda quando a
              descrição é curta; atrapalha quando você escreveu exatamente o que
              quer, porque ele acrescenta por conta própria.
            </Ajuda>
          </span>
        </label>
      )}

      {porChaves ? (
        <div className="campo">
          <label>Resolução de saída</label>
          <span className="opcional">
            1280 × 720 em 16:9; 720 × 1280 em 9:16. Nas demais proporções,
            até 720 px no lado menor e 1280 px no maior. Com upscale e refinamento.
          </span>
        </div>
      ) : (
      <div className="campo">
        <label>
          Resolução
          <Ajuda titulo="O que o “p” significa">
            É o <strong>lado menor</strong> do vídeo, como se usa em cinema e TV:
            a 720p um clipe deitado sai 1280×704 e um em pé sai 704×1280.
            {ger?.max_pixels && (
              <>
                {' '}As combinações que a sua placa não aguenta ficam
                desabilitadas — o limite é medido, não chutado.
              </>
            )}
          </Ajuda>
        </label>
        <div className="opcoes segmentado">
          {resolucoes.map((r) => {
            const [w, h] = pixelsDe(r, proporcao, alinhamento)
            const cabe = !ger?.max_pixels || w * h <= ger.max_pixels
            return (
              <button
                key={r}
                data-ativo={resolucaoNuvem === r}
                disabled={!cabe}
                title={cabe ? `${w}×${h}` : `${w}×${h} não cabe na placa`}
                onClick={() => setResolucaoNuvem(r)}
              >
                {/* O Wan identifica as resolucoes como "480P"; os outros
                    geradores, como "480p". O valor enviado e o do provedor,
                    mas na tela os quatro se parecem. */}
                {r.toLowerCase()}
              </button>
            )
          })}
        </div>
      </div>

      )}

      <div className="campo">
        <label>Proporção</label>
        <div className="opcoes segmentado">
          {(ger?.proporcoes ?? []).map((x) => (
            <button key={x} data-ativo={proporcao === x} onClick={() => setProporcao(x)}>
              {x}
            </button>
          ))}
        </div>
      </div>

      {naNuvem && custoWan == null && ger?.usd_por_segundo_gpu == null && (
        <p className="custo">
          {custoMultiRef ? (
            <>
              Custo estimado:{' '}
              <strong>
                {custoMultiRef.minimo === custoMultiRef.maximo
                  ? `US$ ${custoMultiRef.minimo.toFixed(2)}`
                  : `US$ ${custoMultiRef.minimo.toFixed(2)}–${custoMultiRef.maximo.toFixed(2)}`}
              </strong>
            </>
          ) : (
            <>Preço <strong>não declarado</strong> pelo provedor</>
          )}
          <Ajuda titulo="Como o preço é calculado">
            {custoMultiRef ? (
              <>
                A variante Padrão cobra por segundo e resolução; até cinco
                imagens estão incluídas. Na Max, o custo também depende dos
                tokens das referências, então aparece como uma faixa
                aproximada. O valor efetivo continua medido pela diferença de
                saldo e gravado na galeria.
              </>
            ) : (
              <>
                O valor real da primeira geração fica{' '}
                <strong>medido pela diferença de saldo</strong> e gravado na
                galeria.
              </>
            )}
          </Ajuda>
        </p>
      )}

      {porChaves && (
        <div className="campo">
          <label>
            Força das chaves{' '}
            <span className="opcional">{forcaChaves.toFixed(2).replace('.', ',')}</span>
          </label>
          <input type="range" className="barra" min={0.3} max={1} step={0.05} value={forcaChaves}
            onChange={(e) => setForcaChaves(Number(e.target.value))} />
          <div className="extremos">
            <span>solta: movimento livre</span>
            <span>presa: imagem exata, risco de fusão</span>
          </div>
          <span className="opcional">
            Último quadro: {ultimoQuadro}. Cada número é levado ao múltiplo de 8 mais próximo.
          </span>
        </div>
      )}

      {/* Barra, e nao botoes: a faixa util varia muito entre modelos — o
          MiniMax local vai a 8 s e o Wan a 30. Uma lista fixa ou ficaria curta
          num, ou cheia de botoes no outro. */}
      <div className="campo">
        <label>
          Duração{' '}
          <span className="opcional">
            {duracao}s · {ger?.fps ?? 24} quadros por segundo
          </span>
        </label>
        <input
          type="range"
          className="barra"
          min={ger?.duracao_min ?? 2}
          max={porChaves ? 15 : (ger?.duracao_max ?? 10)}
          step={1}
          value={duracao}
          onChange={(e) => setDuracao(Number(e.target.value))}
        />
        <div className="extremos">
          <span>{ger?.duracao_min ?? 2}s</span>
          <span>máx. deste modo: {porChaves ? 15 : (ger?.duracao_max ?? 10)}s</span>
        </div>
      </div>

      {/* Custo do Wan: exato, porque e por segundo de video gerado. */}
      {custoWan != null && (
        <p className="custo">
          No máximo <strong>US$ {custoWan.toFixed(2)}</strong>
          <Ajuda titulo="Como o preço é calculado">
            O preço é por <strong>segundo de vídeo gerado</strong>, então dá para
            saber antes. Dobrar a duração dobra o custo, e cada salto de
            resolução também.
            {' '}<strong>Este valor é teto:</strong> a tabela do provedor
            superestima — num clipe de 2 s em 480p ela previa US$ 0,14 e a
            cobrança real foi US$ 0,10. O valor cobrado de verdade fica gravado
            na galeria.
          </Ajuda>
        </p>
      )}

      {/* So quem cobra por TEMPO tem tarifa por segundo de GPU. O Hailuo nao
          declara preco nenhum, e cair no `?? 0` fazia a tela anunciar
          "US$ 0.000000" — pior que nao dizer nada, porque afirma que e
          gratis. Ver o bloco seguinte. */}
      {naNuvem && custoWan == null && ger?.usd_por_segundo_gpu != null && (
        <p className="custo">
          {/* Aqui nao ha total a mostrar: quem decide quanto tempo leva e o
              servidor. Sobra a tarifa, e a explicacao vai para a ajuda. */}
          <strong>US$ {(ger?.usd_por_segundo_gpu ?? 0).toFixed(6)}</strong> por
          segundo de GPU
          <Ajuda titulo="Por que não há preço fixo">
            Este é o único item do projeto cobrado por <strong>tempo</strong>,
            não por vídeo — os modelos de imagem cobram por peça. Como o
            servidor decide quanto tempo leva, não dá para mostrar o total
            antes do clique.{' '}
            <strong>Medido:</strong> 5 s em 480p levaram 62 s de relógio, com a
            sua placa parada.
          </Ajuda>
        </p>
      )}



      <details className="avancado">
        <summary>Avançado</summary>
        {porReferencia && (ger?.tamanhos_referencia?.length ?? 0) > 0 && (
          <div className="campo">
            <label>
              Detalhe das referências
              <Ajuda titulo="Match ou máximo">
                <strong>Compatível</strong> reduz cada referência para a área
                do vídeo e é o padrão. <strong>Máximo</strong> usa borda curta
                de 2048 px para tentar preservar mais identidade, mas os tokens
                maiores atravessam todos os passos e podem levar várias vezes
                mais tempo.
              </Ajuda>
            </label>
            <div className="opcoes segmentado">
              {ger?.tamanhos_referencia?.map((valor) => (
                <button
                  key={valor}
                  data-ativo={tamanhoReferencia === valor}
                  onClick={() => setTamanhoReferencia(valor)}
                >
                  {valor === 'max' ? 'Máximo' : 'Compatível'}
                </button>
              ))}
            </div>
          </div>
        )}
        {audioDeIdentidade && refsAudio.length > 0 && (
          <div className="campo">
            <label>
              Força da identidade vocal: {forcaAudioReferencia.toFixed(2)}
              <Ajuda titulo="Custo da força">
                Acima de zero, o LTX faz uma passada adicional por etapa para
                reforçar a voz. O padrão oficial é 3. Zero mantém os tokens da
                amostra, mas desliga essa passada extra.
              </Ajuda>
            </label>
            <input
              type="range"
              min="0"
              max="6"
              step="0.25"
              value={forcaAudioReferencia}
              onChange={(e) => setForcaAudioReferencia(Number(e.target.value))}
            />
          </div>
        )}
        <div className="campo">
          <label>Seed</label>
          <input
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            placeholder="aleatória"
          />
        </div>
      </details>

      <button
        className="principal"
        style={{ width: '100%' }}
        onClick={gerar}
        disabled={!motorVivo || faltamImagens || faltaTexto}
      >
        {ocupado ? 'Adicionar à fila' : 'Gerar vídeo'} · ~{segundos}s
      </button>
      {faltamImagens && (
        <p className="dica">
          {aceitaReferenciaAlternativa
            ? 'Envie ao menos uma imagem, um vídeo ou um áudio de referência.'
            : precisa - refs.length === 1
            ? 'Falta 1 imagem para este modo.'
            : `Faltam ${precisa - refs.length} imagens para este modo.`}
        </p>
      )}
        </>
      )}
    </>
  )
}


// Mesma area de arrastar e soltar de "Imagem de partida", para envios avulsos.
function AreaSolta({ rotulo, aceita, desativada, aoEscolher }: {
  rotulo: string; aceita: string; desativada?: boolean; aoEscolher: (f: File) => void
}) {
  const entrada = useRef<HTMLInputElement>(null)
  return (
    <div
      className="area-solta"
      style={{ marginTop: 6 }}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault()
        const f = e.dataTransfer.files?.[0]
        if (f && !desativada) aoEscolher(f)
      }}
      onClick={() => !desativada && entrada.current?.click()}
    >
      {rotulo}
      <input
        ref={entrada}
        type="file"
        accept={aceita}
        hidden
        onChange={(e) => {
          const f = e.target.files?.[0]
          if (f) aoEscolher(f)
          e.target.value = ''
        }}
      />
    </div>
  )
}


type Escolhida = { nome: string; rotulo: string } | null

// Uma imagem para a aba Transformar: da galeria (menu) ou do computador
// (arrastar e soltar). Mostra a escolhida e permite tirar.
function EscolhaImagem({ titulo, ajuda, valor, aoMudar, galeria, aoErro }: {
  titulo: string; ajuda?: string; valor: Escolhida
  aoMudar: (v: Escolhida) => void; galeria: ItemGaleria[]; aoErro: (e: string) => void
}) {
  const [enviando, setEnviando] = useState(false)
  const pegar = async (f: () => Promise<Escolhida>) => {
    setEnviando(true); aoErro('')
    try { aoMudar(await f()) } catch (e) { aoErro(String(e)) } finally { setEnviando(false) }
  }
  return (
    <div className="campo">
      <label>
        {titulo}
        {ajuda && <Ajuda titulo={titulo}>{ajuda}</Ajuda>}
      </label>
      <select value="" disabled={enviando} onChange={(e) => {
        const item = galeria.find((g) => g.id === Number(e.target.value)); if (!item) return
        pegar(async () => ({ nome: (await referenciaDaGaleria(item)).nome, rotulo: item.arquivo }))
      }}>
        <option value="">Escolher uma imagem da galeria…</option>
        {galeria.filter((g) => !g.duracao_video && !/\.(mp3|wav|flac|ogg|m4a)$/i.test(g.arquivo)).map((g) => (
          <option key={g.id} value={g.id}>{(g.rotulo || g.prompt || g.arquivo).slice(0, 70)}</option>
        ))}
      </select>
      <AreaSolta
        rotulo={enviando ? 'Enviando…' : valor ? 'Arraste outra imagem para trocar'
          : 'Ou arraste uma imagem aqui, ou clique para escolher'}
        aceita="image/*"
        desativada={enviando}
        aoEscolher={(f) => pegar(async () => ({ nome: (await api.enviarReferencia(f)).nome, rotulo: f.name }))}
      />
      {valor && (
        <div style={{ position: 'relative', marginTop: 6 }}>
          <img src={urlEntrada(valor.nome)} alt={titulo} style={{ maxWidth: '100%', borderRadius: 6 }} />
          <button className="mini" style={{ position: 'absolute', top: 4, right: 4 }}
            title="Tirar" onClick={() => aoMudar(null)}>×</button>
        </div>
      )}
    </div>
  )
}


// Player da aba Transformar que mostra o QUADRO (a 24 fps, contado de 1, como
// no Blender), e nao o tempo. O navegador pode errar um quadro ao parar; por
// isso a captura e feita pelo servidor, a partir do numero mostrado, sobre o
// mesmo video em 24 fps que a geracao usa.
function PlayerQuadros({ src, maxQuadros, aoCapturar }: {
  src: string; maxQuadros: number; aoCapturar?: (quadro: number) => void
}) {
  const ref = useRef<HTMLVideoElement>(null)
  const [quadro, setQuadro] = useState(1)
  const [total, setTotal] = useState(0)
  const [capturando, setCapturando] = useState(false)
  useEffect(() => {
    let id = 0
    const passo = () => {
      const v = ref.current
      if (v) setQuadro(Math.floor(v.currentTime * 24 + 1e-3) + 1)
      id = requestAnimationFrame(passo)
    }
    id = requestAnimationFrame(passo)
    return () => cancelAnimationFrame(id)
  }, [])
  // Le a posicao do PROPRIO video, que muda na hora da atribuicao; o numero
  // exibido so atualiza no proximo quadro de tela, e cliques rapidos se perdiam.
  const agora = () => {
    const v = ref.current
    return v ? Math.floor(v.currentTime * 24 + 1e-3) + 1 : quadro
  }
  const ir = (n: number) => {
    const v = ref.current; if (!v) return
    v.pause()
    const alvo = Math.max(1, Math.min(total || n, n))
    // meio do quadro, para o navegador nao parar no anterior
    v.currentTime = (alvo - 1 + 0.5) / 24
  }
  const aceito = Math.round((quadro - 1) / 8) * 8 + 1
  const usado = Math.min(total, maxQuadros)
  return (
    <div style={{ marginTop: 8 }}>
      <video ref={ref} src={src} controls muted preload="metadata"
        style={{ width: '100%', borderRadius: 6, background: '#000' }}
        onLoadedMetadata={(e) => setTotal(Math.floor(e.currentTarget.duration * 24 + 1e-3))} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
        <button className="mini" title="8 quadros para trás" onClick={() => ir(Math.ceil((agora() - 1) / 8) * 8 - 7)}>« 8</button>
        <button className="mini" title="Quadro anterior" onClick={() => ir(agora() - 1)}>‹ 1</button>
        <strong style={{ fontVariantNumeric: 'tabular-nums' }}>Quadro {quadro} de {total || '…'}</strong>
        <button className="mini" title="Próximo quadro" onClick={() => ir(agora() + 1)}>1 ›</button>
        <button className="mini" title="8 quadros para a frente" onClick={() => ir(Math.floor((agora() - 1) / 8) * 8 + 9)}>8 »</button>
      </div>
      <p className="dica" style={{ margin: '4px 2px' }}>
        {quadro > usado
          ? `Depois do quadro ${usado}, o vídeo não é usado neste efeito.`
          : aceito === quadro
            ? 'Este quadro é aceito como quadro-chave.'
            : `Como quadro-chave, entra no quadro ${aceito} (o modelo usa múltiplos de 8; « 8 » pulam entre eles).`}
      </p>
      {aoCapturar && (
        <button className="mini" title="Salva este quadro na galeria e cria o quadro-chave"
          disabled={capturando || quadro > usado} onClick={async () => {
          setCapturando(true)
          try { await aoCapturar(Math.min(aceito, usado)) } finally { setCapturando(false) }
        }}>
          {capturando ? 'Capturando…' : `Capturar quadro ${Math.min(aceito, usado)}`}
        </button>
      )}
    </div>
  )
}
