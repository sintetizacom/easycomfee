import { useEffect, useState } from 'react'
import { Chips } from './comum'

// Advanced: o proprio ComfyUI, com o editor de nodes, dentro do estudio.
// Mostra os motores do seu PC (o principal e, se instalado, o de video).

type MotorNos = { id: string; rotulo: string; url: string; vivo: boolean }

export default function AbaNodes() {
  const [motores, setMotores] = useState<MotorNos[] | null>(null)
  const [escolhido, setEscolhido] = useState('principal')
  const [versao, setVersao] = useState(0)

  const carregar = () => fetch('/api/nos').then((r) => r.json())
    .then((d) => setMotores(d.motores)).catch(() => setMotores([]))
  useEffect(() => { carregar() }, [])

  const atual = motores?.find((m) => m.id === escolhido) ?? motores?.[0]

  return (
    <div className="hf-nodes">
      <div className="hf-nodes-barra">
        <b>ComfyUI · nodes</b>
        {motores && motores.length > 1 && (
          <Chips rotulo="Engine" opcoes={motores.map((m) => ({ id: m.id, rotulo: m.rotulo + (m.vivo ? '' : ' · off') }))}
            valor={atual?.id ?? 'principal'} aoMudar={setEscolhido} />
        )}
        <button type="button" className="hf-botao-sec" onClick={() => { carregar(); setVersao((v) => v + 1) }}>Reload</button>
        {atual?.vivo && <a className="hf-botao-sec" href={atual.url} target="_blank" rel="noreferrer">Open in new window ↗</a>}
        <a className="hf-nodes-nuvem" href="https://cloud.comfy.org" target="_blank" rel="noreferrer">Comfy Cloud nodes ↗</a>
      </div>
      {!motores ? <p className="hf-dica hf-nodes-aviso">Looking for ComfyUI…</p>
        : !atual?.vivo ? (
          <p className="hf-dica hf-nodes-aviso">
            {atual?.id === 'video'
              ? 'The video engine is off. It starts by itself when you generate an LTX video or a YuE2 song; then press Reload.'
              : 'Your ComfyUI is not running. Start the app with iniciar.bat (it starts ComfyUI too), then press Reload.'}
          </p>
        ) : <iframe key={atual.id + versao} className="hf-nodes-quadro" src={atual.url} title="ComfyUI" />}
    </div>
  )
}
