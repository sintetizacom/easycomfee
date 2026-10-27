<script setup lang="ts">
/**
 * The visuals' settings: the mode (auto, random from a choice, cycle, fixed), when it changes, the colours,
 * the sensitivity - and a visual of its own for this song or for the playlist that plays. Plenio Drop's
 * quality, and the listener's own Drop presets: the folder, the files that do not work and why, a copy of a
 * preset to edit.
 */
import { computed, ref } from 'vue'

import { guestStatus } from '../guests'
import { current, queueSource, say, settings, state } from '../store'
import { CLASSIC, PRESETS, allPresets, presetById, type Preset, type Scheme } from '../visuals/presets'
import type { SwitchOn, VisualMode } from '../visuals/chooser'
import { FADE_STYLES } from '../visuals/mixer'
import { copyToMyPresets, myPresetErrors, myPresetFile, myPresetFolder, myPresets, openMyPresetFolder, playingFile } from '../visuals/drop'
import Icon from './Icon.vue'
import { isPortable } from '../portable'

const props = defineProps<{ active: string }>()
const emit = defineEmits<{ close: []; next: []; fullscreen: [] }>()

const GUIDE = 'https://github.com/jplenio/Plenio-Music-Production-System/blob/main/docs/user/concepts/player-visuals.md'
const QUALITY: [number, string][] = [
  [0.5, 'Fast - for a slow computer'],
  [0.75, 'Balanced'],
  [1, 'Sharp - every pixel'],
]
const GROUPS = computed<[string, string, Preset[]][]>(() => [
  ['classic', 'Classic', CLASSIC],
  ['drop', 'Plenio Drop', PRESETS.filter((p) => p.kind === 'drop')],
  ['mine', 'My presets', myPresets.value],
])
const everything = computed(() => allPresets())
const activePreset = computed(() => presetById(props.active))
const copying = ref(false)

const v = settings.visuals
const MODES: [VisualMode, string, string][] = [
  ['auto', 'Match the music', 'A visual that suits the song’s genre, mood and tempo'],
  ['random', 'Random', 'From the visuals ticked below'],
  ['cycle', 'Cycle', 'Through the ticked visuals in turn'],
  ['fixed', 'Fixed', 'Always the same visual'],
]
const SWITCHES: [SwitchOn, string][] = [
  ['song', 'With every song'],
  ['section', 'At every section (verse, chorus …)'],
  ['interval', 'Every few seconds - also within a song'],
  ['drop', 'When the music drops in'],
]
const SCHEMES: [Scheme, string][] = [
  ['song', 'The song’s colours'],
  ['winamp', 'Winamp classic'],
  ['neon', 'Neon'],
  ['sunset', 'Sunset'],
  ['mono', 'Monochrome'],
]

const playlist = computed(() => state.playlists.find((p) => p.id === queueSource.value) ?? null)
const songOwn = computed(() => (current.value ? v.songs[current.value.id] ?? '' : ''))

function togglePool(id: string): void {
  const at = v.pool.indexOf(id)
  if (at >= 0 && v.pool.length > 1) v.pool.splice(at, 1)
  else if (at < 0) v.pool.push(id)
}
function setSong(id: string): void {
  if (!current.value) return
  if (id) v.songs[current.value.id] = id
  else delete v.songs[current.value.id]
}
function setPlaylist(id: string): void {
  if (playlist.value) playlist.value.visual = id
}
/** Tick or untick a whole group (at least one visual stays ticked). */
function tickGroup(list: Preset[], on: boolean): void {
  for (const p of list) {
    const at = v.pool.indexOf(p.id)
    if (on && at < 0) v.pool.push(p.id)
    if (!on && at >= 0 && v.pool.length > 1) v.pool.splice(at, 1)
  }
}
async function editCopy(): Promise<void> {
  const file = playingFile.value ?? activePreset.value?.file
  if (!file || copying.value) return
  copying.value = true
  try {
    const saved = await copyToMyPresets(file)
    say(`Saved as ${saved} in your visuals folder (Open my folder) - edit it, save, and it changes on screen.`, 7000)
  } catch (error) {
    say(error instanceof Error ? error.message : String(error), 6000)
  } finally {
    copying.value = false
  }
}
</script>

<template>
  <aside class="panel">
    <header>
      <h3><Icon name="sparkles" /> Visuals</h3>
      <button class="icon-btn" title="Close" @click="emit('close')"><Icon name="close" /></button>
    </header>
    <div class="now">
      Now: <b>{{ activePreset?.name ?? '-' }}</b>
      <button class="chip" title="Another visual (N)" @click="emit('next')"><Icon name="dice" :size="14" /> next</button>
      <button class="chip" title="Only the visual, on the whole screen (Shift+F, or double-click the visual)" @click="emit('fullscreen')"><Icon name="expand" :size="14" /> full screen</button>
    </div>

    <label class="row switch"><input v-model="v.enabled" type="checkbox" /> Visuals on</label>

    <h4>Mode</h4>
    <div class="modes">
      <button v-for="[id, label, hint] in MODES" :key="id" class="mode" :class="{ on: v.mode === id }" :title="hint" @click="v.mode = id">
        {{ label }}<small>{{ hint }}</small>
      </button>
    </div>

    <template v-if="v.mode === 'fixed'">
      <h4>The visual</h4>
      <select v-model="v.fixed">
        <optgroup v-for="[id, label, list] in GROUPS" :key="id" :label="label">
          <option v-for="p in list" :key="p.id" :value="p.id">{{ p.name }}</option>
        </optgroup>
      </select>
    </template>

    <template v-if="v.mode !== 'fixed'">
      <h4>Change</h4>
      <select v-model="v.switchOn">
        <option v-for="[id, label] in SWITCHES" :key="id" :value="id">{{ label }}</option>
      </select>
      <div v-if="v.switchOn === 'interval'" class="row">
        every <input v-model.number="v.interval" type="number" min="5" max="600" /> seconds
        <button v-for="s in [10, 20, 30, 60]" :key="s" class="chip" :class="{ on: v.interval === s }" @click="v.interval = s">{{ s }} s</button>
      </div>
    </template>

    <h4>Crossfade</h4>
    <select v-model="v.fade" title="How one visual turns into the next - with a new song, a new section, or N">
      <option v-for="[id, label, hint] in FADE_STYLES" :key="id" :value="id" :title="hint">{{ label }}</option>
    </select>
    <label v-if="v.fade !== 'cut'" class="row" :title="v.fade === 'flash' ? 'How long the flash fades' : 'How long the change takes'">
      {{ v.fade === 'flash' ? 'Flash' : 'Over' }} <input v-model.number="v.fadeSeconds" type="range" min="0.5" max="8" step="0.5" /> {{ v.fadeSeconds }} s
    </label>
    <p class="note tight">{{ FADE_STYLES.find(([id]) => id === v.fade)?.[2] }}. Both visuals play on while it changes; from one Plenio Drop preset to another the picture stays and its motion turns into the new one.</p>

    <h4>{{ v.mode === 'auto' ? 'Choose from' : v.mode === 'fixed' ? 'All visuals' : 'Ticked visuals' }}</h4>
    <template v-for="[id, label, list] in GROUPS" :key="id">
      <div v-if="list.length" class="group">
        <span>{{ label }}</span>
        <button class="link" @click="tickGroup(list, true)">all</button>
        <button class="link" @click="tickGroup(list, false)">none</button>
      </div>
      <div class="pool">
        <label v-for="p in list" :key="p.id" class="preset" :class="{ on: v.pool.includes(p.id), now: p.id === active }" :title="p.blurb">
          <input type="checkbox" :checked="v.pool.includes(p.id)" @change="togglePool(p.id)" />
          <span class="name">{{ p.name }}</span>
          <span class="blurb">{{ p.blurb }}</span>
        </label>
      </div>
    </template>

    <h4>Plenio Drop</h4>
    <label class="row">Quality
      <select v-model.number="v.dropScale" title="How finely Plenio Drop draws: Fast draws a quarter of the pixels, and every computer keeps up">
        <option v-for="[scale, label] in QUALITY" :key="scale" :value="scale">{{ label }}</option>
      </select>
    </label>
    <p class="note">MilkDrop-style visuals, drawn by Plenio itself. Write your own: a preset is a short JSON file - <a :href="GUIDE" target="_blank" rel="noopener">the guide</a>.</p>
    <div v-if="!isPortable" class="drop-tools">
      <button class="chip" :disabled="!activePreset?.file || copying" :title="activePreset?.file ? `A copy of ${activePreset.name} in your visuals folder, to change` : 'Play a Plenio Drop visual to copy it'" @click="editCopy">
        <Icon name="edit" :size="14" /> Edit a copy
      </button>
      <button class="chip" title="Your visuals folder: every .json file there is a visual of your own" @click="openMyPresetFolder"><Icon name="folder" :size="14" /> Open my folder</button>
    </div>
    <p v-if="myPresetFile(active)" class="note">Playing your file <code>{{ myPresetFile(active) }}</code> - save it and it changes here.</p>
    <p v-if="myPresetFolder" class="note path">{{ myPresetFolder }}</p>
    <div v-for="e in myPresetErrors" :key="e.file" class="bad"><b>{{ e.file }}</b> {{ e.error }}</div>

    <h4>This song</h4>
    <select :value="songOwn" @change="setSong(($event.target as HTMLSelectElement).value)">
      <option value="">As the mode says</option>
      <option v-for="p in everything" :key="p.id" :value="p.id">Always {{ p.name }}</option>
    </select>
    <template v-if="playlist">
      <h4>The playlist “{{ playlist.name }}”</h4>
      <select :value="playlist.visual ?? ''" @change="setPlaylist(($event.target as HTMLSelectElement).value)">
        <option value="">As the mode says</option>
        <option v-for="p in everything" :key="p.id" :value="p.id">Always {{ p.name }}</option>
      </select>
    </template>

    <h4>Look</h4>
    <select v-model="v.scheme">
      <option v-for="[id, label] in SCHEMES" :key="id" :value="id">{{ label }}</option>
    </select>
    <label class="row">Sensitivity <input v-model.number="v.sensitivity" type="range" min="0.5" max="2" step="0.05" /></label>
    <label class="row switch"><input v-model="v.lyrics" type="checkbox" /> Lyrics over the visual</label>
    <label class="row switch"><input v-model="v.titles" type="checkbox" /> Title card when a song starts</label>
    <label v-if="guestStatus?.on" class="row switch" title="The QR code and address of the live playlist over the visual (its corner and size: Live Play > Guests)"><input v-model="settings.live.overVisual" type="checkbox" /> The guests' way in over the visual</label>
    <p class="note">A song’s own visual wins, then the playlist’s, then the mode.</p>
  </aside>
</template>

<style scoped>
.panel {
  width: 340px;
  max-height: 100%;
  overflow-y: auto;
  background: rgba(14, 12, 22, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 18px;
  padding: 16px 18px 20px;
  backdrop-filter: blur(20px);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
  font: 13px var(--font);
  color: #ddd;
}
header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
h3 {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 0;
  font: 600 16px var(--font);
  color: #fff;
}
h4 {
  margin: 14px 0 6px;
  font: 600 11px var(--font);
  text-transform: uppercase;
  letter-spacing: 0.7px;
  color: var(--muted);
}
.now {
  margin: 8px 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.now b {
  color: var(--accent);
}
.modes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.mode {
  text-align: left;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
  color: #eee;
  border-radius: 10px;
  padding: 8px 10px;
  cursor: pointer;
  font: 600 12px var(--font);
}
.mode small {
  display: block;
  font-weight: 400;
  color: var(--muted);
  font-size: 11px;
  margin-top: 2px;
}
.mode.on {
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 18%, transparent);
}
select,
input[type='number'] {
  width: 100%;
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  padding: 6px 8px;
  font: 13px var(--font);
}
input[type='number'] {
  width: 70px;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
}
.row input[type='range'] {
  flex: 1;
  accent-color: var(--accent);
}
.pool {
  display: grid;
  gap: 4px;
}
.preset {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid transparent;
}
.preset:hover {
  background: rgba(255, 255, 255, 0.04);
}
.preset.now {
  border-color: color-mix(in srgb, var(--accent) 60%, transparent);
}
.preset input {
  grid-row: span 2;
  accent-color: var(--accent);
}
.name {
  font-weight: 600;
  color: #fff;
}
.blurb {
  color: var(--muted);
  font-size: 11px;
}
.note {
  color: var(--muted);
  font-size: 11px;
  margin-top: 14px;
}
.note a {
  color: var(--accent);
}
.note.tight {
  margin-top: 2px;
}
.note.path {
  margin-top: 4px;
  word-break: break-all;
}
.group {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 10px 0 4px;
  font: 600 12px var(--font);
  color: #fff;
}
.group span {
  flex: 1;
}
.link {
  background: none;
  border: 0;
  padding: 0;
  color: var(--accent);
  cursor: pointer;
  font: 12px var(--font);
}
.drop-tools {
  display: flex;
  gap: 6px;
  margin-top: 8px;
}
.chip:disabled {
  opacity: 0.45;
  cursor: default;
}
.bad {
  margin-top: 6px;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(255, 90, 90, 0.12);
  color: #ffb4b4;
  font-size: 11px;
  word-break: break-word;
}
.bad b {
  color: #fff;
  margin-right: 4px;
}
</style>
