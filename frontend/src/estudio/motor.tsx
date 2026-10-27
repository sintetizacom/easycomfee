import { createContext, useContext } from 'react'

// Where generations run, shared by every model menu. There is no Local / Cloud
// switch in the top bar any more: each menu has a "Local" group (open models
// installed here) and a "Comfy Cloud" group (open models hosted there and the
// paid "(API)" ones); picking an open model of the other group switches the engine.

export type Motor = 'local' | 'nuvem'

export const MotorCtx = createContext<{ naNuvem: boolean; temChave: boolean; instalados?: Set<string>; ocultarNaoInstalados?: boolean }>({ naNuvem: false, temChave: false })

/** The user's choice (Config Models > Local models): hide, instead of greying out, the models not installed. */
export const CHAVE_OCULTAR = 'openfield.ocultarNaoInstalados'

export async function trocarMotor(modo: Motor) {
  const r = await fetch('/api/motor', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ modo }),
  })
  const corpo = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(corpo.detail ?? 'Could not switch the engine.')
  window.dispatchEvent(new CustomEvent('motor-trocado', { detail: corpo.modo }))
}

type Item = { id: string; rotulo: string; nuvem?: boolean; soLocal?: boolean; soNuvem?: boolean; desligado?: boolean
  /** The tab knows it is not installed here (the menus that do not go by package). */
  naoInstalado?: boolean }

// Which install package (Config Models > Local models) each menu id needs.
// A model whose package is not installed does not show under "Local".
const PACOTE: Record<string, string | string[]> = {
  krea: 'krea2', kroma: 'kroma', flux3: 'flux3', klein: 'flux2_klein', qwen21: 'qwen21', zimage: 'zimage',
  mage: 'mage', ideogram: 'ideogram4', ltx: 'ltx25', minimax: 'minimax_h3', ltx23: 'avatar_ltx', h3_swap: 'h3_swap', wan22_replace: 'wan22_animate',
  // Recast: Qwen edits the first frame, then LTX 2.5 with the LTX 2.3 Union Control moves it.
  recast: ['ltx25', 'ltx23', 'qwen_edit'],
  // Modelos leves, para placas pequenas.
  flux1dev: 'flux1dev', flux1krea: 'flux1krea', flux2dev: 'flux2dev', hidream: 'hidream', chroma: 'chroma', sd35l: 'sd35l', kandinsky5i: 'kandinsky5i',
  flux1s: 'flux1s', sd35m: 'sd35m', sdxl: 'sdxl', sd15: 'sd15',
  ltxv2b: 'ltxv2b', fasth3: 'fasth3', wan22_14b: 'wan22_14b', hunyuan15: 'hunyuan15', kandinsky5: 'kandinsky5', wan22_5b: 'wan22_5b', wan21_13b: 'wan21_13b',
}

/** The value of a select option: "local:flux3", "nuvem:flux3". */
export function valorAberto(id: string, naNuvem: boolean) {
  return `${naNuvem ? 'nuvem' : 'local'}:${id}`
}

/** Two groups: "Local" (open models installed here) and "Comfy Cloud" (open
 *  models that exist there, plus the paid API ones marked "(API)"). */
export function GruposAbertos({ itens, api = [] }: { itens: Item[]; api?: { id: string; rotulo: string }[] }) {
  const { temChave, instalados, ocultarNaoInstalados } = useContext(MotorCtx)
  const precisa = (id: string) => ([] as string[]).concat(PACOTE[id] ?? [])
  const instalado = (m: Item) => !m.naoInstalado && (!instalados || precisa(m.id).every((p) => instalados.has(p)))
  // Not installed: greyed out with a hint, or hidden if the user asked for that.
  const local = itens.filter((m) => !m.soNuvem && (instalado(m) || !ocultarNaoInstalados))
  const nuvem = itens.filter((m) => !m.soLocal && m.nuvem !== false)
  return (
    <>
      {local.length > 0 && (
        <optgroup label="Local · your GPU">
          {local.map((m) => (
            <option key={'l' + m.id} value={`local:${m.id}`} disabled={m.desligado || !instalado(m)}>
              {m.rotulo}{instalado(m) ? '' : ' (install it in Config Models)'}
            </option>
          ))}
        </optgroup>
      )}
      {(temChave || api.length > 0) && (
        <optgroup label="Comfy Cloud · credits">
          {temChave && nuvem.map((m) => <option key={'n' + m.id} value={`nuvem:${m.id}`} disabled={m.desligado}>{m.rotulo}</option>)}
          {api.map((m) => <option key={m.id} value={m.id}>{m.rotulo.replace(/ \((API|nuvem)\)$/, '')} (API)</option>)}
        </optgroup>
      )}
    </>
  )
}

/** The handler for a model select: switches the engine when an open model of the other group is picked. */
export function useEscolha(aoMudar: (id: string) => void) {
  const { naNuvem } = useContext(MotorCtx)
  return async (v: string) => {
    const [motor, id] = v.includes(':') ? (v.split(':', 2) as [Motor, string]) : [null, v]
    aoMudar(id)
    if (motor && (motor === 'nuvem') !== naNuvem) {
      try { await trocarMotor(motor) } catch (e) { alert(String(e instanceof Error ? e.message : e)) }
    }
  }
}

/** The select value: open models carry the engine, API models their own id. */
export function useValor(id: string, ehApi: boolean) {
  const { naNuvem } = useContext(MotorCtx)
  return ehApi ? id : valorAberto(id, naNuvem)
}

/** Se os pacotes de um modelo (PACOTE) estao instalados neste computador. */
export function useInstalado() {
  const { instalados } = useContext(MotorCtx)
  return (id: string) => !instalados || ([] as string[]).concat(PACOTE[id] ?? []).every((p) => instalados.has(p))
}

/** Etiqueta "Your GPU" / "Cloud" dentro de um cartao de modelo: escolhe o modelo
 *  JA no motor indicado (o cartao em si e um botao, por isso isto e um span). */
export function Onde({ onde, ativo, falta, aoEscolher }: { onde: 'local' | 'nuvem'; ativo: boolean; falta?: boolean; aoEscolher: () => void }) {
  return (
    <span role="button" tabIndex={0} className="hf-onde" data-onde={onde} data-ativo={ativo} data-falta={!!falta}
      title={onde === 'local' ? (falta ? 'Not installed: install it in Config Models' : 'Run it on your GPU (free)') : 'Run it on Comfy Cloud (credits)'}
      onClick={(e) => { e.stopPropagation(); aoEscolher() }}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); aoEscolher() } }}>
      {onde === 'local' ? (falta ? 'Your GPU · not installed' : 'Your GPU') : 'Cloud'}
    </span>
  )
}

/** A linha "Run on" de um cartao de modelo: sempre embaixo, a opcao nao escolhida apagada. */
export function LinhaOnde({ id, cartaoAtivo, local, nuvem, faltaLocal, escolher }: {
  id: string; cartaoAtivo: boolean; local: boolean; nuvem: boolean; faltaLocal?: boolean
  /** O useEscolha da aba: escolhe o modelo E o motor ("local:id" / "nuvem:id"). */
  escolher: (v: string) => void
}) {
  const { naNuvem } = useContext(MotorCtx)
  if (!local && !nuvem) return null
  return (
    <span className="hf-linha-onde" data-cartao-ativo={cartaoAtivo}>
      <small>Run on</small>
      {local && <Onde onde="local" ativo={cartaoAtivo && !naNuvem} falta={faltaLocal} aoEscolher={() => escolher(`local:${id}`)} />}
      {nuvem && <Onde onde="nuvem" ativo={cartaoAtivo && naNuvem} aoEscolher={() => escolher(`nuvem:${id}`)} />}
    </span>
  )
}
