export type FiltroGaleria = 'tudo' | 'imagem' | 'video' | 'voz' | 'musica'

export const FILTROS_GALERIA: { id: FiltroGaleria; rotulo: string }[] = [
  { id: 'tudo', rotulo: 'Tudo' },
  { id: 'imagem', rotulo: 'Imagem' },
  { id: 'video', rotulo: 'Vídeo' },
  { id: 'voz', rotulo: 'Voz' },
  { id: 'musica', rotulo: 'Música' },
]
