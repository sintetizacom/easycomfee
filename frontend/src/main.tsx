import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import Estudio from './estudio/Estudio'
import './estilo.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Estudio />
  </StrictMode>,
)
