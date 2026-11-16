import { useCallback, useEffect, useState } from 'react'

/**
 * LoRA do usuario (abas Image, Video e Cinema): so com modelo local. A lista vem da
 * pasta models/loras do ComfyUI (/api/loras). Devolve os campos do pedido e o campo
 * da tela; com `ativo` falso (nuvem, API, modo de referencia) nao manda nada.
 */
export function useLora(ativo: boolean, exemplo = "an SDXL LoRA won't work on Z-Image") {
  const [loras, setLoras] = useState<string[]>([])
  const [lora, setLora] = useState('')
  const [forca, setForca] = useState(1)
  const buscar = useCallback(() => {
    fetch('/api/loras').then((r) => r.json()).then((d) => setLoras(Array.isArray(d.loras) ? d.loras : [])).catch(() => {})
  }, [])
  useEffect(() => { if (ativo) buscar() }, [ativo, buscar])
  const loraOk = ativo && loras.includes(lora) ? lora : ''
  const campos: { lora?: string; forca_lora?: number } = loraOk ? { lora: loraOk, forca_lora: forca } : {}

  const campo = ativo ? (
    <div className="hf-campo"><span>LoRA (optional)</span>
      <select className="hf-select" value={loraOk} onChange={(e) => setLora(e.target.value)} onFocus={buscar} aria-label="LoRA">
        <option value="">None</option>
        {loras.map((n) => <option key={n} value={n}>{n.replace(/[\\/]/g, ' / ').replace(/\.safetensors$/i, '')}</option>)}
      </select>
      {loraOk ? (<>
        <span>Strength · {forca.toFixed(2)}</span>
        <input type="range" min={0} max={1.5} step={0.05} value={forca} aria-label="LoRA strength"
          onChange={(e) => setForca(Number(e.target.value))} />
        <small className="hf-dica">The LoRA must be made for this model ({exemplo}). Add its trigger word to the prompt if it has one.</small>
      </>) : (
        <small className="hf-dica">{loras.length ? "Your LoRAs from ComfyUI's models/loras folder." : "No LoRAs found. Put .safetensors files in ComfyUI's models/loras folder."}</small>
      )}
    </div>
  ) : null

  return { campos, campo }
}
