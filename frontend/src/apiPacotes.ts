// Cliente da tela Modelos: catalogo de pacotes, instalacao e progresso.

export type ArquivoPacote = {
  arquivo: string
  subpasta: string
  repo: string
  /** O repositorio exige login no Hugging Face e o aceite da licenca. */
  requer_aceite: boolean
  sem_origem?: boolean
  rotulo: string
  pasta: string
  tamanho: number
  opcional: boolean
  /** null quando o motor nao respondeu e nao da para saber. */
  instalado: boolean | null
  url: string
}

export type Pacote = {
  id: string
  nome: string
  tipo: string
  descricao: string
  vram_min_gb: number
  licenca: { nome: string; url: string; comercial: string }
  nuvem: string
  arquivos: ArquivoPacote[]
  pronto: boolean | null
  tamanho_total: number
  tamanho_faltando: number
  /** Arquivos sem origem publica: a pessoa coloca na pasta a mao. */
  manual: string[]
  modos: string[]
  /** Nos extras do ComfyUI que este pacote usa (base + proprios). */
  nos: { nome: string; instalado: boolean | null }[]
  requisitos: { vram_min: number; vram_rec: number; ram_min?: number; medido?: string; nota_limitado?: string }
  nesta_maquina: { selo: 'bem' | 'limitado' | 'nao_roda' | 'sem_perfil' | 'nuvem'; motivo?: string; sem_espaco?: boolean; medido?: string }
}

export type PerfilMaquina = { gpu: string; vram_gb: number; ram_gb: number; so_nuvem: boolean }
export type Detectado = { gpu: string | null; vram_gb: number | null; ram_gb: number | null; disco_livre_gb: number | null; fonte: string | null }

export type ProgressoInstalacao = {
  pacote: string | null
  ativo: boolean
  arquivo: string | null
  baixado: number
  total: number
  feitos: number
  quantos: number
  velocidade: number
  erro: string | null
  repo_recusado: string | null
}

async function pedir<T>(caminho: string, opcoes?: RequestInit): Promise<T> {
  const r = await fetch(caminho, { headers: { 'Content-Type': 'application/json' }, ...opcoes })
  if (!r.ok) {
    const corpo = await r.text()
    let frase = corpo
    try { frase = JSON.parse(corpo).detail ?? corpo } catch { /* texto puro */ }
    throw new Error(frase || `falha em ${caminho}`)
  }
  return r.json() as Promise<T>
}

export const apiPacotes = {
  listar: () => pedir<{ motor_respondendo: boolean; pacotes: Pacote[]; maquina: PerfilMaquina | null }>('/api/pacotes'),
  maquina: () => pedir<{ detectado: Detectado; salvo: PerfilMaquina | null }>('/api/maquina'),
  salvarMaquina: (perfil: PerfilMaquina) =>
    pedir<PerfilMaquina>('/api/maquina', { method: 'POST', body: JSON.stringify(perfil) }),
  instalar: (id: string, opcionais: boolean) =>
    pedir<{ arquivos: number; bytes: number }>(`/api/pacotes/${id}/instalar`, {
      method: 'POST',
      body: JSON.stringify({ opcionais }),
    }),
  progresso: () => pedir<ProgressoInstalacao>('/api/pacotes/progresso'),
  token: () => pedir<{ configurado: boolean; final: string | null }>('/api/pacotes/token'),
  salvarToken: (token: string) =>
    pedir<{ configurado: boolean; final: string | null }>('/api/pacotes/token', {
      method: 'POST',
      body: JSON.stringify({ token }),
    }),
  progressoNos: () =>
    pedir<{ progresso: { ativo: boolean; atual: string | null; feitos: string[]; erros: string[]; reiniciar: boolean } }>('/api/nos'),
  instalarNos: (pacote: string) =>
    pedir<{ nos: string[] }>('/api/nos/instalar', { method: 'POST', body: JSON.stringify({ pacote }) }),
  cancelar: () => pedir<{ ok: boolean }>('/api/pacotes/cancelar', { method: 'POST' }),
}
