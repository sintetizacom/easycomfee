/** The Plenio Player's server (plenio/player/server.py): the library, one song, the files and the state - or,
 * in a shared player (one HTML file, portable.ts), the songs inside the page and the listener's browser. */
import { ensureMedia, isPortable, notInShared, portable, portableMedia, portablePage, portableState, savePortableState } from './portable'

export interface Loudness {
  lufs: number | null
  true_peak: number | null
  range: number | null
}

export interface Brief {
  kind?: string
  mode?: string
  template?: string
  description?: string
  genre?: string
  mood?: string
  tempo?: string
  length?: string
  vocals?: string
  language?: string
  voice?: string
  theme?: string
  lead_instrument?: string
  key?: string
  meter?: string
  arrangement?: string
  harmony?: string
  closeness?: number | null
  melody?: string
  lyrics_closeness?: number | null
  lines_under_singing?: boolean
  /** 0 steady ... 50 the reference ... 100 experimental (a song made before the slider: 50). */
  creativity?: number | null
  /** Per field where its value came from: ``typed``, ``template`` or ``default`` (left empty: the brief's
   * default, or for a text field the writer's choice). */
  sources?: Record<string, 'typed' | 'template' | 'default'>
}

export type SamplingStage = 'writer' | 'arrangement' | 'plan' | 'take'

/** A stage's sampling as the song was made: the writer's and a creative mode's temperature, YuE2's plan and take
 * with top-p and top-k. */
export interface SamplingValues {
  temperature: number
  top_p?: number
  top_k?: number
  /** The numbers were written in the workflow, not given by the creativity (a block saved before 1.0.2, or set by hand). */
  fixed?: boolean
}

export interface SongSummary {
  id: string
  title: string
  created: string
  year: string
  seconds: number
  model: string
  kind: string
  brief: Brief
  genre: string
  mood: string
  language: string
  vocals: string
  instrumental: boolean
  arrangement: string
  template: string
  style: string
  lyrics: string
  loudness: Loudness
  tags: Record<string, string>
  plenio: string
  folder: string
  file: string
  takes_key: string
  has: Record<'audio' | 'original' | 'cover' | 'pdf' | 'lines' | 'notes' | 'stems' | 'timing' | 'score', boolean>
  bpm?: number | null
  score_key?: string
  score_meter?: string
  seeds: Partial<Record<'take' | 'draft' | 'arrangement', number>>
  writer: string
  /** What the record shows of the sampling (older players' caches and other music: none). */
  sampling?: Partial<Record<SamplingStage, SamplingValues>>
  /** Music not made with Plenio (a folder with *also other music*): what its file has, no more. */
  other?: boolean
  artist?: string
  album?: string
}

/** A timed lyrics line: ``units`` are ``[start, cut]`` (the line shown up to ``cut`` from ``start``), with the
 * syllable's place in the score as a third number where the song has a score. */
export interface TimedLine {
  text: string
  start: number
  end: number
  units: number[][]
}

export interface Section {
  label: string
  start: number
  bar: number
}

export interface Notation {
  abc?: string
  tempo?: number
  sections?: Section[]
  seconds?: number
  warp?: [number, number] | null
  /** For a song without measured times: ``(audio, score)`` time pairs estimated from the music. */
  anchors?: [number, number][]
  estimated?: boolean
  error?: string
}

export interface SongDetail extends SongSummary {
  documents: Record<string, string>
  lyrics_raw: string
  notation: Notation
  lines: TimedLine[]
  timing_source: string
  files: Record<string, string>
  record_path: string
  /** Other music: the audio file's path. */
  file_path?: string
  /** Every file the song has in its record's folder (relative to it): what removing it moves or deletes. */
  owned_files: string[]
  /** Where retiring moves the files. */
  retire_to: string
  licences: string[]
  versions: Record<string, string>
}

export interface Playlist {
  id: string
  name: string
  songs: string[]
  created: string
  hue?: number
  /** A visual for the whole playlist (``''``: the visual settings decide). */
  visual?: string
}

export interface PlayerState {
  playlists: Playlist[]
  favorites: string[]
  plays: Record<string, number>
  last_played: Record<string, string>
  /** The listener's own tags per song (song id -> tags, in the order given). */
  tags: Record<string, string[]>
  settings: Record<string, unknown>
}

export interface RemoveAnswer {
  action: 'retire' | 'delete'
  files: string[]
  folder: string | null
}

/** Who answers (``/api/info``): the player, where it keeps the state, which ComfyUI started it. */
export interface PlayerInfo {
  app: string
  version: string
  folders: string[]
  state: string
  retired: string
  comfyui: string
  pid: number
  /** This page came from the network (by the player's gateway): it does all but this computer's own things. */
  remote?: boolean
}

/** The player and ComfyUI from the network (``plenio/player/network.py``). */
export interface NetworkStatus {
  on: boolean
  port: number
  comfy_port: number
  /** The links with their code: they let a browser in (the first is this computer's main address). */
  url: string
  urls: string[]
  comfyui_url: string
  comfyui_urls: string[]
  /** For a page from the network: ComfyUI by the address it came by. */
  comfyui_here: string
  comfyui_running: boolean
  error: string
  remote: boolean
}

/** The state as the player sends it: with its change's number. */
export type StateAnswer = PlayerState & { rev?: number }

/** Saving the state: saved (and the change's number) - or another page saved since, and this is what is saved
 * now, to merge. */
export type SaveAnswer = { ok: true; rev?: number } | { ok: false; rev: number; state: StateAnswer }

export interface ComfyFound {
  url: string
  version: string
}

/** A folder the player reads, its songs and its other music. */
export interface FolderRow {
  path: string
  other: boolean
  exists: boolean
  songs: number
  other_songs: number
}

export interface FoldersAnswer {
  folders: FolderRow[]
  /** Chosen in Settings (else the folders it started with). */
  chosen: boolean
  started_with: string[]
}

export interface DirsAnswer {
  path: string | null
  parent: string | null
  dirs: { name: string; path: string }[]
  places: { name: string; path: string }[]
  error: string
}

export interface LibraryAnswer {
  songs: SongSummary[]
  folders: string[]
  errors: string[]
  version: string
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init)
  if (!response.ok) throw new Error(`${url}: ${response.status}`)
  return (await response.json()) as T
}

/** A JSON request that changes something; errors carry the server's words. */
async function post<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  const data = await response.json().catch(() => null)
  if (!response.ok) throw new Error(data?.error ?? `${url}: ${response.status}`)
  return data as T
}

export interface PackageOptions {
  songs: string[]
  title: string
  bitrate: number
  pdf: boolean
  settings?: Record<string, unknown>
  presets?: { name: string; text: string }[]
  playlists?: { name: string; songs: string[] }[]
  /** Your tags of the songs packed (song id -> tags). */
  tags?: Record<string, string[]>
  /** Parts of at most so many MB (250, 500, 1000) - for phones; 0: one file. */
  part_mb?: number
}

/** The guests' access to the live playlist (``plenio/player/guest.py``). */
export interface GuestStatus {
  on: boolean
  mode: 'view' | 'change'
  show: 'both' | 'qr' | 'address' | 'none'
  port: number
  url: string
  urls: string[]
  guests: number
  error: string
}

export interface GuestWish {
  n: number
  op: 'up' | 'down' | 'next' | 'remove' | 'add'
  id: string
  at?: number
  where?: 'next' | 'end'
}

export interface PackageStatus {
  job?: string
  state: 'waiting' | 'working' | 'done' | 'error' | 'stopped'
  /** ``reading`` the songs, then ``packing`` their sound. */
  stage?: string
  done: number
  total: number
  title?: string
  bitrate?: number
  file?: string
  /** Every file made: one, or the parts. */
  files?: { name: string; size: number }[]
  size?: number
  folder?: string
  error?: string
  part_mb?: number
}

const serverApi = {
  library: () => json<LibraryAnswer>('/api/library'),
  song: (id: string) => json<SongDetail>(`/api/song/${id}`),
  state: () => json<StateAnswer>('/api/state'),
  /** The number of the last change saved (another page's too). */
  stateRev: () => json<{ rev: number }>('/api/state/rev'),
  /** Save the state, from the change ``rev`` (``undefined``: whatever is saved); ``keepalive``: also when the
   * page is closing (the last change is not lost). */
  saveState: async (state: PlayerState, keepalive = false, rev?: number): Promise<SaveAnswer> => {
    const response = await fetch('/api/state', {
      method: 'PUT',
      keepalive,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rev === undefined ? state : { ...state, rev }),
    })
    const data = await response.json().catch(() => null)
    if (response.status === 409 && data?.state) return { ok: false, rev: data.rev, state: data.state }
    if (!response.ok) throw new Error(data?.error ?? `/api/state: ${response.status}`)
    return { ok: true, rev: data?.rev }
  },
  network: () => json<NetworkStatus>('/api/network'),
  /** Switch the player's access from the network on or off, or make a new link. */
  setNetwork: (changes: { on?: boolean; regenerate?: boolean }) =>
    json<NetworkStatus>('/api/network', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(changes) }),
  info: () => json<PlayerInfo>('/api/info'),
  find: (record: string) => json<{ id: string }>(`/api/find?record=${encodeURIComponent(record)}`),
  comfyui: (url = '') => json<{ found: ComfyFound | null }>(`/api/comfyui${url ? `?url=${encodeURIComponent(url)}` : ''}`),
  quit: () => json<{ ok: boolean }>('/api/quit', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }),
  rescan: () => json<{ songs: number }>('/api/rescan', { method: 'POST' }),
  removeSong: (id: string, action: 'retire' | 'delete') =>
    json<RemoveAnswer>(`/api/song/${id}/remove`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, confirm: id }),
    }),
  peaks: (id: string) => json<{ peaks: number[] }>(`/api/peaks/${id}`),
  folders: () => json<FoldersAnswer>('/api/folders'),
  videoStart: (body: { song: string; take: string; start: number; length: number; fps: number; width: number; height: number }) =>
    post<{ job: string }>('/api/video', body),
  videoData: async (job: string, data: Uint8Array<ArrayBuffer>): Promise<void> => {
    const response = await fetch(`/api/video/${job}/data`, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream', 'X-Plenio-Player': '1' }, body: data })
    if (!response.ok) throw new Error((await response.json().catch(() => null))?.error ?? `the video could not be sent (${response.status})`)
  },
  videoFinish: (job: string, frames: number) => post<{ file: string; size: number; folder: string }>(`/api/video/${job}/finish`, { frames }),
  videoCancel: (job: string) => post<{ ok: boolean }>(`/api/video/${job}/cancel`, {}),
  videos: () => json<{ folder: string; files: { name: string; size: number; mtime: number }[] }>('/api/videos'),
  /** The videos folder in the file manager (``file``: that video chosen). */
  openVideos: (file = '') => post<{ folder: string }>('/api/videos/open', file ? { file } : {}),
  /** The songs that appeared since ``since`` (the last answer's ``now``; ``null``: only the ``now``). */
  newSongs: (since: number | null) => json<{ now: number; songs: SongSummary[] }>(`/api/new${since !== null ? `?since=${since}` : ''}`),
  /** Save the folders (or ``null``: back to the ones it started with); errors carry the server's words. */
  setFolders: async (folders: { path: string; other: boolean }[] | null): Promise<FoldersAnswer> => {
    const response = await fetch('/api/folders', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(folders ? { folders } : { reset: true }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data?.error ?? `could not save the folders (${response.status})`)
    return data as FoldersAnswer
  },
  dirs: (path: string | null) => json<DirsAnswer>(`/api/dirs${path ? `?path=${encodeURIComponent(path)}` : ''}`, { headers: { 'X-Plenio-Player': '1' } }),
  /** A shared player of chosen songs (one HTML file), made by the server; its progress, the ones made. */
  packageStart: (options: PackageOptions) => post<{ job: string }>('/api/package', options),
  packageStatus: (job: string) => json<PackageStatus>(`/api/package/${job}`),
  /** The shared players being made, waiting and made since the player started (newest first). */
  packageJobs: () => json<{ jobs: PackageStatus[] }>('/api/package-jobs'),
  packageCancel: (job: string) => post<{ ok: boolean }>(`/api/package/${job}/cancel`, {}),
  packageClear: () => post<{ jobs: PackageStatus[] }>('/api/package-jobs/clear', {}),
  packages: () => json<{ folder: string; files: { name: string; size: number; mtime: number }[] }>('/api/packages'),
  openPackages: (file = '') => post<{ folder: string }>('/api/packages/open', file ? { file } : {}),
  guests: () => json<GuestStatus>('/api/guests'),
  /** Switch the guests' access on or off, choose what they may do and what the screen shows, or make a new
   * address (``regenerate``). */
  setGuests: (changes: Partial<Pick<GuestStatus, 'on' | 'mode' | 'show'>> & { regenerate?: boolean }) =>
    json<GuestStatus>('/api/guests', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(changes) }),
  /** What the page shows of the live playlist, for the guests. */
  showGuests: (shown: unknown) => post<{ ok: boolean }>('/api/guests/live', shown),
  guestWishes: (after: number) => json<{ wishes: GuestWish[]; last: number }>(`/api/guests/wishes?after=${after}`),
}

/** In a shared player: the songs inside the page, the listener's state in their browser; the rest is the
 * Plenio Player's only. */
function sharedApi(): typeof serverApi {
  const data = portable as NonNullable<typeof portable>
  const none = async () => notInShared()
  return {
    ...serverApi,
    library: async () => ({ songs: data.songs, folders: [], errors: [], version: data.plenio }),
    song: async (id: string) => {
      const page = await portablePage(id)
      if (!page) throw new Error('no such song')
      return page.detail
    },
    state: async () => portableState(),
    stateRev: async () => ({ rev: 0 }),
    saveState: async (state: PlayerState) => {
      savePortableState(state)
      return { ok: true as const }
    },
    network: none,
    setNetwork: none,
    info: async () => ({ app: 'plenio-shared', version: data.plenio, folders: [], state: 'this browser', retired: '', comfyui: '', pid: 0 }),
    find: none,
    comfyui: async () => ({ found: null }),
    quit: none,
    rescan: async () => ({ songs: data.songs.length }),
    removeSong: none,
    peaks: async (id: string) => {
      const levels = (await portablePage(id))?.peaks
      if (!levels) throw new Error('no waveform')
      return { peaks: levels }
    },
    folders: none,
    setFolders: none,
    dirs: none,
    newSongs: async () => ({ now: 0, songs: [] }),
    videoStart: none,
    videoData: none,
    videoFinish: none,
    videoCancel: none,
    videos: async () => ({ folder: '', files: [] }),
    openVideos: none,
    packageStart: none,
    packageStatus: none,
    packageJobs: async () => ({ jobs: [] }),
    packageCancel: none,
    packageClear: none,
    packages: async () => ({ folder: '', files: [] }),
    openPackages: none,
    guests: none,
    setGuests: none,
    showGuests: none,
    guestWishes: none,
  }
}

export const api: typeof serverApi = isPortable ? sharedApi() : serverApi

/** A song's file by kind (``audio``, ``cover``, ``pdf`` ...): its URL (in a shared player ``''`` until it is
 * made from the page, then the page shows it by itself). */
export const media = (id: string, kind: string): string => (isPortable ? portableMedia(id, kind) : `/media/${id}/${kind}`)

/** The file's URL once it can be used (a shared player makes it from the page first). */
export const mediaReady = (id: string, kind: string): Promise<string> => (isPortable ? ensureMedia(id, kind) : Promise.resolve(`/media/${id}/${kind}`))
