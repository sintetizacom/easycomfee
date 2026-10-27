import type { ReactNode } from 'react'
import Ajuda from './Ajuda'

export default function RotuloAjuda({ campo, rotulo, ajuda }: { campo: string; rotulo: ReactNode; ajuda: ReactNode }) {
  return <div className="rotulo-ajuda">
    <label htmlFor={campo}>{rotulo}</label>
    <Ajuda titulo={`Ajuda: ${typeof rotulo === 'string' ? rotulo : 'campo'}`}>{ajuda}</Ajuda>
  </div>
}
