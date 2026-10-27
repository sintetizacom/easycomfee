import { useState } from 'react'
import { MODOS_QUE_EDITAM, urlImagem, type ItemGaleria } from './api'

export type Acao = 'ampliar' | 'editar' | 'referencia' | 'variar' | 'personagem'

type Props = {
  item: ItemGaleria | null
  aoFechar: () => void
  aoReusar: (i: ItemGaleria) => void
  aoAgir: (acao: Acao, item: ItemGaleria) => void
  ocupado: boolean
  /** Catálogo de estilos, para mostrar o rótulo e não o id. */
  estilos: { id: string; rotulo: string; nota?: string }[]
  /** Os geradores de vídeo COMO O BACKEND os declara. Ver NOME_GERADOR. */
  geradoresVideo?: { id: string; rotulo: string }[]
}

const NOME_MODELO: Record<string, string> = {
  krea: 'Krea 2 Turbo',
  klein: 'Flux 2 Klein 9B',
  zimage: 'Z-Image Turbo',
  mage: 'Mage Flow',
  ideogram: 'Ideogram 4',
  trocar: 'Flux 2 Klein · troca',
  instrucao: 'Mage Flow · edição',
  estilo: 'Krea 2 · estilo',
  controle: 'Z-Image · estrutura',
  ampliar: 'Ampliação',
  angulo: 'Flux 2 Klein · ângulo',
  reluz: 'Flux 2 Klein · reiluminação',
}

function tamanho(bytes: number) {
  if (!bytes) return '—'
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

function duracao(s: number) {
  if (!s) return '—'
  if (s < 60) return `${s.toFixed(1)} s`
  const m = Math.floor(s / 60)
  return `${m} min ${Math.round(s % 60)} s`
}

function quando(t: number) {
  return new Date(t * 1000).toLocaleString('pt-BR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function Linha({ rotulo, children }: { rotulo: string; children: React.ReactNode }) {
  return (
    <div className="linha-info">
      <span>{rotulo}</span>
      <strong>{children}</strong>
    </div>
  )
}

function TituloCopiavel({ rotulo, texto, chave, copiado, aoCopiar }: {
  rotulo: React.ReactNode
  texto: string
  chave: string
  copiado: string
  aoCopiar: (texto: string, chave: string) => void
}) {
  const pronto = copiado === chave
  const nome = typeof rotulo === 'string' ? rotulo.toLocaleLowerCase('pt-BR') : 'texto'
  return (
    <div className="titulo-copiavel">
      <h3>{rotulo}</h3>
      <button
        type="button"
        className="copiar-texto"
        onClick={() => aoCopiar(texto, chave)}
        title={pronto ? 'Copiado' : `Copiar ${nome}`}
        aria-label={pronto ? `${nome} copiado` : `Copiar ${nome}`}
      >
        {pronto ? (
          <span aria-hidden="true">✓</span>
        ) : (
          <svg aria-hidden="true" viewBox="0 0 16 16">
            <rect x="5.25" y="2.25" width="8.5" height="9.5" rx="1.25" />
            <path d="M10.75 11.75v.5a1.5 1.5 0 0 1-1.5 1.5h-5.5a1.5 1.5 0 0 1-1.5-1.5v-6.5a1.5 1.5 0 0 1 1.5-1.5h1.5" />
          </svg>
        )}
      </button>
    </div>
  )
}

// Nomes legiveis para linhas ANTIGAS da galeria. Os geradores atuais vem
// do backend, em `geradoresVideo` — este mapa e so o que ele nao tem como
// declarar.
//
// Ele ja foi a unica fonte, e isso falhou DUAS vezes: o FastH3 e o "Varios
// planos" entraram no aplicativo e ninguem lembrou de acrescenta-los aqui,
// entao o campo "Gerador" mostrava "—" para os videos deles. O `?? '—'`
// engolia a falta sem reclamar.
//
// Por isso a ordem inverteu: o rotulo vivo vem primeiro, e um gerador novo
// passa a aparecer sozinho.
const NOME_GERADOR: Record<string, string> = {
  ltx: 'LTX 2.5 (local)',
  // O LTX e a rota PADRAO do backend: qualquer `modelo_video` que nao case
  // com os outros cai nele. Linhas antigas da galeria guardaram "video", que
  // e o nome do modelo, nao do gerador — sem esta entrada elas mostram "—".
  video: 'LTX 2.5 (local)',
  minimax: 'MiniMax H3 (local)',
  'minimax-nuvem': 'MiniMax H3 (nuvem)',
  'minimax-ref-nuvem': 'MiniMax H3 - MultiRef (nuvem)',
  wan3: 'Wan 3.0 (nuvem)',
}

/** O rótulo vivo do backend primeiro; o mapa fixo só para linhas antigas.
 *
 *  O último degrau é mostrar o PRÓPRIO identificador, não "—". Um traço diz
 *  "não há gerador", e havia: o `fasth3` estava gravado certinho no banco, e
 *  a tela escondeu isso por não ter o rótulo dele. Ver "fasth3" é feio e é
 *  verdade; ver "—" é bonito e é mentira.
 */
function nomeDoGerador(id: unknown,
                       vivos?: { id: string; rotulo: string }[]): string {
  const chave = String(id ?? '')
  if (!chave) return '—'
  return vivos?.find((g) => g.id === chave)?.rotulo ?? NOME_GERADOR[chave] ?? chave
}

const NOME_MODO: Record<string, string> = {
  texto: 'A partir de um texto',
  imagem: 'Animar uma imagem',
  primeiro_ultimo: 'Primeiro e último quadro',
  referencia: 'Por referências',
}

export default function PainelInfo({ item, aoFechar, aoReusar, aoAgir, ocupado,
                                    estilos, geradoresVideo }: Props) {
  const [copiado, setCopiado] = useState('')
  const [ocupadaAcao, setOcupadaAcao] = useState('')

  if (!item) {
    return (
      <aside className="info">
        <header>
          <h2>Informações</h2>
          <button className="mini" onClick={aoFechar}>×</button>
        </header>
        <p className="dica">Selecione uma imagem da galeria para ver os dados dela.</p>
      </aside>
    )
  }

  const p = item.parametros as Record<string, unknown>
  const copiar = (texto: string, qual: string) => {
    navigator.clipboard.writeText(texto).then(() => {
      setCopiado(qual)
      setTimeout(() => setCopiado(''), 1500)
    })
  }

  const endereco = urlImagem({ nome: item.arquivo, subpasta: item.subpasta })

  // Os modos que consomem uma imagem não guardam as referências na galeria,
  // então não dá para refazer a receita com outra seed.
  const naoGeraVariacao = MODOS_QUE_EDITAM.includes(item.modelo)

  const disparar = async (acao: Acao) => {
    setOcupadaAcao(acao)
    try {
      await aoAgir(acao, item)
    } finally {
      setOcupadaAcao('')
    }
  }

  const baixar = () => {
    const a = document.createElement('a')
    a.href = endereco
    a.download = item.arquivo
    document.body.appendChild(a)
    a.click()
    a.remove()
  }

  const copiarImagem = async () => {
    try {
      const blob = await (await fetch(endereco)).blob()
      await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })])
      setCopiado('imagem')
      setTimeout(() => setCopiado(''), 1500)
    } catch {
      // A área de transferência falha em contexto não seguro ou sem permissão.
      setCopiado('')
      baixar()
    }
  }

  const mp = (item.largura * item.altura) / 1e6
  // Video se reconhece pela duracao gravada, nao pela extensao: e o
  // dado que o backend mediu do arquivo.
  const ehAudio = ["voz", "musica"].includes(item.modelo)
  const ehVideo = !!item.duracao_video

  return (
    <aside className="info">
      <header>
        <h2>Informações</h2>
        <button className="mini" onClick={aoFechar}>×</button>
      </header>

      <section>
        {/* O rótulo, quando existe, diz o que o id do modo não diz — é o
            caso das comparações lado a lado. */}
        {/* No video esta linha diria so "video", e o que interessa e QUAL
            gerador — mostrado logo abaixo. */}
        {!ehVideo && !ehAudio && (
          <Linha rotulo="Modelo">
            {item.rotulo ?? NOME_MODELO[item.modelo] ?? item.modelo}
          </Linha>
        )}
        {item.modelo === "voz" && <Linha rotulo="Modelo">OmniVoice · áudio local</Linha>}
        {!ehAudio && <Linha rotulo="Resolução">
          {item.largura && item.altura
            ? `${item.largura} × ${item.altura}${mp ? ` · ${mp.toFixed(1)} MP` : ''}`
            : '—'}
        </Linha>}
        {/* Video: duracao e cadencia sao o que o distingue de uma imagem.
            Medidas do ARQUIVO, nao do pedido. */}
        {!!item.duracao_video && (
          <Linha rotulo="Duração">
            {item.duracao_video.toFixed(2)} s · {item.fps ?? 24} fps
          </Linha>
        )}
        <Linha rotulo="Tempo">{duracao(item.duracao)}</Linha>
        <Linha rotulo="Arquivo">{tamanho(item.bytes)}</Linha>
        {/* So aparece quando houve custo: nos modelos locais a linha seria
            sempre "US$ 0,00", que e ruido. O valor e MEDIDO pela diferenca de
            saldo, nao a tabela do provedor — a tabela erra alguns por cento. */}
        {!!item.custo_usd && (
          <Linha rotulo="Custo">US$ {item.custo_usd.toFixed(4)}</Linha>
        )}
        <Linha rotulo="Gerada em">{quando(item.criada_em)}</Linha>
      </section>

      <section>
        <Linha rotulo="Seed">
          <button className="mini" onClick={() => copiar(String(p.seed ?? ''), 'seed')}>
            {copiado === 'seed' ? 'copiado' : String(p.seed ?? '—')}
          </button>
        </Linha>
        {/* No video o tamanho vem em pixels; a `proporcao` do pedido e um
            valor de preenchimento e mostra-la seria mentir. */}
        {!ehVideo && !ehAudio && <Linha rotulo="Proporção">{String(p.proporcao ?? '—')}</Linha>}
        {/* Só aparece quando o registro tem o campo: as imagens gravadas antes
            de o banco guardar o pedido inteiro não o têm, e uma linha com "—"
            ali sugeriria que nenhum estilo foi usado, o que seria mentira. */}
        {!ehAudio && p.estilo != null && (
          <Linha rotulo="Estilo">
            {p.estilo === 'manual'
              ? String(p.estilo_manual || 'manual (vazio)')
              : (estilos.find((e) => e.id === p.estilo)?.rotulo ?? String(p.estilo))}
          </Linha>
        )}
        {!ehAudio && p.expandir_prompt != null && (
          <Linha rotulo="Prompt expandido">
            {p.expandir_prompt
              ? `sim · ${p.modo_expansao === 'livre' ? 'Livre' : 'Fiel'}`
              : 'não'}
          </Linha>
        )}
        {ehAudio ? (
          <>
            {item.modelo === 'musica' ? <>
              <Linha rotulo="Modelo">{{"minimax-music3": "MiniMax Music 3", "stable-audio3": "Stable Audio 3", "ace-step15": "ACE-Step 1.5 Turbo"}[String(p.modelo_musica)] ?? String(p.modelo_musica)}</Linha>
              {Boolean(p.projeto_musica) && <Linha rotulo="Projeto / Artista">{String(p.projeto_musica)}</Linha>}
              {Boolean(p.titulo_musica) && <Linha rotulo="Música">{String(p.titulo_musica)}</Linha>}
              <Linha rotulo="Tipo">{p.vocal_musica ? 'Com letra' : 'Instrumental'}</Linha>
              {p.modelo_musica === 'ace-step15' && <Linha rotulo="Tonalidade">{String(p.tonalidade_musica ?? 'C major')}</Linha>}
              {p.modelo_musica === 'ace-step15' && p.vocal_musica && <Linha rotulo="Gênero vocal">{{livre:'Sem preferência', feminino:'Feminino', masculino:'Masculino'}[String(p.genero_vocal_musica ?? 'livre')] ?? String(p.genero_vocal_musica)}</Linha>}
              <Linha rotulo="Duração solicitada">{String(p.duracao_musica)} s</Linha>
              {Boolean(p.referencia_musica) && <><Linha rotulo="Composição guia">{String(p.referencia_musica)}</Linha><Linha rotulo="Transformação">{Math.round(Number(p.transformacao_musica ?? .75)*100)}%</Linha></>}
              {!!p.finalizacao_musica && <>
                <Linha rotulo="Versão">{String((p.finalizacao_musica as Record<string, unknown>).versao)}</Linha>
                <Linha rotulo="Duração do áudio">{String((p.finalizacao_musica as Record<string, unknown>).versao === 'Original' ? (p.finalizacao_musica as Record<string, unknown>).duracao_original : (p.finalizacao_musica as Record<string, unknown>).duracao_final)} s</Linha>
                <Linha rotulo="Encerramento">{String((p.finalizacao_musica as Record<string, unknown>).motivo)}</Linha>
              </>}
              {p.letra_musica && p.vocal_musica ? <Linha rotulo="Letra">{String(p.letra_musica)}</Linha> : null}
            </> : <>
            <Linha rotulo="Modo">{p.modo_voz === 'clonar' ? 'Voz de referência' : p.modo_voz === 'criar' ? 'Criar voz' : 'Narração'}</Linha>
            {Boolean(p.nome_voz) && <Linha rotulo="Voz">{String(p.nome_voz)}</Linha>}
            {Boolean(p.titulo_audio_voz) && <Linha rotulo="Título do áudio">{String(p.titulo_audio_voz)}</Linha>}
            <Linha rotulo="Idioma">{String(p.idioma_voz ?? "Portuguese")}</Linha>
            <Linha rotulo="Velocidade">{Number(p.velocidade_voz ?? 1).toFixed(2)}×</Linha>
            <Linha rotulo="Passos">{String(p.passos_voz ?? 32)}</Linha>
            </>}
          </>
        ) : ehVideo ? (
          <>
            {/* Qual gerador fez este video. Com quatro deles, "modelo: video"
                na linha de cima nao diz nada — o que importa e se foi LTX,
                MiniMax ou Wan. */}
            <Linha rotulo="Gerador">{nomeDoGerador(p.modelo_video, geradoresVideo)}</Linha>
            {/* Nos modos de referencia, QUAIS fotos entraram e a informacao
                mais util para repetir o resultado — e era justamente a que se
                perdia. O nome do envio traz um prefixo tecnico
                (`ref_<uuid>_`); aqui mostra-se so o nome original. */}
            {Array.isArray(p.referencias_usadas) && p.referencias_usadas.length > 0 && (
              <Linha rotulo={p.referencias_usadas.length === 1 ? 'Referência' : 'Referências'}>
                {(p.referencias_usadas as string[])
                  .map((r) => String(r).replace(/^ref_[0-9a-f]{12}_/, ''))
                  .join(', ')}
              </Linha>
            )}
            {p.modelo_video === 'minimax' && (
              <Linha rotulo="Turbo">{p.turbo === false ? 'não' : 'sim'}</Linha>
            )}
            {p.modelo_video === 'minimax' && p.modo_video === 'referencia' && (
              <Linha rotulo="Detalhe das refs">
                {p.tamanho_referencia === 'max' ? 'máximo' : 'compatível'}
              </Linha>
            )}
            {p.modelo_video === 'wan3' && (
              <Linha rotulo="Variante">
                {String(p.variante_video ?? '').includes('prime') ? 'Prime' : 'Padrão'}
              </Linha>
            )}
            <Linha rotulo="Com som">{p.com_audio === false ? 'não' : 'sim'}</Linha>
            <Linha rotulo="Modo">{NOME_MODO[String(p.modo_video ?? '')] ?? String(p.modo_video ?? '—')}</Linha>
          </>
        ) : item.modelo === 'ideogram' ? (
          <Linha rotulo="Qualidade">{String(p.qualidade ?? '—')}</Linha>
        ) : (
          <>
            <Linha rotulo="Steps">{p.steps == null ? 'padrão' : String(p.steps)}</Linha>
            <Linha rotulo="CFG">{p.cfg == null ? 'padrão' : String(p.cfg)}</Linha>
          </>
        )}
        {Number(p.escala ?? 1) !== 1 && (
          <Linha rotulo="Escala">{Number(p.escala).toFixed(2)}×</Linha>
        )}
      </section>

      <section>
        <TituloCopiavel
          rotulo={<>
            {item.modelo === "voz" ? "Texto falado" : item.modelo === "musica" ? "Descrição da música" : "Prompt"}
            {Boolean(p.expandiu_prompt) && <em> · enriquecido</em>}
          </>}
          texto={item.prompt}
          chave="prompt"
          copiado={copiado}
          aoCopiar={copiar}
        />
        <p className="texto-info">{item.prompt}</p>
        {/* Duas chaves: `expandiu_prompt` nas imagens antigas, `expandir_prompt`
            nas novas. Ler só a nova deixaria de mostrar o prompt expandido
            das antigas; ler só a velha — que foi o que aconteceu — deixa de
            mostrar o das novas. */}
        {Boolean(p.expandiu_prompt ?? p.expandir_prompt)
          && item.prompt_final !== item.prompt && (
          <>
            <TituloCopiavel
              rotulo="Enviado ao modelo"
              texto={item.prompt_final}
              chave="prompt-final"
              copiado={copiado}
              aoCopiar={copiar}
            />
            <p className="texto-info">{item.prompt_final}</p>
          </>
        )}
        {Boolean(p.negativo) && (
          <>
            <TituloCopiavel
              rotulo="Negativo"
              texto={String(p.negativo)}
              chave="negativo"
              copiado={copiado}
              aoCopiar={copiar}
            />
            <p className="texto-info">{String(p.negativo)}</p>
          </>
        )}
      </section>

      {item.caption && (
        <section>
          <h3>Layout ({item.caption.compositional_deconstruction.elements.length} elementos)</h3>
          <p className="texto-info">{item.caption.compositional_deconstruction.background}</p>
          <details>
            <summary>JSON completo</summary>
            <pre className="json-info">{JSON.stringify(item.caption, null, 1)}</pre>
          </details>
        </section>
      )}

      <section>
        <h3>Ações</h3>
        <div className="grade-acoes">
          {/* Ampliar, editar e usar como referencia sao ferramentas de IMAGEM:
              todas mandariam o mp4 para um no que espera um PNG. Ficam fora em
              vez de desabilitadas — botao que nunca funciona so convida ao
              clique. */}
          {!ehVideo && !ehAudio && (
            <>
              <button disabled={ocupado || !!ocupadaAcao}
                      onClick={() => disparar('ampliar')}>
                {ocupadaAcao === 'ampliar' ? '…' : 'Ampliar 2×'}
              </button>
              <button disabled={ocupado || !!ocupadaAcao}
                      onClick={() => disparar('editar')}>
                {ocupadaAcao === 'editar' ? '…' : 'Editar isto'}
              </button>
              <button disabled={ocupado || !!ocupadaAcao}
                      onClick={() => disparar('referencia')}>
                {ocupadaAcao === 'referencia' ? '…' : 'Usar como referência'}
              </button>
              <button disabled={!!ocupadaAcao} onClick={() => disparar('personagem')}>
                {ocupadaAcao === 'personagem' ? '…' : 'Usar como personagem'}
              </button>
            </>
          )}
          <button
            disabled={ocupado || !!ocupadaAcao || naoGeraVariacao || ehAudio}
            title={naoGeraVariacao
              ? 'Variação só existe para imagens geradas a partir de um prompt.'
              : 'Mesma receita, seed nova'}
            onClick={() => disparar('variar')}
          >
            Variar
          </button>
        </div>
      </section>

      <section className="acoes-info">
        <div className="linha">
          <button onClick={baixar}>Baixar</button>
          {/* A area de transferencia nao aceita video; copiar so vale para
              imagem. Baixar funciona nos dois. */}
          {!ehVideo && !ehAudio && (
            <button onClick={copiarImagem}>
              {copiado === 'imagem' ? 'Copiada' : 'Copiar imagem'}
            </button>
          )}
        </div>
        <button onClick={() => aoReusar(item)}>Reusar parâmetros</button>
        <button
          onClick={() => copiar(
            `${item.arquivo}\n${NOME_MODELO[item.modelo] ?? item.modelo} · ${item.largura}×${item.altura} · seed ${p.seed}\n${item.prompt_final}`,
            'tudo')}
        >
          {copiado === 'tudo' ? 'Copiado' : 'Copiar resumo'}
        </button>
      </section>

      <p className="dica" style={{ margin: 0 }}>{item.subpasta}/{item.arquivo}</p>
    </aside>
  )
}
