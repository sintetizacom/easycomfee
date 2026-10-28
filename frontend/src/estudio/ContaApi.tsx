import { useEffect, useState } from 'react'
import { api } from '../api'
import { textoDoDetalhe } from './comum'

// "Comfy Cloud API" tab of Config Models: the key, the balance and whether the
// paid API models show up in the menus. The key is typed by the user and goes
// straight to backend/chaves.json; the backend never sends it back.

type Saldo = Awaited<ReturnType<typeof api.saldoNuvem>>

export default function ContaApi({ temChave, soAbertos, linkRecarga, aoMudar }: {
  temChave: boolean; soAbertos: boolean; linkRecarga?: string; aoMudar: () => void
}) {
  const [saldo, setSaldo] = useState<Saldo | null>(null)
  const [chave, setChave] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [salvando, setSalvando] = useState(false)

  useEffect(() => { if (temChave) api.saldoNuvem(true).then(setSaldo).catch(() => setSaldo(null)) }, [temChave])

  const salvar = async (valor: string) => {
    setSalvando(true); setErro(null)
    try {
      const r = await fetch('/api/nuvem/chave', { method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chave: valor }) })
      const corpo = await r.json()
      if (!r.ok) throw new Error(textoDoDetalhe(corpo.detail, 'Could not save the key.'))
      setChave('')
      setSaldo(corpo.saldo)
      if (valor && corpo.saldo && !corpo.saldo.ok) setErro(`Saved, but Comfy did not accept it: ${corpo.saldo.motivo ?? 'unknown reason'}`)
      aoMudar()
    } catch (e) { setErro(e instanceof Error ? e.message : String(e)) } finally { setSalvando(false) }
  }

  const abertos = async (valor: boolean) => {
    await fetch('/api/abertos', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ valor }) })
    aoMudar()
  }

  return (
    <>
      <section className="mq-cartao">
        <span className="mq-rotulo">Comfy API key</span>
        <p className="mq-sub">
          One key for Comfy Cloud GPUs and the paid API models. Create it at{' '}
          <a href="https://platform.comfy.org/profile/api-keys" target="_blank" rel="noreferrer">platform.comfy.org</a>.
          It stays on this computer and is never shown again.
        </p>
        {/* A Comfy nao oferece "entrar com a Comfy" para apps de fora: o acesso e
            pela chave. O botao abre a pagina onde a pessoa entra e cria a chave. */}
        {!temChave && (
          <ol className="mq-passos">
            <li><a className="mq-botao" href="https://platform.comfy.org/profile/api-keys" target="_blank" rel="noreferrer">Sign in to Comfy and create a key ↗</a></li>
            <li>Copy the key it shows (starts with <code>comfyui-</code>).</li>
            <li>Paste it below and press Save.</li>
          </ol>
        )}
        <form className="mq-acoes" onSubmit={(e) => { e.preventDefault(); if (chave.trim()) salvar(chave) }}>
          <input className="mq-token" type="password" autoComplete="off" value={chave} onChange={(e) => setChave(e.target.value)}
            aria-label="Comfy Cloud API key"
            placeholder={temChave ? 'Key saved. Paste a new one to replace it' : 'comfyui-…'} />
          <button type="submit" className="mq-botao" disabled={!chave.trim() || salvando}>{salvando ? 'Saving…' : 'Save'}</button>
          {temChave && <button type="button" className="mq-botao-sec" onClick={() => salvar('')}>Remove</button>}
        </form>
        {erro && <p className="mq-aviso erro">{erro}</p>}
      </section>

      {temChave && (
        <section className="mq-cartao mq-resumo">
          <div>
            <span className="mq-rotulo">Balance</span>
            <p className="mq-linha">
              {saldo?.ok && saldo.usd != null ? `$${saldo.usd.toFixed(2)} available` : saldo ? `Unavailable: ${saldo.motivo ?? ''}` : 'Reading…'}
              {saldo?.gasto && saldo.gasto.usd > 0 && ` · $${saldo.gasto.usd.toFixed(2)} spent in this app`}
            </p>
          </div>
          {linkRecarga && <a className="mq-botao-sec" href={linkRecarga} target="_blank" rel="noreferrer">Top up ↗</a>}
        </section>
      )}

      <section className="mq-cartao">
        <span className="mq-rotulo">Paid API models</span>
        <label className="mq-check">
          <input type="checkbox" checked={!soAbertos} onChange={(e) => abertos(!e.target.checked)} />
          <span>Show Kling, Seedance, Veo, Nano Banana and the other paid models in the menus (they use your Comfy credits).</span>
        </label>
        <p className="mq-sub">Open-weight models run free on your GPU or on Comfy Cloud: pick where in each model menu.</p>
      </section>
    </>
  )
}
