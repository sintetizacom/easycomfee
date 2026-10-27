/**
 * The song page's "The song": every field of the brief the song was made with, in the brief's order (owner's
 * request 2026-10-17: also the arrangement, genre, mood … when they were left empty - then with the default
 * and a note that it is one). A field the template filled says so; a text field left empty, which has no
 * default value, says that the writer chose. A recording (Enhance & Master) and other music have no brief:
 * they show what there is.
 */
import type { Brief, SamplingStage, SongSummary } from './api'
import { CREATIVITY_REFERENCE, describeCreativity, describeSampling, isReference } from './creativity'
import { formatTime } from './timing'

export interface Fact {
  label: string
  value: string
  /** Shown after the value in brackets: ``default``, ``from the template`` … */
  note?: string
}

/** A text field left empty: no default value, the writer (or the music model) chose. */
export const OPEN = 'open - the writer chose'

export function songFacts(s: SongSummary): Fact[] {
  const b = s.brief
  if (!b.kind) return plainFacts(s)
  const sources = b.sources ?? {}
  const cover = b.kind === 'cover'
  const out: Fact[] = []
  const noteOf = (name: keyof Brief): string => (sources[name] === 'default' ? 'default' : sources[name] === 'template' ? 'from the template' : '')
  /** A field of the brief: its value with where it came from, or - left empty - ``empty`` as the default. */
  const field = (label: string, name: keyof Brief, value?: string, empty = OPEN): void => {
    const text = value ?? String(b[name] ?? '')
    out.push(text ? { label, value: text, note: noteOf(name) } : { label, value: empty, note: 'default' })
  }
  /** A field the score answers (tempo, key, meter): the score's value, and when the brief left it empty, that
   * the writer chose it. */
  const scored = (label: string, name: keyof Brief, fromScore: string): void => {
    const typed = String(b[name] ?? '')
    if (fromScore) out.push({ label, value: typed && !fromScore.includes(typed) ? `${fromScore} · ${typed}` : fromScore, note: typed ? noteOf(name) : 'default - the writer chose' })
    else field(label, name)
  }
  field('Work mode', 'mode')
  field('Template', 'template', b.template || 'none')
  field('Genre', 'genre', b.genre || s.genre)
  field('Mood', 'mood')
  if (!cover) scored('Tempo', 'tempo', s.bpm ? `${s.bpm} BPM` : '')
  else if (s.bpm) out.push({ label: 'Tempo', value: `${s.bpm} BPM`, note: 'from the source' })
  if (s.score_key || !cover) scored('Key', 'key', s.score_key ?? '')
  if (s.score_meter || !cover) scored('Meter', 'meter', s.score_meter ?? '')
  out.push({ label: 'Length', value: formatTime(s.seconds) })
  if (!cover) field('Target length', 'length')
  field('Vocals', 'vocals')
  if (b.vocals === 'instrumental') {
    field('Melody', 'melody')
    field('Lead instrument', 'lead_instrument')
  } else {
    field('Language', 'language', b.language || s.language)
    field('Voice', 'voice')
    if (!cover || b.vocals === 'new lyrics') field('Lyrics theme', 'theme')
  }
  if (cover) field('Harmony', 'harmony')
  field('Arrangement', 'arrangement', b.arrangement || s.arrangement)
  field(cover ? 'Song flow closeness' : 'Genre closeness', 'closeness', b.closeness === null || b.closeness === undefined ? '' : String(b.closeness))
  if (cover && b.lyrics_closeness !== null && b.lyrics_closeness !== undefined) field('Lyrics closeness', 'lyrics_closeness', String(b.lyrics_closeness))
  field('Lines under the singing', 'lines_under_singing', b.lines_under_singing ? 'on' : 'off')
  if (b.creativity !== null && b.creativity !== undefined) field('Creativity', 'creativity', describeCreativity(b.creativity))
  out.push(...samplingFacts(s))
  out.push({ label: 'Model', value: s.model || 'a recording (Enhance & Master)' })
  if (s.writer) out.push({ label: 'Lyrics and score by', value: s.writer })
  out.push({ label: 'Kind', value: s.kind })
  return out
}

const SAMPLING_LABELS: [SamplingStage, string][] = [
  ['writer', 'Writer temperature'],
  ['arrangement', 'Arrangement temperature'],
  ['plan', 'YuE2 plan sampling'],
  ['take', 'YuE2 take sampling'],
]

/** Numbers written in the workflow while the brief asked for another creativity (owner's report 2026-10-20). */
export const FIXED_NOTE = 'fixed in the workflow, not from the creativity'

/** The sampling the song was made with (owner's request 2026-10-19), marked where it is the reference (50) -
 * or, away from 50, where the workflow had it fixed (a block saved before 1.0.2); a creative mode's plan only
 * when a mode was on. */
export function samplingFacts(s: SongSummary): Fact[] {
  const out: Fact[] = []
  const away = s.brief.creativity !== null && s.brief.creativity !== undefined && s.brief.creativity !== CREATIVITY_REFERENCE
  for (const [stage, label] of SAMPLING_LABELS) {
    const values = s.sampling?.[stage]
    if (!values) continue
    if (stage === 'arrangement' && (!s.brief.arrangement || s.brief.arrangement === 'off')) continue
    const value = stage === 'writer' || stage === 'arrangement' ? String(values.temperature) : describeSampling(values)
    const note = away && values.fixed ? FIXED_NOTE : isReference(stage, values) ? 'the reference' : ''
    out.push({ label, value, note })
  }
  return out
}

/** No brief: what the song's record or file has. */
function plainFacts(s: SongSummary): Fact[] {
  const b = s.brief
  return (
    [
      ['Genre', s.genre],
      ['Mood', s.mood],
      ['Tempo', s.bpm ? `${s.bpm} BPM` : b.tempo ?? ''],
      ['Key', s.score_key || b.key || ''],
      ['Meter', s.score_meter || b.meter || ''],
      ['Length', formatTime(s.seconds)],
      ['Language', s.language],
      ['Artist', s.artist ?? ''],
      ['Album', s.album ?? ''],
      ['Year', s.other ? s.year : ''],
      ['Model', s.other ? '' : s.model || 'a recording (Enhance & Master)'],
      ['Lyrics and score by', s.writer],
      ['Kind', s.other ? 'other music - not made with Plenio' : s.kind],
    ] as [string, string][]
  )
    .filter(([, value]) => value)
    .map(([label, value]) => ({ label, value }))
}
