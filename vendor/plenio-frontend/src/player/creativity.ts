/**
 * The brief's creativity (owner's request 2026-10-19): 0 steady ... 50 the reference ... 100 experimental - its
 * levels for the song page and the filters, and the sampling values at 50 (as ``plenio/core/creativity.py``).
 */
import type { SamplingStage, SamplingValues } from './api'

/** The levels by their highest value, as the writer's rules know them. */
export const CREATIVITY_LEVELS: [number, string][] = [
  [19, 'steady'],
  [39, 'restrained'],
  [60, 'balanced'],
  [80, 'varied'],
  [100, 'experimental'],
]

export const CREATIVITY_REFERENCE = 50

export function creativityLevel(value: number): string {
  return CREATIVITY_LEVELS.find(([highest]) => value <= highest)?.[1] ?? 'experimental'
}

/** ``75 - varied``, ``50 - balanced, the reference``. */
export function describeCreativity(value: number): string {
  return `${value} - ${creativityLevel(value)}${value === CREATIVITY_REFERENCE ? ', the reference' : ''}`
}

/** The filter's ranges, with their labels: one level each. */
export const CREATIVITY_RANGES: [string, string][] = [
  ['0-19', 'steady, 0-19'],
  ['20-39', 'restrained, 20-39'],
  ['40-60', 'balanced, 40-60'],
  ['61-80', 'varied, 61-80'],
  ['81-100', 'experimental, 81-100'],
]

/** The values every stage had before the slider - the templates' at 50. */
export const REFERENCE_SAMPLING: Record<SamplingStage, SamplingValues> = {
  writer: { temperature: 0.8 },
  arrangement: { temperature: 0.7 },
  plan: { temperature: 0.7, top_p: 0.9, top_k: 30 },
  take: { temperature: 1, top_p: 0.95, top_k: 100 },
}

/** ``temperature 0.81 · top-p 0.925 · top-k 40``. */
export function describeSampling(values: SamplingValues): string {
  const parts = [`temperature ${values.temperature}`]
  if (values.top_p !== undefined) parts.push(`top-p ${values.top_p}`)
  if (values.top_k !== undefined) parts.push(`top-k ${values.top_k}`)
  return parts.join(' · ')
}

export function isReference(stage: SamplingStage, values: SamplingValues): boolean {
  const reference = REFERENCE_SAMPLING[stage]
  return values.temperature === reference.temperature && values.top_p === reference.top_p && values.top_k === reference.top_k
}
