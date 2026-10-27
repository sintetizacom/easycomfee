/**
 * A song as an MP4 video (owner's request 2026-10-16): every frame drawn here - the visual from the song's
 * own sound (offline.ts), the lyrics, the notation, a title card, the song in a corner, a progress bar - then
 * encoded as H.264 by the browser (WebCodecs, on the graphics card where it can) and sent to the player's
 * server in pieces, which puts it together with the song's sound into an MP4 (plenio/player/video.py).
 *
 * And more to choose (owner's request 2026-10-18): the cover always in the picture - in its place, size and
 * shape (also a spinning record), pulsing with the beat; the lyrics word by word, in a place of their own or a
 * new place every line, coming in with a fade, a rise, a zoom, a drop, a blur, a wipe or a glitch - in one
 * beat when they follow it; and the title, the lyrics and the cover drawn into a Plenio Drop visual's smoke.
 */
import { api, media, type SongDetail, type SongSummary } from '../api'
import { paletteFrom, songHue } from '../colors'
import { fontOf, litColor, lyricsWithDefaults, type LyricsStyle } from '../lyricsStyle'
import { settings } from '../store'
import { lineAt, sectionAt, sectionsInSong, songAnchors, type TimedSection } from '../timing'
import { chooseVisual } from '../visuals/chooser'
import { DropRenderer } from '../visuals/drop/renderer'
import { storySprites, tellRenderer, textPicture } from '../visuals/drop/story'
import { SceneMixer, fadeWithDefaults, type FadeStyle } from '../visuals/mixer'
import { allPresets, makeColors, presetById, type Scheme } from '../visuals/presets'
import { NotationStrip } from './notationStrip'
import { OfflineAnalysis } from './offline'
import { drawCorner, drawCoverBadge, drawCredit, drawMovingLyrics, drawProgress, drawTitleCard, drawWords, type CoverLook, type Entrance, type LyricsLook, type LyricsPlace, type TitleInfo } from './overlay'

export interface VideoOptions {
  width: number
  height: number
  fps: number
  /** The part of the song: from ``start`` for ``length`` seconds (0: to the end). */
  start: number
  length: number
  take: 'master' | 'original'
  /** A visual (its id), or ``''``: as the visuals' settings choose for this song. */
  visual: string
  /** Another visual: never, at every section of the song, or every ``interval`` seconds. */
  change: 'never' | 'section' | 'interval'
  interval: number
  /** How one visual turns into the next, and over how many seconds (owner's request 2026-10-18: softly). */
  fade: FadeStyle
  fadeSeconds: number
  scheme: Scheme
  lyrics: 'off' | 'subtitles' | 'karaoke' | 'words'
  /** The lyrics' font, colour, size and effect (at first the player's own). */
  lyricsStyle: LyricsStyle
  /** Where the lyrics stand (``random``: a new place every line), how each line comes in, and whether it comes
   * in one beat and pulses with the beat. */
  lyricsPlace: LyricsPlace
  lyricsIn: Entrance
  onBeat: boolean
  /** The cover always in the picture: whether, where, how large, its shape, a pulse on the beat. */
  cover: CoverLook & { show: boolean }
  /** Drawn into a Plenio Drop visual's smoke (melting and swirling with it): the title at the start, the line
   * sung, the cover; over another visual, as a glow. */
  into: { title: boolean; lyrics: boolean; cover: boolean }
  notation: boolean
  title: boolean
  corner: boolean
  progress: boolean
  credit: boolean
  quality: 'standard' | 'high'
}

const ENTRANCE_IDS: Entrance[] = ['none', 'fade', 'rise', 'zoom', 'drop', 'blur', 'wipe', 'glitch', 'random']
export const COVER_PLACES: CoverLook['place'][] = ['top-left', 'top', 'top-right', 'left', 'center', 'right', 'bottom-left', 'bottom', 'bottom-right', 'drift']

export const SIZES: { id: string; label: string; width: number; height: number }[] = [
  { id: '1080p', label: '1920 × 1080 - Full HD, 16:9', width: 1920, height: 1080 },
  { id: '720p', label: '1280 × 720 - HD, 16:9', width: 1280, height: 720 },
  { id: '4k', label: '3840 × 2160 - 4K, 16:9', width: 3840, height: 2160 },
  { id: 'square', label: '1080 × 1080 - square', width: 1080, height: 1080 },
  { id: 'vertical', label: '1080 × 1920 - upright (Shorts, Reels, TikTok)', width: 1080, height: 1920 },
]

export const DEFAULT_VIDEO: VideoOptions = {
  width: 1920,
  height: 1080,
  fps: 30,
  start: 0,
  length: 0,
  take: 'master',
  visual: '',
  change: 'never',
  interval: 20,
  fade: 'blend',
  fadeSeconds: 3,
  scheme: 'song',
  lyrics: 'subtitles',
  lyricsStyle: lyricsWithDefaults(null),
  lyricsPlace: 'bottom',
  lyricsIn: 'fade',
  onBeat: true,
  cover: { show: false, place: 'bottom-right', size: 0.2, shape: 'rounded', pulse: true },
  into: { title: false, lyrics: false, cover: false },
  notation: false,
  title: true,
  corner: true,
  progress: true,
  credit: true,
  quality: 'standard',
}

/** Saved video settings, checked. */
export function videoWithDefaults(raw: unknown, lyrics?: unknown): VideoOptions {
  const given = (raw && typeof raw === 'object' ? raw : {}) as Partial<VideoOptions> & { eachSection?: boolean }
  const out = { ...DEFAULT_VIDEO, ...given, start: 0, length: 0 }
  // settings of before: a new visual at every section
  if (given.change === undefined && given.eachSection) out.change = 'section'
  delete (out as { eachSection?: boolean }).eachSection
  if (!['never', 'section', 'interval'].includes(out.change)) out.change = 'never'
  out.interval = Math.min(600, Math.max(3, Number(out.interval) || 20))
  const fade = fadeWithDefaults(out.fade, out.fadeSeconds)
  out.fade = fade.style
  out.fadeSeconds = fade.seconds
  out.lyricsStyle = lyricsWithDefaults(given.lyricsStyle ?? lyrics)
  if (!SIZES.some((s) => s.width === out.width && s.height === out.height)) Object.assign(out, { width: 1920, height: 1080 })
  if (![24, 25, 30, 50, 60].includes(out.fps)) out.fps = 30
  if (!['off', 'subtitles', 'karaoke', 'words'].includes(out.lyrics)) out.lyrics = 'subtitles'
  if (!['bottom', 'middle', 'top', 'random'].includes(out.lyricsPlace)) out.lyricsPlace = 'bottom'
  if (!ENTRANCE_IDS.includes(out.lyricsIn)) out.lyricsIn = 'fade'
  out.onBeat = out.onBeat !== false
  const cover = { ...DEFAULT_VIDEO.cover, ...(given.cover && typeof given.cover === 'object' ? given.cover : {}) }
  if (!COVER_PLACES.includes(cover.place)) cover.place = 'bottom-right'
  if (!['square', 'rounded', 'round', 'record'].includes(cover.shape)) cover.shape = 'rounded'
  cover.size = Math.min(0.6, Math.max(0.08, Number(cover.size) || 0.2))
  cover.show = !!cover.show
  cover.pulse = cover.pulse !== false
  out.cover = cover
  const into = (given.into && typeof given.into === 'object' ? given.into : {}) as Partial<VideoOptions['into']>
  out.into = { title: !!into.title, lyrics: !!into.lyrics, cover: !!into.cover }
  if (!['standard', 'high'].includes(out.quality)) out.quality = 'standard'
  return out
}

// --- the song's sound ------------------------------------------------------------------------------------

export interface Sound {
  left: Float32Array
  right: Float32Array
  rate: number
  duration: number
}

let decoded: { key: string; sound: Sound } | null = null

/** The song's audio, decoded (the last one is kept: the preview and the video use it again). */
export async function soundOf(song: SongSummary, take: 'master' | 'original'): Promise<Sound> {
  const kind = take === 'original' && song.has.original ? 'original' : 'audio'
  const key = `${song.id}/${kind}`
  if (decoded?.key === key) return decoded.sound
  const response = await fetch(media(song.id, kind))
  if (!response.ok) throw new Error(`the song's audio could not be read (${response.status})`)
  const data = await response.arrayBuffer()
  const context = new OfflineAudioContext(2, 1, 48000)
  const buffer = await context.decodeAudioData(data)
  const left = buffer.getChannelData(0)
  const right = buffer.numberOfChannels > 1 ? buffer.getChannelData(1) : left
  const sound = { left, right, rate: buffer.sampleRate, duration: buffer.duration }
  decoded = { key, sound }
  return sound
}

// --- the frames ------------------------------------------------------------------------------------------

function loadImage(url: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => resolve(null)
    img.src = url
  })
}

/** Draws the video's frames, one after the other (the visuals have memory: trails, beats). */
export class Composer {
  readonly canvas: HTMLCanvasElement
  private readonly ctx: CanvasRenderingContext2D
  private readonly analysis: OfflineAnalysis
  private readonly mixer: SceneMixer
  private drop: DropRenderer | null | undefined
  private turn = 0
  private lastChange = 0
  private section: TimedSection | null = null
  private readonly look: { stack: string; weight: number; lit: string }
  private readonly sections: TimedSection[]
  private readonly hue: number
  private readonly accent: string
  readonly length: number

  private constructor(
    private readonly song: SongSummary,
    private readonly detail: SongDetail,
    private readonly sound: Sound,
    readonly options: VideoOptions,
    private readonly strip: NotationStrip | null,
    private readonly info: TitleInfo,
    width: number,
    height: number
  ) {
    this.canvas = document.createElement('canvas')
    this.canvas.width = width
    this.canvas.height = height
    this.ctx = this.canvas.getContext('2d') as CanvasRenderingContext2D
    this.analysis = new OfflineAnalysis(sound, options.fps, settings.visuals.sensitivity)
    this.mixer = new SceneMixer((preset) => preset.create({ drop: { renderer: () => this.dropRenderer(), scale: 1 } }))
    this.sections = sectionsInSong(detail.notation.sections, songAnchors(detail.lines, detail.notation), detail.notation.warp, sound.duration)
    this.hue = songHue(song.id, song.genre)
    this.accent = paletteFrom(this.hue).accent
    const font = fontOf(options.lyricsStyle)
    this.look = { ...font, lit: litColor(options.lyricsStyle, this.accent) }
    const rest = Math.max(0, sound.duration - options.start)
    this.length = options.length > 0 ? Math.min(options.length, rest) : rest
  }

  /** ``scale``: smaller than the video, for a preview. */
  static async create(song: SongSummary, detail: SongDetail, sound: Sound, options: VideoOptions, scale = 1): Promise<Composer> {
    const width = Math.round((options.width * scale) / 2) * 2
    const height = Math.round((options.height * scale) / 2) * 2
    const upright = height > width * 1.2
    const strip = options.notation && detail.notation.abc ? await NotationStrip.create(detail.notation, detail.lines, upright ? 760 : 1100) : null
    // the cover for the title card, the corner, the visual's pictures
    const cover = song.has.cover ? await loadImage(media(song.id, 'cover')) : null
    const subtitle = song.other
      ? [song.artist, song.album].filter(Boolean).join(' · ') || 'Other music'
      : [song.genre.split(',')[0], song.model || 'Plenio'].filter(Boolean).join(' · ')
    const info: TitleInfo = { title: song.title, subtitle, cover: options.title ? cover : null, accent: paletteFrom(songHue(song.id, song.genre)).accent, image: cover }
    return new Composer(song, detail, sound, options, strip, info, width, height)
  }

  get total(): number {
    return Math.max(1, Math.ceil(this.length * this.options.fps))
  }

  private dropRenderer(): DropRenderer | null {
    if (this.drop === undefined) {
      try {
        this.drop = new DropRenderer()
        // a change of Drop preset glides as long as the video's crossfade
        this.drop.blendSeconds = this.options.fade === 'cut' ? 0.05 : this.options.fadeSeconds
      } catch {
        this.drop = null
      }
    }
    return this.drop
  }

  /** The visual for this moment: the one chosen, or as the visuals' settings choose; another at a new
   * section, or every few seconds, when asked. */
  private pick(t: number, elapsed: number): void {
    const { change, interval } = this.options
    const section = change === 'section' ? sectionAt(this.sections, t) : null
    const due =
      this.mixer.preset === null ||
      (change === 'section' && section !== this.section) ||
      (change === 'interval' && elapsed - this.lastChange >= Math.max(3, interval))
    if (!due) return
    if (this.mixer.preset) this.turn += 1
    this.section = section
    this.lastChange = elapsed
    let id = this.options.visual
    if (!id || (change !== 'never' && this.turn > 0)) {
      const pool = { ...settings.visuals, songs: this.turn > 0 ? {} : settings.visuals.songs }
      if (this.options.visual && this.turn > 0) Object.assign(pool, { mode: 'cycle' as const })
      id = chooseVisual({ settings: pool, song: this.song, previous: this.mixer.preset?.id ?? (this.options.visual || null), turn: this.turn })
    }
    // the change as the video's crossfade says: both visuals play on while the new one comes in
    this.mixer.use(presetById(id) ?? allPresets()[0], { style: this.options.fade, seconds: this.options.fadeSeconds })
  }

  /** Over a visual that is not Plenio Drop, the song's title, line and cover chosen into it - as a glow (the
   * classic visuals draw no smoke to melt them into). */
  private glowInto(ctx: CanvasRenderingContext2D, t: number, elapsed: number, w: number, h: number, pulse: number): void {
    const unit = Math.min(w, h)
    ctx.save()
    ctx.globalCompositeOperation = 'screen'
    if (this.options.into.cover && this.info.image) {
      const s = unit * (0.34 + 0.04 * pulse)
      ctx.globalAlpha = 0.28
      ctx.drawImage(this.info.image, w / 2 - s / 2, h / 2 - s / 2, s, s)
    }
    const picture = (text: string, size: number, y: number, alpha: number) => {
      const p = textPicture(text)
      const ph = size
      const pw = Math.min(w * 0.9, (p.width / p.height) * ph)
      ctx.globalAlpha = alpha
      ctx.drawImage(p, w / 2 - pw / 2, y - ph / 2, pw, (pw / ((p.width / p.height) * ph)) * ph)
    }
    if (this.options.into.title) {
      const alpha = Math.min(1, elapsed / 0.8) * Math.max(0, 1 - elapsed / 8)
      if (alpha > 0) picture(this.song.title, unit * 0.16, h * 0.42, alpha * 0.5)
    }
    if (this.options.into.lyrics) {
      const i = lineAt(this.detail.lines, t)
      const line = i >= 0 ? this.detail.lines[i] : null
      if (line && t <= line.end + 0.3) picture(line.text, unit * 0.09, h * 0.72, 0.35)
    }
    ctx.restore()
  }

  /** Draw frame ``k`` (``k / fps`` seconds into the part). */
  draw(k: number): void {
    const { fps } = this.options
    const elapsed = k / fps
    const t = this.options.start + elapsed
    const w = this.canvas.width
    const h = this.canvas.height
    const ctx = this.ctx
    const frame = this.analysis.frame(t, 1 / fps, elapsed)
    this.pick(t, elapsed)
    const colors = makeColors(this.hue, this.options.scheme, elapsed)
    const into = this.options.into
    const lines = this.detail.lines
    if (this.mixer.preset?.kind === 'drop') {
      // the song for the pictures of the Drop visual, and the title, line and cover chosen into its smoke
      const renderer = this.dropRenderer()
      if (renderer) {
        tellRenderer(renderer, { id: this.song.id, title: this.song.title, cover: this.info.image ?? null, lines }, t)
        renderer.extraSprites = storySprites(into, elapsed, frame.pulse, renderer.story.lineOn)
      }
    }
    this.mixer.draw(ctx, frame, w, h, colors)
    if (this.mixer.preset?.kind !== 'drop' && (into.title || into.lyrics || into.cover)) this.glowInto(ctx, t, elapsed, w, h, frame.pulse)
    // what is drawn over it
    const upright = h > w * 1.2
    const stripH = Math.round(h * (upright ? 0.16 : 0.25))
    const stripY = h - stripH - Math.round(h * 0.045)
    if (this.strip) this.strip.draw(ctx, t, Math.round(w * 0.03), stripY, Math.round(w * 0.94), stripH, this.accent, settings.notationShift[this.song.id] ?? 0)
    // after the title card: the cover in its place, the lyrics
    const after = this.options.title ? Math.min(1, Math.max(0, (elapsed - 4) / 0.8)) : 1
    const cover = this.options.cover
    if (cover.show && this.info.image) drawCoverBadge(ctx, this.info.image, cover, w, h, elapsed, frame.pulse, this.accent, after)
    // the lyrics come in as the title card goes
    const lyricsAlpha = this.options.title ? Math.min(1, Math.max(0, (elapsed - 3.4) / 0.8)) : 1
    const look: LyricsLook = { ...this.look, effect: this.options.lyricsStyle.effect, clock: elapsed, pulse: this.options.onBeat ? frame.pulse : 0 }
    const size = this.options.lyricsStyle.size
    // a line comes in in one beat when it follows the beat (the song's tempo), else in four tenths of a second
    const beat = this.song.bpm ? 60 / this.song.bpm : 0.5
    const span = this.options.onBeat ? Math.min(0.9, Math.max(0.25, beat)) : 0.4
    const floor = this.strip ? stripY - h * 0.02 : h * 0.9
    if (lines.length && lyricsAlpha > 0) {
      if (this.options.lyrics === 'words') {
        ctx.save()
        ctx.globalAlpha = lyricsAlpha
        const centre = this.options.lyricsPlace === 'top' ? h * 0.3 : this.options.lyricsPlace === 'bottom' ? Math.min(h * 0.7, floor - h * 0.12) : this.strip ? floor / 2 : h / 2
        drawWords(ctx, lines, t, w, h, look, size, this.options.onBeat ? Math.min(0.32, beat / 2) : 0.22, centre)
        ctx.restore()
      } else if (this.options.lyrics !== 'off') {
        const place = this.options.lyrics === 'karaoke' && this.options.lyricsPlace === 'bottom' ? 'middle' : this.options.lyricsPlace
        drawMovingLyrics(ctx, this.options.lyrics, lines, t, w, h, place, this.options.lyricsIn, span, lyricsAlpha, look, size, this.options.lyrics === 'karaoke' && this.strip ? floor / 2 : floor, this.hue)
      }
    }
    // the song's name in the corner keeps clear of a cover there
    const nudge = cover.show && this.info.image && cover.place === 'top-left' ? Math.min(w, h) * (cover.size + 0.06) : 0
    if (this.options.corner) drawCorner(ctx, this.info, w, h, after, nudge)
    if (this.options.credit) drawCredit(ctx, w, h)
    if (this.options.progress) drawProgress(ctx, t, this.sound.duration, this.sections, this.accent, w, h)
    if (this.options.title) drawTitleCard(ctx, this.info, elapsed, w, h)
  }
}

/** One frame of the video at ``at`` seconds into the song, small - after a few seconds drawn before it, so
 * that the visual has its trails. */
export async function preview(song: SongSummary, detail: SongDetail, options: VideoOptions, at: number, width = 640): Promise<HTMLCanvasElement> {
  const sound = await soundOf(song, options.take)
  const composer = await Composer.create(song, detail, sound, options, width / options.width)
  const target = Math.max(0, Math.round((at - options.start) * options.fps))
  for (let k = Math.max(0, target - options.fps * 3); k <= target; k++) composer.draw(k)
  return composer.canvas
}

// --- the encoder -----------------------------------------------------------------------------------------

/** The H.264 level the frame size and rate need (macroblocks per frame and per second). */
export function levels(width: number, height: number, fps: number): string[] {
  const frame = Math.ceil(width / 16) * Math.ceil(height / 16)
  const rate = frame * fps
  const all: [string, number, number][] = [
    ['28', 8192, 245760],
    ['2A', 8704, 522240],
    ['32', 22080, 589824],
    ['33', 36864, 983040],
    ['34', 36864, 2073600],
  ]
  return all.filter(([, maxFrame, maxRate]) => frame <= maxFrame && rate <= maxRate).map(([level]) => level)
}

async function encoderConfig(options: VideoOptions): Promise<VideoEncoderConfig> {
  if (typeof VideoEncoder === 'undefined') throw new Error('This browser cannot encode video (WebCodecs): use a current Chrome or Edge.')
  const { width, height, fps } = options
  const bitrate = Math.round(width * height * fps * (options.quality === 'high' ? 0.15 : 0.085))
  for (const level of levels(width, height, fps)) {
    for (const profile of ['6400', '4D00', '42E0']) {
      const config: VideoEncoderConfig = {
        codec: `avc1.${profile}${level}`,
        width,
        height,
        bitrate,
        framerate: fps,
        bitrateMode: 'variable',
        latencyMode: 'quality',
        avc: { format: 'annexb' },
      }
      const answer = await VideoEncoder.isConfigSupported(config)
      if (answer.supported) return answer.config ?? config
    }
  }
  throw new Error(`This browser cannot encode H.264 at ${width} × ${height}, ${fps} frames a second.`)
}

// --- pauses a tab in the background does not stretch --------------------------------------------------------

const channel = typeof MessageChannel !== 'undefined' ? new MessageChannel() : null
const resumes: (() => void)[] = []
if (channel) channel.port1.onmessage = () => resumes.shift()?.()

/** A short pause for the page between frames. A tab in the background has its timers held back to once a second
 * (a video in the queue would crawl there); a message to itself is not held back. */
export function nextTask(): Promise<void> {
  if (!channel) return new Promise((resolve) => setTimeout(resolve, 0))
  return new Promise((resolve) => {
    resumes.push(resolve)
    channel.port2.postMessage(0)
  })
}

/** Until the encoder has taken a frame from its queue (its ``dequeue`` event; a short wait where it has none). */
function dequeued(encoder: VideoEncoder): Promise<void> {
  return new Promise((resolve) => {
    const done = (): void => {
      encoder.removeEventListener('dequeue', done)
      window.clearTimeout(timer)
      resolve()
    }
    const timer = window.setTimeout(done, 40)
    encoder.addEventListener('dequeue', done)
  })
}

export interface Progress {
  stage: string
  frame: number
  total: number
  /** Frames a second against the video's rate: 2 = twice as fast as it plays. */
  speed: number
  /** Seconds left. */
  left: number
}

/** Make the video: every frame drawn and encoded, sent to the player, put together there with the sound.
 * ``onFrame`` sees the canvas now and then (a live preview). */
export async function makeVideo(
  song: SongSummary,
  options: VideoOptions,
  onProgress: (progress: Progress) => void,
  signal: AbortSignal,
  onFrame?: (canvas: HTMLCanvasElement) => void
): Promise<{ file: string; size: number; folder: string }> {
  onProgress({ stage: 'Reading the song', frame: 0, total: 0, speed: 0, left: 0 })
  const detail = await api.song(song.id)
  const sound = await soundOf(song, options.take)
  const composer = await Composer.create(song, detail, sound, options)
  const config = await encoderConfig(options)
  const total = composer.total
  const { job } = await api.videoStart({
    song: song.id,
    take: options.take,
    start: options.start,
    length: composer.length,
    fps: options.fps,
    width: composer.canvas.width,
    height: composer.canvas.height,
  })
  let failure: unknown = null
  let pending: Uint8Array[] = []
  let pendingBytes = 0
  let uploading: Promise<unknown> = Promise.resolve()
  const send = (): void => {
    if (!pendingBytes) return
    const data = new Uint8Array(pendingBytes)
    let at = 0
    for (const piece of pending) {
      data.set(piece, at)
      at += piece.length
    }
    pending = []
    pendingBytes = 0
    uploading = uploading.then(() => api.videoData(job, data)).catch((error) => (failure = failure ?? error))
  }
  const encoder = new VideoEncoder({
    output: (chunk) => {
      const piece = new Uint8Array(chunk.byteLength)
      chunk.copyTo(piece)
      pending.push(piece)
      pendingBytes += piece.length
      if (pendingBytes > 2 * 2 ** 20) send()
    },
    error: (error) => (failure = failure ?? error),
  })
  encoder.configure(config)
  const began = performance.now()
  try {
    for (let k = 0; k < total; k++) {
      if (signal.aborted) throw new DOMException('stopped', 'AbortError')
      if (failure) throw failure
      composer.draw(k)
      const frame = new VideoFrame(composer.canvas, { timestamp: Math.round((k * 1e6) / options.fps), duration: Math.round(1e6 / options.fps) })
      encoder.encode(frame, { keyFrame: k % (options.fps * 2) === 0 })
      frame.close()
      while (encoder.encodeQueueSize > 6) await dequeued(encoder)
      if (k % 15 === 0 || k === total - 1) {
        const seconds = (performance.now() - began) / 1000
        const rate = (k + 1) / Math.max(seconds, 0.001)
        onProgress({ stage: 'Drawing and encoding', frame: k + 1, total, speed: rate / options.fps, left: (total - k - 1) / rate })
        if (k % 60 === 0) onFrame?.(composer.canvas)
        await nextTask()
      }
    }
    await encoder.flush()
    send()
    await uploading
    if (failure) throw failure
    onProgress({ stage: 'Putting it together with the sound', frame: total, total, speed: 0, left: 0 })
    return await api.videoFinish(job, total)
  } catch (error) {
    void api.videoCancel(job).catch(() => {})
    throw error
  } finally {
    if (encoder.state !== 'closed') encoder.close()
  }
}
