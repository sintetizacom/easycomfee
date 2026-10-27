import { useState } from 'react'
import { MODOS_QUE_EDITAM, urlImagem, urlMiniatura, type ItemGaleria } from './api'
import { FILTROS_GALERIA, type FiltroGaleria } from './filtrosGaleria'
import type { Acao } from './PainelInfo'

export type LayoutGaleria = 'grade' | 'lista'

type Props = {
  itens: ItemGaleria[]
  total: number
  layout: LayoutGaleria
  selecionado: number | null
  filtro: FiltroGaleria
  aoMudarLayout: (layout: LayoutGaleria) => void
  aoMudarFiltro: (filtro: FiltroGaleria) => void
  aoSelecionar: (item: ItemGaleria) => void
  aoAbrir: (item: ItemGaleria) => void
  /** As MESMAS acoes do painel de informacoes — nao uma segunda versao delas. */
  aoAgir: (acao: Acao, item: ItemGaleria) => void
  aoReusar: (item: ItemGaleria) => void
  aoApagar: (item: ItemGaleria) => void
}

function tipoDoItem(item: ItemGaleria) {
  if (item.modelo === 'voz') return 'Voz'
  if (item.modelo === 'musica') return 'Música'
  if (item.duracao_video) return 'Vídeo'
  return 'Imagem'
}

function dataDoItem(segundos: number) {
  return new Date(segundos * 1000).toLocaleString('pt-BR', {
    day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

/* Icones em SVG embutido: nitidos em qualquer escala e sem depender de fonte
   de emoji, que muda de desenho entre Windows e navegadores. */
const ICONE = {
  referencia: 'M8 8h11v11H8zM5 16V5h11',
  apagar: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6',
  baixar: 'M12 4v11M7 10l5 5 5-5M5 20h14',
  mais: 'M12 5.5v.01M12 12v.01M12 18.5v.01',
  editar: 'M4 20h4L19 9l-4-4L4 16zM14 6l4 4',
  recriar: 'M20 12a8 8 0 1 1-2.3-5.6M20 4v5h-5',
  seta: 'M7 10l5 5 5-5',
}

function Icone({ d }: { d: string }) {
  return (
    <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  )
}

function baixar(item: ItemGaleria) {
  const a = document.createElement('a')
  a.href = urlImagem({ nome: item.arquivo, subpasta: item.subpasta })
  a.download = item.arquivo
  document.body.appendChild(a)
  a.click()
  a.remove()
}

export default function GaleriaCentral({ itens, total, layout, selecionado,
  filtro, aoMudarLayout, aoMudarFiltro, aoSelecionar, aoAbrir,
  aoAgir, aoReusar, aoApagar }: Props) {
  // Um menu aberto por vez, identificado pelo item e por qual dos dois menus.
  const [menu, setMenu] = useState<{ id: number; qual: 'mais' | 'recriar' } | null>(null)

  return (
    <section className="navegador-galeria">
      <header className="topo-navegador-galeria">
        <div>
          <h2>Criações</h2>
          <span>{itens.length === total ? `${total} itens` : `${itens.length} de ${total}`}</span>
        </div>
        <div className="acoes-navegador-galeria">
          <div className="filtros-centrais" role="group" aria-label="Filtrar criações por tipo">
            {FILTROS_GALERIA.map((opcao) => (
              <button
                key={opcao.id}
                type="button"
                data-ativo={filtro === opcao.id}
                aria-pressed={filtro === opcao.id}
                onClick={() => aoMudarFiltro(opcao.id)}
              >
                {opcao.rotulo}
              </button>
            ))}
          </div>
          <div className="escolha-layout" role="group" aria-label="Modo de visualização">
            <button
              type="button"
              data-ativo={layout === 'grade'}
              aria-pressed={layout === 'grade'}
              onClick={() => aoMudarLayout('grade')}
              title="Visualização em grade"
            >
              <span aria-hidden="true">▦</span> Grade
            </button>
            <button
              type="button"
              data-ativo={layout === 'lista'}
              aria-pressed={layout === 'lista'}
              onClick={() => aoMudarLayout('lista')}
              title="Visualização em lista"
            >
              <span aria-hidden="true">☷</span> Lista
            </button>
          </div>
        </div>
      </header>

      {itens.length === 0 ? (
        <div className="galeria-central-vazia">
          <span aria-hidden="true">◇</span>
          <strong>Nenhuma criação neste filtro</strong>
          <p>Escolha outro tipo de mídia na barra da galeria.</p>
        </div>
      ) : (
        <div className="itens-galeria-central" data-layout={layout}>
          {itens.map((item) => {
            const audio = item.modelo === 'voz' || item.modelo === 'musica'
            const video = !!item.duracao_video
            const rotulo = item.rotulo ?? tipoDoItem(item)
            // Mesmas regras do painel de informacoes. Ampliar, editar e usar
            // como referencia sao ferramentas de IMAGEM: com video ou audio
            // mandariam o arquivo para um no que espera um PNG. Variar nao
            // vale para audio nem para o que saiu de uma edicao, cuja receita
            // depende de referencias que a galeria nao guarda.
            const ehImagem = !audio && !video
            const podeVariar = ehImagem && !MODOS_QUE_EDITAM.includes(item.modelo)
            const aberto = menu?.id === item.id ? menu.qual : null

            // Os botoes vivem DENTRO do cartao, que seleciona no clique e abre
            // no duplo clique. Sem parar a propagacao, apagar tambem
            // selecionaria o item e baixar o abriria.
            const acao = (f: () => void) => (e: React.MouseEvent) => {
              e.stopPropagation()
              setMenu(null)
              f()
            }
            const alternar = (qual: 'mais' | 'recriar') => (e: React.MouseEvent) => {
              e.stopPropagation()
              setMenu(aberto === qual ? null : { id: item.id, qual })
            }

            return (
              <article
                key={item.id}
                className="cartao-galeria-central"
                data-ativo={selecionado === item.id}
                data-menu={aberto ? 'aberto' : undefined}
                tabIndex={0}
                aria-label={`${rotulo}. Clique duas vezes para abrir.`}
                onClick={() => aoSelecionar(item)}
                onDoubleClick={() => aoAbrir(item)}
                onMouseLeave={() => aberto && setMenu(null)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') aoAbrir(item)
                  if (e.key === 'Escape') setMenu(null)
                }}
              >
                <div className="midia-cartao">
                  {audio ? (
                    <div className="icone-audio-cartao" aria-hidden="true">
                      <span>{item.modelo === 'musica' ? '♫' : '◖))'}</span>
                    </div>
                  ) : (
                    <img
                      src={urlMiniatura({ nome: item.arquivo, subpasta: item.subpasta })}
                      loading="lazy"
                      alt=""
                    />
                  )}
                  <span className="tipo-cartao">{tipoDoItem(item)}</span>
                  {!!item.duracao_video && (
                    <span className="duracao-cartao">{item.duracao_video.toFixed(1)} s</span>
                  )}

                  <div className="acoes-cartao topo">
                    {ehImagem && (
                      <button type="button" title="Usar como referência"
                              aria-label="Usar como referência"
                              onClick={acao(() => aoAgir('referencia', item))}>
                        <Icone d={ICONE.referencia} />
                      </button>
                    )}
                    <div className="menu-cartao">
                      <button type="button" title="Mais ações" aria-label="Mais ações"
                              aria-expanded={aberto === 'mais'}
                              onClick={alternar('mais')}>
                        <Icone d={ICONE.mais} />
                      </button>
                      {aberto === 'mais' && (
                        <div className="lista-menu-cartao" role="menu">
                          {ehImagem && (
                            <button type="button" role="menuitem"
                                    onClick={acao(() => aoAgir('ampliar', item))}>
                              Ampliar 2×
                            </button>
                          )}
                          <button type="button" role="menuitem"
                                  onClick={acao(() => aoReusar(item))}>
                            Reusar parâmetros
                          </button>
                          <button type="button" role="menuitem"
                                  onClick={acao(() => aoAbrir(item))}>
                            Abrir
                          </button>
                        </div>
                      )}
                    </div>
                    <button type="button" title="Remover da galeria"
                            aria-label="Remover da galeria"
                            onClick={acao(() => aoApagar(item))}>
                      <Icone d={ICONE.apagar} />
                    </button>
                    <button type="button" title="Baixar" aria-label="Baixar"
                            onClick={acao(() => baixar(item))}>
                      <Icone d={ICONE.baixar} />
                    </button>
                  </div>

                  <div className="acoes-cartao base">
                    {ehImagem && (
                      <button type="button" title="Editar" aria-label="Editar"
                              onClick={acao(() => aoAgir('editar', item))}>
                        <Icone d={ICONE.editar} />
                      </button>
                    )}
                    <div className="menu-cartao recriar">
                      {/* Recriar = mesma receita, seed nova. Onde nao ha como
                          recriar com um clique, o botao principal reabre a
                          receita no formulario para a pessoa conferir antes. */}
                      <button type="button" className="principal"
                              title={podeVariar ? 'Mesma receita, seed nova'
                                : 'Reabre a receita no formulário'}
                              onClick={acao(() => (podeVariar ? aoAgir('variar', item)
                                : aoReusar(item)))}>
                        <Icone d={ICONE.recriar} />
                        <span>{podeVariar ? 'Recriar' : 'Reusar'}</span>
                      </button>
                      {podeVariar && (
                        <button type="button" className="seta" title="Mais opções"
                                aria-label="Mais opções de recriar"
                                aria-expanded={aberto === 'recriar'}
                                onClick={alternar('recriar')}>
                          <Icone d={ICONE.seta} />
                        </button>
                      )}
                      {aberto === 'recriar' && (
                        <div className="lista-menu-cartao para-cima" role="menu">
                          <button type="button" role="menuitem"
                                  onClick={acao(() => aoAgir('variar', item))}>
                            Recriar com seed nova
                          </button>
                          <button type="button" role="menuitem"
                                  onClick={acao(() => aoReusar(item))}>
                            Ajustar antes de recriar
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
                <div className="dados-cartao">
                  <strong>{rotulo}</strong>
                  <p>{item.prompt || item.arquivo}</p>
                  <div>
                    <span>{dataDoItem(item.criada_em)}</span>
                    {item.largura > 0 && item.altura > 0 && (
                      <span>{item.largura} × {item.altura}</span>
                    )}
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
