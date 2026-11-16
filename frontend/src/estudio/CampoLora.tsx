import { useCallback, useEffect, useState } from 'react'

type Lista = { loras: string[]; familias: Record<string, string | null>; modelos: Record<string, string[]> }
const VAZIA: Lista = { loras: [], familias: {}, modelos: {} }
// LoRAs que nunca entram no modelo de imagem/video (de codificador de texto, embeddings soltos).
const FORA = new Set(['texto', 'nenhuma'])
const nomeBonito = (n: string) => n.replace(/[\\/]/g, ' / ').replace(/\.safetensors$/i, '')

/**
 * LoRA do usuario (abas Image, Video e Cinema): so com modelo local. A lista vem da
 * pasta models/loras do ComfyUI (/api/loras), com a familia de cada uma (lida do arquivo
 * pelo servidor). `modelo` e o id do modelo de imagem ou "video:<id>": o menu mostra
 * primeiro as feitas para ele, depois as nao reconhecidas; as de outros modelos so com
 * "Show all". Com `ativo` falso (nuvem, API, modo de referencia) nao manda nada.
 */
export function useLora(ativo: boolean, modelo: string) {
  const [lista, setLista] = useState<Lista>(VAZIA)
  const [lora, setLora] = useState('')
  const [forca, setForca] = useState(1)
  const [todas, setTodas] = useState(false)
  const buscar = useCallback(() => {
    fetch('/api/loras').then((r) => r.json()).then((d) => setLista({
      loras: Array.isArray(d.loras) ? d.loras : [], familias: d.familias ?? {}, modelos: d.modelos ?? {},
    })).catch(() => {})
  }, [])
  useEffect(() => { if (ativo) buscar() }, [ativo, buscar])

  const aceitas = new Set(lista.modelos[modelo] ?? [])
  const fam = (n: string) => lista.familias[n] ?? null
  const usaveis = lista.loras.filter((n) => !FORA.has(fam(n) ?? ''))
  const deste = usaveis.filter((n) => aceitas.has(fam(n) ?? ''))
  const desconhecidas = usaveis.filter((n) => fam(n) === null)
  const outras = usaveis.filter((n) => fam(n) !== null && !aceitas.has(fam(n) ?? ''))
  const visiveis = [...deste, ...desconhecidas, ...(todas ? outras : [])]
  const loraOk = ativo && visiveis.includes(lora) ? lora : ''
  const campos: { lora?: string; forca_lora?: number } = loraOk ? { lora: loraOk, forca_lora: forca } : {}
  const deOutro = !!loraOk && fam(loraOk) !== null && !aceitas.has(fam(loraOk) ?? '')

  const grupo = (rotulo: string, nomes: string[]) => nomes.length > 0 && (
    <optgroup label={rotulo}>{nomes.map((n) => <option key={n} value={n}>{nomeBonito(n)}</option>)}</optgroup>
  )
  const campo = ativo ? (
    <div className="hf-campo"><span>LoRA (optional)</span>
      <select className="hf-select" value={loraOk} onChange={(e) => setLora(e.target.value)} onFocus={buscar} aria-label="LoRA">
        <option value="">None</option>
        {grupo('Made for this model', deste)}
        {grupo('Unknown model (may not work)', desconhecidas)}
        {todas && grupo('Made for other models', outras)}
      </select>
      {outras.length > 0 && (
        <label className="hf-toggle">
          <input type="checkbox" checked={todas} onChange={(e) => setTodas(e.target.checked)} />
          Show all ({outras.length} for other models)
        </label>
      )}
      {loraOk ? (<>
        <span>Strength · {forca.toFixed(2)}</span>
        <input type="range" min={0} max={1.5} step={0.05} value={forca} aria-label="LoRA strength"
          onChange={(e) => setForca(Number(e.target.value))} />
        {deOutro
          ? <small className="hf-dica hf-dica-aviso">This LoRA was made for another model: it will probably fail or change nothing.</small>
          : <small className="hf-dica">Add its trigger word to the prompt if it has one.</small>}
      </>) : (
        <small className="hf-dica">{deste.length || desconhecidas.length ? "From ComfyUI's models/loras folder."
          : lista.loras.length ? 'No LoRA for this model in the loras folder.'
          : "No LoRAs found. Put .safetensors files in ComfyUI's models/loras folder."}</small>
      )}
    </div>
  ) : null

  return { campos, campo }
}
