import { useEffect, useRef, useState } from 'react'
import LuzEsfera from './LuzEsfera'
import Ajuda from './Ajuda'
import Seletor from './Seletor'
import JanelaPip from './JanelaPip'
import {
  api, referenciaDaGaleria, urlImagem, urlMiniatura,
  type ItemGaleria, type ModoEdicao, type Referencia,
} from './api'

type Props = {
  modos: ModoEdicao[]
  gruposEdicao: { id: string; rotulo: string }[]
  proporcoes: string[]
  galeria: ItemGaleria[]
  motorVivo: boolean
  motorCarregado: string | null
  /** Parâmetros vindos de "Reusar parâmetros". O painel repõe o que é dele. */
  reuso: Record<string, unknown> | null
  aoAplicarReuso: () => void
  aoErro: (e: string) => void
  niveisPele: { id: string; rotulo: string }[]
  tiposImagem: { id: string; rotulo: string; nota: string }[]
  // O modo e as referências moram no App para que os botões de ação do painel
  // de informações consigam preencher este formulário de fora.
  modo: string
  setModo: (m: string) => void
  referencias: Referencia[]
  setReferencias: (fn: (r: Referencia[]) => Referencia[]) => void
}

function Deslizante({ rotulo, valor, aoMudar, aoSoltar, min = 0, max = 1,
                     passo = 0.01, dica, rotuloZero = 'desligado',
                     unidade = '' }: {
  rotulo: string
  valor: number
  aoMudar: (v: number) => void
  aoSoltar?: () => void
  min?: number
  max?: number
  passo?: number
  dica?: string
  rotuloZero?: string
  /** Sufixo do valor, como '°' ou '×'. Vazio por omissão, então as
      ferramentas que já usavam este componente não mudam de aparência. */
  unidade?: string
}) {
  // Com passo inteiro, duas casas decimais só poluem.
  const texto = valor === 0 ? rotuloZero
    : (passo >= 1 ? String(valor) : valor.toFixed(passo >= 0.5 ? 1 : 2)) + unidade
  return (
    <div className="deslizante" title={dica}>
      <div className="topo-deslizante">
        <span>{rotulo}</span>
        <strong>{texto}</strong>
      </div>
      <input type="range" min={min} max={max} step={passo} value={valor}
             onChange={(e) => aoMudar(Number(e.target.value))}
             onPointerUp={aoSoltar} onKeyUp={aoSoltar} />
    </div>
  )
}

export default function PainelEdicao({
  modos, gruposEdicao, proporcoes, galeria, motorVivo, motorCarregado, reuso,
  aoAplicarReuso, aoErro, niveisPele, tiposImagem,
  modo, setModo, referencias, setReferencias,
}: Props) {
  const [instrucao, setInstrucao] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [arrastando, setArrastando] = useState(false)
  const [proporcao, setProporcao] = useState('1:1')
  const [forcaEstilo, setForcaEstilo] = useState(1)
  const [seed, setSeed] = useState('')
  const [steps, setSteps] = useState('')
  const [cfg, setCfg] = useState('')
  const [abrirGaleria, setAbrirGaleria] = useState(false)
  const [mascaraAlvo, setMascaraAlvo] = useState('')
  const [limiar, setLimiar] = useState(0.5)
  const [expandir, setExpandir] = useState(12)
  const [suavizar, setSuavizar] = useState(12)
  const [tipoControle, setTipoControle] = useState('contorno')
  const [forcaControle, setForcaControle] = useState(1)
  const [mapa, setMapa] = useState<string | null>(null)
  const [calculandoMapa, setCalculandoMapa] = useState(false)
  const [metodoAmpliar, setMetodoAmpliar] = useState('seedvr')
  const [escalaAmpliar, setEscalaAmpliar] = useState(2)
  const [magnific, setMagnific] = useState({ magnific_criatividade: 0, magnific_hdr: 0, magnific_semelhanca: 0, magnific_fractalidade: 0 })
  const ehMagnific = modo === 'ampliar' && metodoAmpliar === 'magnific'
  const custoMagnific = ({2: '0,172–0,515', 4: '0,343–0,844', 8: '0,515–1,015', 16: '0,844–1,187'} as Record<number, string>)[escalaAmpliar]
  const [otimizacao, setOtimizacao] = useState('geral')
  const [criatividade, setCriatividade] = useState(0.33)
  const [semelhanca, setSemelhanca] = useState(0)
  const [microcontraste, setMicrocontraste] = useState(0)
  const [granulacao, setGranulacao] = useState(0)
  const [detalhe, setDetalhe] = useState(0)
  const [vista, setVista] = useState('tres_quartos_esq')
  const [azimute, setAzimute] = useState(-45)
  const [elevacao, setElevacao] = useState(25)
  const [intensidade, setIntensidade] = useState(1)
  const [temperatura, setTemperatura] = useState('neutra')
  const [usarMapaLuz, setUsarMapaLuz] = useState(true)
  const [nivelPele, setNivelPele] = useState('moderado')
  const [tipoImagem, setTipoImagem] = useState('retrato')
  const [negativoManual, setNegativoManual] = useState('')
  const [blocos, setBlocos] = useState<Record<string, boolean>>({})
  // Vazio = "o usuário ainda não escolheu". O padrão não pode ser literal:
  // "Rápido" só entra no catálogo se o Klein destilado estiver no disco, e um
  // padrão fixo abriria o painel numa opção que talvez não exista. Quem manda
  // é a ordem de presets.PERSONAGEM["prioridades"], já filtrada pelo motor.
  const [prioridade, setPrioridade] = useState('')
  // Média (1,5 MP) é onde a textura fina aparece sem o custo da alta.
  const [resolucao, setResolucao] = useState('media')
  const [variacoes, setVariacoes] = useState(1)
  const [metodoAngulo, setMetodoAngulo] = useState('camera')
  const [metodoLuz, setMetodoLuz] = useState('direcional')
  const [estiloLuz, setEstiloLuz] = useState('standard')
  const [forcaLuz, setForcaLuz] = useState(100)
  const [rosto, setRosto] = useState<Record<string, number>>({})
  const [camera, setCamera] = useState<Record<string, number>>({})
  const [previaRosto, setPreviaRosto] = useState<string | null>(null)
  const [calculandoRosto, setCalculandoRosto] = useState(false)
  const [pipRosto, setPipRosto] = useState(false)
  const entradaRef = useRef<HTMLInputElement>(null)

  const m = modos.find((x) => x.id === modo)
  // O que vai no pedido e o que acende no painel — nunca o estado cru, que
  // fica vazio até o usuário tocar na chave ou o reuso preencher.
  const prioridadeEfetiva = prioridade || m?.prioridades?.[0]?.id || 'fiel'
  const ehEstilo = modo === 'estilo'
  const ehControle = modo === 'controle'
  const ehAmpliar = modo === 'ampliar'
  const ehRecorte = modo === 'recorte'
  const ehAngulo = modo === 'angulo'
  const ehPersonagem = modo === 'personagem'
  const ehReluz = modo === 'reluz'
  const ehQwen = modo === 'qwen'
  const ehFolha = modo === 'folha'
  const ehCabeca = modo === 'cabeca'
  const ehRosto = modo === 'rosto'
  const ehAnygles = modo === 'anygles'

  // Sinaliza que um reuso acabou de repor os controles, para o efeito de
  // baixo não zerá-los. Um estado não serviria: limpar o `reuso` é em si uma
  // mudança que dispara aquele efeito de novo, agora sem a guarda.
  const veioDeReuso = useRef(false)

  // Repõe os controles a partir de uma imagem da galeria. Cada campo só entra
  // se veio no registro — assim uma imagem antiga, gravada antes de o banco
  // guardar tudo, não zera o que está na tela.
  useEffect(() => {
    if (!reuso) return
    const n = (k: string) => (typeof reuso[k] === 'number' ? (reuso[k] as number) : undefined)
    const t = (k: string) => (typeof reuso[k] === 'string' ? (reuso[k] as string) : undefined)
    const pares: [string, (v: never) => void][] = [
      ['metodo_ampliar', setMetodoAmpliar as never],
      ['otimizacao', setOtimizacao as never],
      ['vista', setVista as never],
      ['temperatura', setTemperatura as never],
      ['tipo_controle', setTipoControle as never],
      ['metodo_angulo', setMetodoAngulo as never],
      ['metodo_luz', setMetodoLuz as never],
      ['resolucao_edicao', setResolucao as never],
      ['prioridade', setPrioridade as never],
      ['nivel_pele', setNivelPele as never],
      ['tipo_imagem', setTipoImagem as never],
    ]
    for (const [chave, aplicar] of pares) {
      const v = t(chave)
      if (v !== undefined) (aplicar as (x: string) => void)(v)
    }
    const numeros: [string, (v: number) => void][] = [
      ['escala_ampliar', setEscalaAmpliar], ['criatividade', setCriatividade],
      ['semelhanca', setSemelhanca], ['detalhe', setDetalhe],
      ['microcontraste', setMicrocontraste], ['granulacao', setGranulacao],
      ['forca_controle', setForcaControle], ['forca_estilo', setForcaEstilo],
      ['azimute', setAzimute], ['elevacao', setElevacao],
      ['intensidade', setIntensidade],
    ]
    setMagnific({ magnific_criatividade: n('magnific_criatividade') ?? 0, magnific_hdr: n('magnific_hdr') ?? 0, magnific_semelhanca: n('magnific_semelhanca') ?? 0, magnific_fractalidade: n('magnific_fractalidade') ?? 0 })
    for (const [chave, aplicar] of numeros) {
      const v = n(chave)
      if (v !== undefined) aplicar(v)
    }
    if (reuso.rosto && typeof reuso.rosto === 'object') {
      setRosto(reuso.rosto as Record<string, number>)
    }
    if (reuso.blocos && typeof reuso.blocos === 'object') {
      setBlocos(reuso.blocos as Record<string, boolean>)
    }
    if (typeof reuso.usar_mapa_luz === 'boolean') setUsarMapaLuz(reuso.usar_mapa_luz)
    veioDeReuso.current = true
    aoAplicarReuso()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reuso])

  // Fora da fila: são ~1s, então dá para ver o efeito arrastando. Uma chamada
  // por soltar de controle — não por pixel movido, que faria dezenas.
  const atualizarPreviaRosto = async () => {
    if (!referencias.length || calculandoRosto) return
    setCalculandoRosto(true)
    try {
      const r = await api.previaRosto(referencias[0].nome, rosto)
      setPreviaRosto(urlImagem({ nome: r.nome, subpasta: r.subpasta }) + `&t=${Date.now()}`)
    } catch (e) {
      aoErro(String(e))
    } finally {
      setCalculandoRosto(false)
    }
  }

  // A folha nao edita a foto no lugar: ela monta uma imagem nova, com
  // dimensoes proprias. Mascara nao tem o que recortar aqui.
  // O Anygles entra na mesma lista por um motivo proprio: ele devolve a cena
  // REENQUADRADA, em outro tamanho, entao nao ha pixel da imagem original com
  // que casar uma mascara.
  const usaMascara =
    !ehEstilo && !ehControle && !ehAmpliar && !ehAngulo && !ehReluz &&
    !ehPersonagem && !ehRecorte && !ehFolha && !ehAnygles && !ehCabeca
  // Ampliação não recebe texto; ângulo e reiluminação montam a instrução
  // sozinhos e o texto é só um complemento opcional.
  // Recorte nao recebe texto: o modelo decide o recorte sozinho.
  const usaPrompt = (!ehAmpliar || ehMagnific) && !ehRecorte
  // Na folha o gatilho do LoRA ja e a instrucao; o texto so complementa.
  // No Anygles a instrucao de camera e montada pelo no, na frase em que o
  // LoRA foi treinado; o texto do usuario so complementa.
  const textoOpcional = ehMagnific || ehAngulo || ehReluz || ehPersonagem || ehFolha || ehAnygles || ehCabeca
  // O metodo pode ampliar o limite do modo: o Magnific aceita uma
  // segunda imagem, a de onde copiar a luz.
  const metodoAtual = m?.metodos?.find(
    (x) => x.id === (ehAngulo ? metodoAngulo : metodoLuz),
  )
  const tetoRefs = metodoAtual?.max_referencias ?? m?.max_referencias ?? 1
  const custoDoMetodo = metodoAtual?.custo_usd ?? 0
  const cheio = m ? referencias.length >= tetoRefs : false

  const adicionar = async (arquivos: FileList | File[]) => {
    if (!m) return
    const espaco = tetoRefs - referencias.length
    const lista = Array.from(arquivos)
      .filter((f) => f.type.startsWith('image/'))
      .slice(0, espaco)
    if (!lista.length) return
    setEnviando(true)
    try {
      const novas: Referencia[] = []
      for (const f of lista) novas.push(await api.enviarReferencia(f))
      setReferencias((r) => [...r, ...novas])
    } catch (e) {
      aoErro(String(e))
    } finally {
      setEnviando(false)
    }
  }

  /** Reaproveita uma imagem da galeria sem o usuário ter que baixá-la antes. */
  const daGaleria = async (item: ItemGaleria) => {
    setEnviando(true)
    try {
      const ref = await referenciaDaGaleria(item)
      setReferencias((lista) => [...lista, ref])
      setAbrirGaleria(false)
    } catch (e) {
      aoErro(String(e))
    } finally {
      setEnviando(false)
    }
  }

  const remover = (i: number) =>
    setReferencias((r) => r.filter((_, j) => j !== i))

  // Arrastar um cartao de referencia sobre outro: ele toma aquela posicao.
  const [arrastandoRef, setArrastandoRef] = useState<number | null>(null)
  const [alvoRef, setAlvoRef] = useState<number | null>(null)
  const moverPara = (de: number, para: number) =>
    setReferencias((r) => {
      if (de === para || de < 0 || para < 0 || de >= r.length || para >= r.length) return r
      const copia = [...r]
      const [item] = copia.splice(de, 1)
      copia.splice(para, 0, item)
      return copia
    })
  const mover = (i: number, delta: number) =>
    setReferencias((r) => {
      const j = i + delta
      if (j < 0 || j >= r.length) return r
      const copia = [...r]
      ;[copia[i], copia[j]] = [copia[j], copia[i]]
      return copia
    })

  /** Trocar o preset repõe os controles no ponto de partida daquele uso.
   *  Só o criativo tem preset — ver o bloco do SeedVR2 mais abaixo. */
  const escolherOtimizacao = (id: string) => {
    setOtimizacao(id)
    const o = m?.otimizacoes?.find((x) => x.id === id)
    if (!o) return
    const p = o.padroes
    setCriatividade(p.criatividade)
    setSemelhanca(p.semelhanca)
    setDetalhe(p.detalhe)
    setMicrocontraste(p.microcontraste)
    setGranulacao(p.granulacao)
  }

  // O criativo parte do preset; o SeedVR2 parte do zero, que é o cru — e no
  // SeedVR2 o cru é a escolha, não um esquecimento.
  //
  // Não roda durante um reuso: os dois efeitos disparam no mesmo commit, e
  // este, sendo declarado depois, apagaria os valores que o reuso acabou de
  // repor. Foi o que aconteceu — o método e a escala voltavam, o Detalhe não.
  useEffect(() => {
    if (modo !== 'ampliar') return
    if (veioDeReuso.current) { veioDeReuso.current = false; return }
    setEscalaAmpliar((v) => metodoAmpliar === 'magnific' ? ([2, 4, 8, 16].includes(v) ? v : 2) : Math.min(v, 4))
    if (metodoAmpliar === 'criativo') escolherOtimizacao(otimizacao)
    if (metodoAmpliar === 'seedvr') {
      setDetalhe(0); setMicrocontraste(0); setGranulacao(0)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [modo, metodoAmpliar, modos])

  const editar = async () => {
    if (!m) return
    try {
      await api.gerar({
        modelo: modo,
        prompt: instrucao,
        proporcao,
        referencias: referencias.map((r) => r.nome),
        forca_estilo: forcaEstilo,
        mascara_alvo: usaMascara ? mascaraAlvo : '',
        tipo_controle: tipoControle,
        forca_controle: forcaControle,
        ...magnific,
        metodo_ampliar: metodoAmpliar,
        escala_ampliar: escalaAmpliar,
        otimizacao,
        criatividade,
        semelhanca,
        microcontraste,
        granulacao,
        detalhe,
        vista,
        azimute,
        elevacao,
        intensidade,
        temperatura,
        usar_mapa_luz: usarMapaLuz,
        nivel_pele: nivelPele,
        blocos,
        prioridade: prioridadeEfetiva,
        resolucao_edicao: resolucao,
        variacoes,
        metodo_angulo: metodoAngulo,
        metodo_luz: metodoLuz,
        estilo_luz: estiloLuz,
        forca_luz: forcaLuz,
        rosto,
        // Os tres eixos da camera. O padrao vem do preset, nao de um
        // numero escrito aqui: duplicar a faixa em dois lugares e como
        // o alinhamento do LTX divergiu entre tela e backend.
        ...Object.fromEntries((m?.camera ?? []).map(
          (c) => [c.id, camera[c.id] ?? c.padrao])),
        tipo_imagem: tipoImagem,
        negativo: negativoManual,
        mascara_limiar: limiar,
        mascara_expandir: expandir,
        mascara_suavizar: suavizar,
        seed: seed.trim() === '' ? null : Number(seed),
        steps: steps.trim() === '' ? null : Number(steps),
        cfg: cfg.trim() === '' ? null : Number(cfg),
      })
    } catch (e) {
      aoErro(String(e))
    }
  }

  const podeEditar =
    motorVivo && m !== undefined &&
    (!usaPrompt || textoOpcional || instrucao.trim() !== '') &&
    referencias.length >= m.min_referencias

  return (
    <>
      <Seletor
        rotulo="Modo"
        valor={modo}
        aoEscolher={setModo}
        grupos={gruposEdicao}
        opcoes={modos.map((x) => ({
          id: x.id,
          rotulo: x.rotulo,
          descricao: x.descricao,
          // O medido vale mais que o escrito à mão: a estimativa era feita
          // com o modelo já quente e errava por minutos quando havia troca.
          segundos: x.medido?.mediana ?? x.segundos_estimados,
          medido: !!x.medido,
          trocaMotor: !!motorCarregado && !!x.motor && x.motor !== motorCarregado,
          grupo: x.grupo,
        }))}
      />

      <div className="campo">
        <label>
          Imagens {m && `(até ${tetoRefs})`}
        </label>

        <div
          className="area-solta"
          data-sobre={arrastando}
          onDragOver={(e) => { e.preventDefault(); setArrastando(true) }}
          onDragLeave={() => setArrastando(false)}
          onDrop={(e) => {
            e.preventDefault()
            setArrastando(false)
            adicionar(e.dataTransfer.files)
          }}
          onClick={() => entradaRef.current?.click()}
        >
          {enviando ? 'Enviando…' : cheio
            ? 'Limite de imagens atingido'
            : 'Arraste imagens aqui, ou clique para escolher'}
          <input
            ref={entradaRef}
            type="file"
            accept="image/*"
            multiple
            hidden
            onChange={(e) => {
              if (e.target.files) adicionar(e.target.files)
              e.target.value = ''
            }}
          />
        </div>

        <button
          className="mini"
          style={{ width: '100%', marginTop: 6 }}
          disabled={cheio || enviando}
          onClick={() => setAbrirGaleria((v) => !v)}
        >
          {abrirGaleria ? 'Fechar galeria' : 'Usar imagem da galeria'}
        </button>

        {abrirGaleria && (
          <div className="galeria-tiras" style={{ marginTop: 8, maxHeight: 190, overflowY: 'auto' }}>
            {galeria.map((item) => (
              <button
                key={item.id}
                className="miniatura"
                style={{ width: 62, height: 62 }}
                title={item.prompt.slice(0, 100)}
                onClick={() => daGaleria(item)}
              >
                <img src={urlMiniatura({ nome: item.arquivo, subpasta: item.subpasta })}
                     loading="lazy" alt="" />
              </button>
            ))}
          </div>
        )}

        {referencias.length > 0 && (
          <div className="lista-referencias">
            {referencias.map((r, i) => (
              <div
                key={r.nome}
                className="item-referencia"
                draggable
                data-arrastando={arrastandoRef === i}
                data-alvo={alvoRef === i && arrastandoRef !== null && arrastandoRef !== i}
                title="Arraste para mudar a ordem"
                onDragStart={(e) => {
                  e.dataTransfer.setData('text/x-referencia', String(i))
                  e.dataTransfer.effectAllowed = 'move'
                  setArrastandoRef(i)
                }}
                onDragOver={(e) => {
                  if (!e.dataTransfer.types.includes('text/x-referencia')) return
                  e.preventDefault(); e.stopPropagation(); setAlvoRef(i)
                }}
                onDrop={(e) => {
                  const de = e.dataTransfer.getData('text/x-referencia')
                  if (de === '') return
                  e.preventDefault(); e.stopPropagation()
                  moverPara(Number(de), i)
                  setArrastandoRef(null); setAlvoRef(null)
                }}
                onDragEnd={() => { setArrastandoRef(null); setAlvoRef(null) }}
              >
                <img src={r.url} alt="" />
                <div className="meta-referencia">
                  <b>
                    {/* Qualquer modo que declare papéis usa os dele; não só
                        a troca de personagem. */}
                    <span className="selo-ref" title="Cite esta imagem assim na instrução">@imagem{i + 1}</span>{' '}
                    {m?.papeis?.length
                      ? (m.papeis[i] ?? `Imagem ${i + 1}`)
                      : ehControle
                      ? 'Referência de estrutura'
                      : i === 0 && !ehEstilo
                        ? 'Imagem base'
                        : `Referência ${ehEstilo ? i + 1 : i}`}
                  </b>
                  <div className="botoes-referencia">
                    <button className="mini" disabled={i === 0} onClick={() => mover(i, -1)}>↑</button>
                    <button className="mini" disabled={i === referencias.length - 1}
                            onClick={() => mover(i, 1)}>↓</button>
                    <button className="mini" onClick={() => remover(i)}>remover</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {usaPrompt && (
      <div className="campo">
        <label>
          {textoOpcional ? 'Complemento (opcional)'
            : usaMascara ? 'Instrução' : 'O que gerar'}
        </label>
        <textarea
          value={instrucao}
          onChange={(e) => setInstrucao(e.target.value)}
          placeholder={
            ehCabeca
              ? 'Detalhe opcional — ex.: preserve o penteado da referência'
              : ehFolha
              ? 'O que a foto não mostra — ex.: bota preta de cano curto'
              : textoOpcional
              ? 'Algo a acrescentar à instrução montada acima'
              : ehControle
              ? 'Descreva a imagem que você quer, seguindo a estrutura da referência'
              : ehEstilo
                ? 'Descreva a imagem que você quer, na estética das referências'
                : 'Diga o que mudar e o que deve permanecer igual'
          }
        />
        {referencias.length > 1 && (
          <p className="dica" style={{ margin: '6px 2px 4px' }}>
            Cite as imagens como <b>@imagem1</b>, <b>@imagem2</b>… (a ordem da lista
            acima). O app troca pelo nome que este modelo reconhece. Diga o papel de
            cada uma: “the person from @imagem1, in the scene of @imagem2”.
          </p>
        )}
      </div>
      )}

      {/* A dica do modo fala da esfera, que o Magnific nao usa. Mostra-la
          ali seria descrever um controle que nao esta na tela. */}
      {/* A dica do MODO aparece em todas as ferramentas e era a mais longa da
          tela. Vira bolinha logo abaixo do seletor: continua a um passo de
          distancia, sem empurrar os controles para baixo. */}
      {m && !(ehReluz && metodoLuz === 'nuvem') && (
        <p className="linha-ajuda">
          Como usar<Ajuda titulo="Como usar este modo">{m.dica}</Ajuda>
        </p>
      )}

      {ehRecorte && (
        <p className="custo">
          Este recorte vai custar <strong>US$ 0.01</strong>. A foto sai da sua
          máquina e roda no servidor do provedor.
        </p>
      )}

      {ehAmpliar && (
        <>
          <Seletor
            rotulo="Método"
            valor={metodoAmpliar}
            aoEscolher={setMetodoAmpliar}
            opcoes={(m?.metodos ?? []).map((x) => ({
              id: x.id, rotulo: x.rotulo, descricao: x.nota,
            }))}
          />

          {/* O custo aparece assim que o metodo e escolhido, e nao so no
              botao: aqui a escala ainda vai mudar o tamanho de saida, e o
              preco do Topaz e por megapixel de SAIDA. */}
          {!ehMagnific && !!m?.metodos?.find((x) => x.id === metodoAmpliar)?.custo_usd && (
            <p className="custo">
              Cerca de{' '}
              <strong>
                US$ {(m.metodos.find((x) => x.id === metodoAmpliar)!.custo_usd!).toFixed(2)}
              </strong>{' '}
              por 8 MP de saída, entao a escala muda o preco. A foto sai da sua
              máquina e roda no servidor do provedor.
            </p>
          )}
          <div className="campo">
            <label>Escala</label>
            <div className="opcoes segmentado">
              {(ehMagnific ? [2, 4, 8, 16] : m?.escalas ?? []).map((e) => (
                <button key={e} data-ativo={escalaAmpliar === e}
                        onClick={() => setEscalaAmpliar(e)}>
                  {e}×
                </button>
              ))}
            </div>
          </div>

          {ehMagnific && <>
            <p className="custo">Estimativa: US$ {custoMagnific} por imagem, conforme o tamanho. Usa créditos Comfy e envia a foto ao provedor.</p>
            <p className="dica">Máximo de 25,3 MP na saída; entrada mínima de 160 × 160 e proporção entre 1:3 e 3:1. Prompt opcional.</p>
            {([
              ['magnific_criatividade', 'Criatividade'], ['magnific_hdr', 'HDR / definição'],
              ['magnific_semelhanca', 'Semelhança'], ['magnific_fractalidade', 'Fractalidade'],
            ] as const).map(([id, rotulo]) => <Deslizante key={id} rotulo={rotulo}
              valor={magnific[id]} min={-10} max={10} passo={1} rotuloZero="0"
              aoMudar={(v) => setMagnific((anterior) => ({ ...anterior, [id]: v }))} />)}
          </>}
          {metodoAmpliar === 'seedvr' && (
            <p className="dica">
              O SeedVR2 roda <strong>sem acabamento</strong>, de propósito. O
              controle de Detalhe abaixo transplanta nitidez de outra imagem, e
              nenhuma das fontes possíveis serve aqui: todas ou borram ou deixam
              padrão na pele. Se o resultado sair duro demais, suba o Detalhe —
              mas saiba que ele suaviza bastante já no primeiro passo.
            </p>
          )}

          {metodoAmpliar === 'criativo' && (
            <>
              <div className="campo">
                <label>Otimizado para
          <Ajuda>
            Trocar o preset repõe estes controles e o acabamento no ponto de
                partida daquele uso. São escolhas de projeto, não ótimos medidos —
                mexa à vontade.
          </Ajuda>
        </label>
                <div className="opcoes">
                  {(m?.otimizacoes ?? []).map((o) => (
                    <button key={o.id} data-ativo={otimizacao === o.id}
                            onClick={() => escolherOtimizacao(o.id)}>
                      {o.rotulo}
                    </button>
                  ))}
                </div>
              </div>
              <Deslizante rotulo="Criatividade" valor={criatividade} aoMudar={setCriatividade}
                          max={0.8} dica="Quanto o modelo pode inventar. Acima de 0,5 ele começa a mudar o conteúdo." />
              <Deslizante rotulo="Semelhança" valor={semelhanca} aoMudar={setSemelhanca}
                          dica="Puxa o resultado de volta para a ampliação sem invenção." />
            </>
          )}

          {!ehMagnific && <div className="campo">
            <label>Acabamento</label>
            <Deslizante rotulo="Detalhe" valor={detalhe} aoMudar={setDetalhe}
                        dica="Recupera microdetalhe real da ampliação. Não inventa." />
            <Deslizante rotulo="Microcontraste" valor={microcontraste} aoMudar={setMicrocontraste}
                        dica="Realce local. Não é HDR de verdade." />
            <Deslizante rotulo="Granulação" valor={granulacao} aoMudar={setGranulacao}
                        dica="Grão de filme, aplicado por último." />
          </div>}
        </>
      )}

      {ehPersonagem && (
        <div className="campo">
          <label>O que a instrução deve travar
          <Ajuda>
            Cada bloco é um parágrafo da instrução enviada ao modelo. Desligue o
            que não se aplica — travar o olhar atrapalha se ele <em>deve</em>
            olhar para a câmera.
          </Ajuda>
        </label>
          {(m?.blocos ?? []).map((b) => (
            <label className="alternador" key={b.id} style={{ marginBottom: 5 }}>
              <input
                type="checkbox"
                checked={blocos[b.id] ?? b.padrao}
                onChange={(e) => setBlocos((v) => ({ ...v, [b.id]: e.target.checked }))}
              />
              <span>{b.rotulo}</span>
            </label>
          ))}
        </div>
      )}

      {ehAnygles && (
        <div className="campo">
          <label>Ângulo
            <Ajuda>
              Use fotos de <strong>corpo inteiro</strong>. Numa imagem cortada
              na cintura o modelo inventa as pernas e o chão, e costuma
              inventar um degrau sob os pés — medido num par com tudo igual
              menos o enquadramento. Ele também <strong>reenquadra</strong>
              para o corpo todo, então a pessoa volta menor no quadro.
              <br /><br />
              O <strong>cenário é recriado</strong>, não girado junto: ao
              <em>girar</em>, o ponto de vista do fundo acompanhou em duas de
              quatro cenas testadas e ficou como estava nas outras duas. A
              pessoa gira sempre — até 180°, de costas.
              <br /><br />
              Na <strong>altura</strong> é diferente: aí o cenário acompanha.
              E os dois eixos <strong>somam</strong> — na cena em que o giro
              sozinho não movia o fundo, bastou acrescentar altura para a
              estrada passar a atravessar o quadro na diagonal. <strong>Se o
              cenário não acompanhar o giro, acrescente Altura.</strong>
              <br /><br />
              As faixas dos três controles já estão limitadas ao que foi
              medido — mais baixo que −45° a pessoa perdia a postura de pé,
              e mais perto que 0,8× o enquadramento cortava a cabeça.
            </Ajuda>
          </label>
          {(m?.camera ?? []).map((c) => (
            <Deslizante
              key={c.id}
              rotulo={c.rotulo}
              valor={camera[c.id] ?? c.padrao}
              min={c.min}
              max={c.max}
              passo={c.passo}
              unidade={c.unidade}
              dica={c.nota}
              rotuloZero="sem mudança"
              aoMudar={(v) => setCamera((x) => ({ ...x, [c.id]: v }))}
            />
          ))}
          <div className="opcoes">
            <button type="button" className="mini" onClick={() => setCamera({})}>
              Voltar ao padrão
            </button>
          </div>
        </div>
      )}

      {ehRosto && (
        <>
          {(m?.grupos ?? []).map((g) => (
            <div className="campo" key={g.rotulo}>
              <label>{g.rotulo}</label>
              {g.controles.map((c) => (
                <Deslizante
                  key={c.id}
                  rotulo={c.rotulo}
                  valor={rosto[c.id] ?? c.padrao}
                  min={c.min}
                  max={c.max}
                  passo={c.passo}
                  dica={c.dica}
                  rotuloZero="neutro"
                  aoMudar={(v) => setRosto((r) => ({ ...r, [c.id]: v }))}
                  aoSoltar={() => void atualizarPreviaRosto()}
                />
              ))}
            </div>
          ))}

          <div className="campo">
            <div className="opcoes">
              <button
                type="button"
                className="mini"
                onClick={() => { setRosto({}); setPreviaRosto(null) }}
              >
                Zerar tudo
              </button>
              <button
                type="button"
                className="mini"
                data-ativo={pipRosto}
                disabled={!referencias.length}
                title="Abre a prévia numa janela flutuante, por cima da tela, com zoom"
                onClick={() => setPipRosto((v) => !v)}
              >
                PIP
              </button>
            </div>
            {pipRosto && referencias.length > 0 && (
              <JanelaPip src={previaRosto} original={referencias[0].url}
                         calculando={calculandoRosto} aoFechar={() => setPipRosto(false)} />
            )}
            {previaRosto && !pipRosto ? (
              <>
                <img src={previaRosto} alt="prévia do rosto"
                     style={{ width: '100%', borderRadius: 6, marginTop: 8 }} />
                <p className="dica">
                  Prévia ao vivo, aplicada fora da fila. {calculandoRosto && '…'}
                </p>
              </>
            ) : pipRosto ? (
              <p className="dica">A prévia está na janela flutuante. {calculandoRosto && '…'}</p>
            ) : (
              <p className="dica">
                Arraste um controle e solte: a prévia aparece em cerca de um
                segundo. Na primeira vez o motor baixa os modelos do
                LivePortrait e pode demorar.
              </p>
            )}
          </div>
        </>
      )}

      {ehQwen && (
        <div className="campo">
          <label>Resolução da saída
          <Ajuda>
            Para sair maior que 2 MP, edite aqui e depois use <strong>Ampliar</strong>
            — o SeedVR2 amplia melhor do que pedir ao editor para gerar grande.
          </Ajuda>
        </label>
          <div className="opcoes">
            {(m?.resolucoes ?? []).map((r) => (
              <button
                type="button"
                key={r.id}
                className="opcao"
                data-ativo={resolucao === r.id}
                onClick={() => setResolucao(r.id)}
              >
                <b>
                  {r.rotulo} <em>· {r.megapixels} MP</em>
                </b>
                <small>{r.nota}</small>
              </button>
            ))}
          </div>
        </div>
      )}

      {ehPersonagem && (m?.prioridades?.length ?? 0) > 1 && (
        <div className="campo">
          <label>Velocidade ou fidelidade
          <Ajuda>
            Dois modelos para o mesmo trabalho: o <strong>Klein
            destilado</strong>, em 4 passos, e o <strong>Klein base</strong>,
            em 20. Num teste lado a lado o destilado empatou, e por isso abre
            por ele. Se a identidade não vier, troque para Fiel.
          </Ajuda>
        </label>
          <div className="opcoes">
            {(m?.prioridades ?? []).map((o) => (
              <button
                type="button"
                key={o.id}
                className="opcao"
                data-ativo={prioridadeEfetiva === o.id}
                onClick={() => setPrioridade(o.id)}
              >
                <b>
                  {o.rotulo} <em>· ~{o.segundos}s</em>
                </b>
                <small>{o.nota}</small>
              </button>
            ))}
          </div>
        </div>
      )}

      {ehPersonagem && m?.tem_destilado === false && (
        <div className="campo">
        </div>
      )}

      {(ehAngulo || ehReluz) && (
        <div className="campo">
          <label>{ehAngulo ? 'O que deve se mover' : 'Como reiluminar'}</label>
          <div className="opcoes">
            {(m?.metodos ?? []).map((o) => {
              const atual = ehAngulo ? metodoAngulo : metodoLuz
              return (
                <button
                  type="button"
                  key={o.id}
                  className="opcao"
                  data-ativo={atual === o.id}
                  onClick={() => (ehAngulo ? setMetodoAngulo(o.id) : setMetodoLuz(o.id))}
                >
                  <b>
                    {o.rotulo} <em>· ~{o.segundos}s</em>
                  </b>
                  <small>{o.nota}</small>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {ehAngulo && (
        <div className="campo">
          <label>Novo ponto de vista</label>
          <div className="opcoes">
            {(m?.vistas ?? []).map((v) => (
              <button key={v.id} data-ativo={vista === v.id} onClick={() => setVista(v.id)}>
                {v.rotulo}
              </button>
            ))}
          </div>
          {metodoAngulo === 'camera' &&
            m?.vistas?.find((v) => v.id === vista)?.camera_documentada === false && (
              <p className="dica">
                A LoRA de câmera não foi treinada nesta vista — a ficha dela cobre
                giros de 45°, cima, baixo, close e grande-angular. Aqui ela pode
                falhar; <strong>Girar o personagem</strong> tende a sair melhor.
              </p>
            )}
        </div>
      )}

      {ehReluz && metodoLuz === 'nuvem' && (
        <>
          {/* A esfera, a temperatura e a intensidade nao aparecem aqui: o
              Magnific nao recebe nada disso. MEDIDO nesta base: pedir "luz
              vinda da direita" por texto NAO moveu a luz — a diferenca
              esquerda-direita foi de +41,3 para +64,4, ou seja, reforcou a luz
              que ja existia e dourou a cena inteira. O caminho que funciona e
              a segunda imagem. */}
          <div className="campo">
            <label>De onde copiar a luz
          <Ajuda>
            {referencias.length > 1
                ? 'A segunda imagem manda: a luz dela é transferida para a primeira.'
                : 'Envie uma SEGUNDA imagem acima, com a luz que você quer. É o que funciona: pedir a direção por texto não moveu a luz no teste.'}
          </Ajuda>
        </label>
          </div>

          <div className="campo">
            <label>Acabamento</label>
            <div className="opcoes">
              {(metodoAtual?.estilos ?? []).map((e) => (
                <button key={e.id} data-ativo={estiloLuz === e.id}
                        onClick={() => setEstiloLuz(e.id)}>
                  {e.rotulo}
                </button>
              ))}
            </div>
          </div>

          <Deslizante rotulo="Força da transferência" valor={forcaLuz}
                      aoMudar={setForcaLuz} min={0} max={100} passo={5}
                      dica="Quanto da luz da referência é aplicado." />

          <p className="custo">
            Esta reiluminação vai custar <strong>US$ {custoDoMetodo.toFixed(2)}</strong>.
            A foto sai da sua máquina e roda no servidor do provedor.
          </p>
        </>
      )}

      {ehReluz && metodoLuz !== 'nuvem' && (
        <>
          <div className="campo">
            <label>Posição da luz</label>
            <LuzEsfera
              azimute={azimute}
              elevacao={elevacao}
              intensidade={intensidade}
              temperatura={temperatura}
              aoMover={(a, e) => { setAzimute(a); setElevacao(e) }}
            />
          </div>

          <div className="campo">
            <label>Temperatura</label>
            <div className="opcoes segmentado">
              {(m?.temperaturas ?? []).map((t) => (
                <button key={t.id} data-ativo={temperatura === t.id}
                        onClick={() => setTemperatura(t.id)}>
                  {t.rotulo}
                </button>
              ))}
            </div>
          </div>

          <Deslizante rotulo="Intensidade" valor={intensidade} aoMudar={setIntensidade}
                      max={1.5} dica="De penumbra a luz dura com sombra marcada." />

          {/* A esfera só serve ao Clima geral. No caminho direcional o modelo
              a DESENHOU dentro da cena no teste, mesmo mandado não desenhar. */}
          {metodoLuz === 'clima' ? (
            <div className="campo">
              <label className="alternador">
                <input type="checkbox" checked={usarMapaLuz}
                       onChange={(e) => setUsarMapaLuz(e.target.checked)} />
                <span>Enviar a esfera como referência</span>
              
          <Ajuda>
            A frase acima é o que mais pesa no resultado. A esfera entra como
                reforço: nos testes o modelo lê bem a direção horizontal dela e só
                em parte a altura.
          </Ajuda>
        </label>
            </div>
          ) : (
            <p className="dica">
              No modo direcional a esfera não é enviada — o modelo segue a direção
              escrita, e mandar a imagem junto fazia ele desenhar a esfera dentro
              da cena. A posição que você escolhe continua valendo.
            </p>
          )}
        </>
      )}

      {ehControle && (
        <>
          <div className="campo">
            <label>O que seguir da referência</label>
            <div className="opcoes segmentado">
              {(m?.tipos ?? []).map((t) => (
                <button
                  key={t.id}
                  data-ativo={tipoControle === t.id}
                  onClick={() => { setTipoControle(t.id); setMapa(null) }}
                >
                  {t.rotulo}
                </button>
              ))}
            </div>
          </div>

          <div className="campo">
            <label style={{ textTransform: 'none', fontSize: 12 }}>
              Força do controle: {forcaControle.toFixed(2)}
            </label>
            <input type="range" min={0.1} max={2} step={0.05} value={forcaControle}
                   onChange={(e) => setForcaControle(Number(e.target.value))} />
          </div>

          <div className="campo">
            <button
              className="mini"
              style={{ width: '100%' }}
              disabled={!referencias.length || calculandoMapa}
              onClick={async () => {
                setCalculandoMapa(true)
                try {
                  const r = await api.previaControle(referencias[0].nome, tipoControle)
                  setMapa(urlImagem({ nome: r.nome, subpasta: r.subpasta }))
                } catch (e) {
                  aoErro(String(e))
                } finally {
                  setCalculandoMapa(false)
                }
              }}
            >
              {calculandoMapa ? 'Calculando…' : 'Ver o mapa de controle'}
            </button>
            {mapa && (
              <>
                <img src={mapa} alt="" className="previa-mapa" />
                <p className="dica" style={{ marginTop: 6, marginBottom: 0 }}>
                  É isto que o modelo vai seguir. Se o mapa estiver ruim, o
                  resultado também vai estar.
                </p>
              </>
            )}
          </div>
        </>
      )}

      {usaMascara && (
        <div className="campo">
          <label>Editar só em (opcional)
          <Ajuda>
            {mascaraAlvo.trim()
              ? 'O SAM 3 vai achar essa região. Tudo fora dela fica idêntico ao original, pixel a pixel.'
              : 'Em branco, o modelo pode alterar a imagem inteira. Preencha para conter a mudança numa região.'}
          </Ajuda>
        </label>
          <input
            value={mascaraAlvo}
            onChange={(e) => setMascaraAlvo(e.target.value)}
            placeholder="ex.: the jacket, o céu, the man on the left"
          />

          {mascaraAlvo.trim() !== '' && (
            <details className="avancado" style={{ marginTop: 10, marginBottom: 0 }}>
              <summary>Ajuste da máscara</summary>
              <div style={{ marginBottom: 10 }}>
                <label style={{ fontSize: 12, color: 'var(--apagado)' }}>
                  Sensibilidade: {limiar.toFixed(2)}
                </label>
                <input type="range" min={0.05} max={0.95} step={0.05}
                       value={limiar} onChange={(e) => setLimiar(Number(e.target.value))} />
              </div>
              <div style={{ marginBottom: 10 }}>
                <label style={{ fontSize: 12, color: 'var(--apagado)' }}>
                  Expandir: {expandir} px
                </label>
                <input type="range" min={-32} max={96} step={2}
                       value={expandir} onChange={(e) => setExpandir(Number(e.target.value))} />
              </div>
              <div>
                <label style={{ fontSize: 12, color: 'var(--apagado)' }}>
                  Suavizar borda: {suavizar} px
                
          <Ajuda>
            A máscara também limita a silhueta: pedir um casaco longo dentro
                do recorte de uma jaqueta curta dá um casaco curto. Aumente
                &quot;expandir&quot; para dar espaço à mudança crescer.
          </Ajuda>
        </label>
                <input type="range" min={0} max={96} step={2}
                       value={suavizar} onChange={(e) => setSuavizar(Number(e.target.value))} />
              </div>
            </details>
          )}
        </div>
      )}

      {ehEstilo && (
        <>
          <div className="campo">
            <label>Proporção</label>
            <div className="opcoes segmentado">
              {proporcoes.map((p) => (
                <button key={p} data-ativo={proporcao === p} onClick={() => setProporcao(p)}>
                  {p}
                </button>
              ))}
            </div>
          </div>
          <div className="campo">
            <label style={{ textTransform: 'none', fontSize: 12 }}>
              Força do estilo: {forcaEstilo.toFixed(2)}
            </label>
            <input
              type="range"
              min={0.1}
              max={1.5}
              step={0.05}
              value={forcaEstilo}
              onChange={(e) => setForcaEstilo(Number(e.target.value))}
            />
          </div>
        </>
      )}

      <div className="campo">
          <label>Variações
          <Ajuda>
            Repete a mesma edição com sementes diferentes. Em várias
            ferramentas a semente muda mais o resultado que qualquer ajuste —
            na migração de luz, a mesma entrada foi de quase nenhuma
            transferência até quase toda ela. Cada variação leva o tempo
            inteiro de novo.
          </Ajuda>
        </label>
          <div className="opcoes segmentado">
            {[1, 2, 3, 4].map((n) => (
              <button key={n} data-ativo={variacoes === n}
                      onClick={() => setVariacoes(n)}>
                {n === 1 ? 'Uma' : String(n)}
              </button>
            ))}
          </div>
      </div>

      {(modo === 'trocar' || ehAngulo || ehReluz) && (
        <div className="campo">
          {/* Uma bolinha por rotulo. A automacao tinha pendurado TRES aqui,
              porque tres paragrafos seguiam o mesmo </label> — e "? ? ?" lado
              a lado nao diz a ninguem qual e qual. O texto do nivel de pele
              desceu para junto dos botoes dele. */}
          <label>
            Freio do artefato
            <Ajuda titulo="Sobre o freio do artefato">
              Cada passagem pelo modelo deixa a textura mais gravada. O tipo
              escolhe <em>quais</em> defeitos combater — não são os mesmos num
              rosto e numa paisagem.
              {tiposImagem.find((x) => x.id === tipoImagem)?.nota && (
                <>
                  {' '}
                  <strong>{tiposImagem.find((x) => x.id === tipoImagem)?.rotulo}:</strong>{' '}
                  {tiposImagem.find((x) => x.id === tipoImagem)?.nota}
                </>
              )}
            </Ajuda>
          </label>

          <div className="opcoes">
            {tiposImagem.map((t) => (
              <button key={t.id} data-ativo={tipoImagem === t.id} title={t.nota}
                      onClick={() => setTipoImagem(t.id)}>
                {t.rotulo}
              </button>
            ))}
          </div>

          {tipoImagem !== 'manual' && (
            <>
              <p className="linha-ajuda">
                Nível
                <Ajuda titulo="Sobre o nível">
                  <strong>Moderado</strong> devolve a textura ao nível da imagem
                  original; <strong>forte</strong> vai além e pode alisar demais.
                </Ajuda>
              </p>
              <div className="opcoes segmentado">
                {niveisPele.map((n) => (
                  <button key={n.id} data-ativo={nivelPele === n.id}
                          onClick={() => setNivelPele(n.id)}>
                    {n.rotulo}
                  </button>
                ))}
              </div>
            </>
          )}

          {tipoImagem === 'manual' && (
            <>
              <textarea
                style={{ marginTop: 8, minHeight: 66 }}
                value={negativoManual}
                onChange={(e) => setNegativoManual(e.target.value)}
                placeholder="O que o modelo deve evitar. Ex.: over-sharpened, halo artifacts, plastic skin"
              />
              <p className="dica" style={{ marginTop: 6, marginBottom: 0 }}>
                Vale exatamente o que estiver escrito aqui — nada é acrescentado
                por cima. Em branco, o modelo fica sem freio nenhum.
              </p>
            </>
          )}
        </div>
      )}

      {!ehMagnific && <details className="avancado">
        <summary>Avançado</summary>
        <div className="linha">
          <div>
            <label style={{ fontSize: 12, color: 'var(--apagado)' }}>Seed</label>
            <input value={seed} onChange={(e) => setSeed(e.target.value)} placeholder="aleatória" />
          </div>
          <div>
            <label style={{ fontSize: 12, color: 'var(--apagado)' }}>Steps</label>
            <input value={steps} onChange={(e) => setSteps(e.target.value)} placeholder="padrão" />
          </div>
          {!ehEstilo && !ehCabeca && (
            <div>
              <label style={{ fontSize: 12, color: 'var(--apagado)' }}>CFG</label>
              <input value={cfg} onChange={(e) => setCfg(e.target.value)} placeholder="padrão" />
            </div>
          )}
        </div>
      </details>}

      <button className="principal" style={{ width: '100%' }} onClick={editar} disabled={!podeEditar}>
        {ehMagnific ? `Ampliar · ≈ US$ ${custoMagnific}` : ehAmpliar ? 'Ampliar' : ehAngulo ? 'Virar' : ehReluz ? 'Reiluminar'
          : ehPersonagem ? 'Trocar' : ehCabeca ? 'Trocar cabeça'
          : ehFolha ? 'Montar a folha'
          : usaMascara ? 'Editar' : 'Gerar'}
      </button>
    </>
  )
}
