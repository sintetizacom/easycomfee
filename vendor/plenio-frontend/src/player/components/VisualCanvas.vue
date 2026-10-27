<script setup lang="ts">
/**
 * The visual in motion: picks the scene (visuals/chooser.ts), draws it every frame from the music
 * (engine.frame), and changes it with the song, the section, the interval or a drop - as the settings say -
 * softly: both play on while the new one fades, zooms or slides in, or comes with a flash on the beat, over
 * the time set (visuals/mixer.ts; owner's request 2026-10-18). ``mini`` draws the player bar's little square
 * (``miniScene``).
 */
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

import { mediaReady } from '../api'
import { songHue } from '../colors'
import { engine } from '../engine'
import { lines } from '../now'
import { current, settings } from '../store'
import { chooseVisual } from '../visuals/chooser'
import { dropOptions, dropRenderer } from '../visuals/drop/renderer'
import { myPresets } from '../visuals/drop'
import { tellRenderer } from '../visuals/drop/story'
import { SceneMixer } from '../visuals/mixer'
import { makeColors, miniScene, presetById, type Scene } from '../visuals/presets'

const props = defineProps<{ section?: string; playlistVisual?: string; mini?: boolean; force?: string }>()
const emit = defineEmits<{ change: [id: string] }>()

const canvas = ref<HTMLCanvasElement | null>(null)
const presetId = ref('')
/** The player bar's square draws on its own; the big visual through the mixer. */
let mini: Scene | null = null
const mixer = new SceneMixer((preset) => preset.create())
let raf = 0
let turn = 0
let lastSwitch = performance.now()
let quiet = 0

const hue = computed(() => (current.value ? songHue(current.value.id, current.value.genre) : 200))
/** The song's cover as a picture for the Drop visuals that draw it (owner's request 2026-10-18). */
const cover = shallowRef<HTMLImageElement | null>(null)
watch(
  () => current.value?.id,
  async () => {
    cover.value = null
    const song = current.value
    if (props.mini || !song?.has.cover) return
    const image = new Image()
    image.onload = () => {
      if (current.value?.id === song.id) cover.value = image
    }
    image.src = await mediaReady(song.id, 'cover')
  },
  { immediate: true }
)

/** Play a visual (``again``: the same one anew - a preset file saved while it plays): the change as the
 * visuals' settings say (a crossfade of so many seconds, a zoom, a slide, a flash on the beat, a cut). */
function use(id: string, again = false): void {
  const preset = presetById(id) ?? presetById('bars')
  if (!preset || (preset.id === presetId.value && !again)) return
  mixer.use(preset, { style: settings.visuals.fade, seconds: settings.visuals.fadeSeconds }, again)
  presetId.value = preset.id
  lastSwitch = performance.now()
  if (!props.mini) emit('change', preset.id)
}

/** The visual by the rules (``newTurn``: the song's next change); ``asked``: N or *next* - another one now,
 * even where the song, the playlist or *fixed* keep one (the rules take over again at the next change). */
function pick(newTurn = false, asked = false): void {
  if (props.mini) {
    mini = mini ?? miniScene()
    return
  }
  if (props.force) return use(props.force)
  if (newTurn) turn += 1
  const v = settings.visuals
  use(
    chooseVisual({
      settings: asked ? { ...v, songs: {}, mode: v.mode === 'fixed' ? 'cycle' : v.mode } : v,
      song: current.value,
      playlist: asked ? '' : props.playlistVisual,
      previous: presetId.value || null,
      turn,
    })
  )
}

function resize(): void {
  const el = canvas.value
  if (!el) return
  const ratio = Math.min(props.mini ? 2 : 1.5, window.devicePixelRatio || 1)
  const w = Math.max(1, Math.floor(el.clientWidth * ratio))
  const h = Math.max(1, Math.floor(el.clientHeight * ratio))
  if (el.width !== w || el.height !== h) {
    el.width = w
    el.height = h
  }
}

function loop(): void {
  raf = requestAnimationFrame(loop)
  const el = canvas.value
  if (!el || (props.mini ? !mini : !mixer.preset)) return
  resize()
  const ctx = el.getContext('2d')
  if (!ctx) return
  engine.sensitivity = settings.visuals.sensitivity
  dropOptions.scale = settings.visuals.dropScale
  const frame = engine.frame()
  const colors = makeColors(hue.value, props.mini ? 'song' : settings.visuals.scheme, frame.time)
  if (props.mini && mini) {
    ctx.save()
    mini.draw(ctx, frame, el.width, el.height, colors)
    ctx.restore()
    return
  }
  // a change of Drop preset glides as long as the crossfade
  const renderer = mixer.preset?.kind === 'drop' ? dropRenderer() : null
  if (renderer) {
    renderer.blendSeconds = settings.visuals.fade === 'cut' ? 0.05 : settings.visuals.fadeSeconds
    // the song for the pictures some presets draw: its cover, its title, the line and word sung
    const song = current.value
    tellRenderer(renderer, song ? { id: song.id, title: song.title, cover: cover.value, lines: lines.value } : null, engine.time)
  }
  mixer.draw(ctx, frame, el.width, el.height, colors)
  if (props.force) return
  // the switches during a song: every N seconds, or when the music drops in after a quiet passage
  const v = settings.visuals
  const since = (performance.now() - lastSwitch) / 1000
  if (v.switchOn === 'interval' && frame.playing && since > Math.max(5, v.interval)) pick(true)
  if (v.switchOn === 'drop' && frame.playing) {
    quiet = frame.level < 0.12 ? quiet + frame.dt : Math.max(0, quiet - frame.dt * 0.5)
    if (quiet > 1.5 && frame.bass > 0.45 && frame.beat && since > 6) {
      quiet = 0
      pick(true)
    }
  }
}

watch(() => current.value?.id, () => {
  turn = 0
  pick()
})
watch(() => props.section, (now, before) => {
  if (now && before && now !== before && settings.visuals.switchOn === 'section') pick(true)
})
watch(() => [settings.visuals.mode, settings.visuals.fixed, props.playlistVisual, props.force, current.value ? settings.visuals.songs[current.value.id] : ''], () => pick())

// one of the listener's presets edited and saved while it plays: it changes on screen
watch(myPresets, () => {
  if (presetId.value.startsWith('my-')) use(presetId.value, true)
})

onMounted(() => {
  pick()
  raf = requestAnimationFrame(loop)
})
onBeforeUnmount(() => cancelAnimationFrame(raf))

defineExpose({ presetId, next: () => pick(true, true) })
</script>

<template>
  <canvas ref="canvas" class="visual-canvas" />
</template>

<style scoped>
.visual-canvas {
  width: 100%;
  height: 100%;
  display: block;
}
</style>
