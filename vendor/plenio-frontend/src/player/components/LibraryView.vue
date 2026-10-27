<script lang="ts">
/** How many songs each library page showed (Show more), while the page is open: a page you come back to shows
 * as many again, so the place you left is still there. */
const shownBefore = new Map<string, { limit: number; list: string }>()
</script>

<script setup lang="ts">
/**
 * The library: a featured song, the search (free words and field filters, with suggestions as you type), the
 * filters - every genre, mood, tag, tempo, length … with how many of the songs shown have it, a click keeping
 * only those, a right click leaving them out (owner's request 2026-10-18: the genres of the templates were
 * missing) - saved filters, tags for the songs shown, the sort, and the songs as a grid or a list.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'

import type { SongSummary } from '../api'
import { isPortable } from '../portable'
import { current, library, playSongs, saveFilter, say, settings, shareFor, state, toggleCurrent } from '../store'
import { countOf, formatTime } from '../timing'
import { chipParts, facetOf, filterRows, fold, lyricsSnippet, parseQuery, score, sortSongs, suggest, toggleFilterChip, valueLabel, type SortKey } from '../search'
import CoverArt from './CoverArt.vue'
import Icon from './Icon.vue'
import SongCard from './SongCard.vue'
import SongMenu from './SongMenu.vue'
import TagEditor from './TagEditor.vue'

const props = defineProps<{ collection: 'all' | 'favorites' | 'top' | 'recent' }>()

// the search and the chips are kept with the settings, one set per view: they are still there after a song's
// page, another window, or a reload - until Reset filters
if (!settings.filters[props.collection]) settings.filters[props.collection] = { query: '', chips: [] }
const filter = computed(() => settings.filters[props.collection] ?? { query: '', chips: [] })
const query = computed({ get: () => filter.value.query, set: (v: string) => (filter.value.query = v) })
const chips = computed(() => filter.value.chips)
const filtered = computed(() => !!query.value.trim() || chips.value.length > 0)
function resetFilters(): void {
  filter.value.query = ''
  filter.value.chips.splice(0)
}
const input = ref<HTMLInputElement | null>(null)
const menu = ref<{ song: SongSummary; x: number; y: number } | null>(null)
const root = ref<HTMLElement | null>(null)
const FIRST = 120
const MORE = 240

const base = computed<SongSummary[]>(() => {
  const all = library.value
  if (props.collection === 'favorites') return state.favorites.map((id) => all.find((s) => s.id === id)).filter((s): s is SongSummary => !!s)
  if (props.collection === 'top') return all.filter((s) => (state.plays[s.id] ?? 0) > 0)
  if (props.collection === 'recent') return all.filter((s) => state.last_played[s.id])
  return all
})

const terms = computed(() => parseQuery([query.value, ...chips.value].join(' ')))
const context = computed(() => ({ favorites: new Set(state.favorites), tags: state.tags, plays: state.plays }))
const scored = computed(() => {
  const map = new Map<string, number>()
  const found = base.value.filter((song) => {
    const value = score(song, terms.value, context.value)
    if (value > 0) map.set(song.id, value)
    return value > 0
  })
  return { found, map }
})
const sortKey = computed<SortKey>(() => {
  if (props.collection === 'top') return 'plays'
  if (props.collection === 'recent') return 'recent'
  if (query.value.trim() && settings.sort === 'newest') return 'relevance'
  return settings.sort as SortKey
})
const songs = computed(() => sortSongs(scored.value.found, sortKey.value, { plays: state.plays, lastPlayed: state.last_played }, scored.value.map))
// a new search, other chips or another sort start with the first songs again - a song that counts a play, or
// one that arrives, changes the songs but not the list you are in (it shrank back to the first 120 before)
const list = computed(() => [query.value.trim(), ...chips.value, sortKey.value].join('\n'))
const kept = shownBefore.get(props.collection)
const limit = ref(kept && kept.list === list.value ? kept.limit : FIRST)
watch(list, () => (limit.value = FIRST))
onBeforeUnmount(() => shownBefore.set(props.collection, { limit: limit.value, list: list.value }))
const shown = computed(() => songs.value.slice(0, limit.value))

// --- the filters ------------------------------------------------------------------------------------------
/** The rows shown before *More filters* (and every row with a chip on). */
const FIRST_ROWS = new Set(['tag', 'genre', 'mood', 'made', 'model'])
/** Rows opened to every value, and the word to look for in one. */
const opened = reactive<Record<string, boolean>>({})
const lookFor = reactive<Record<string, string>>({})
const chipState = (key: string, value: string): 'in' | 'out' | '' => (chips.value.includes(`${key}:"${value}"`) ? 'in' : chips.value.includes(`-${key}:"${value}"`) ? 'out' : '')

interface FacetRow {
  id: string
  key: string
  label: string
  /** Every value among the songs shown (and every chip on), with how many have it. */
  all: [string, number][]
  shown: [string, number][]
  top: number
  on: boolean
}
const facets = computed<FacetRow[]>(() =>
  // the numbers are of the songs the search and the chips leave: a chip says how many would stay
  filterRows(base.value, query.value, chips.value, context.value, scored.value.found).map((row) => {
    const on = row.all.some(([v]) => chipState(row.key, v))
    const want = fold(lookFor[row.id] ?? '')
    const shown = opened[row.id] ? row.all.filter(([v]) => !want || fold(valueLabel(facetOf(row.key, v), v)).includes(want)) : row.all.filter(([v], k) => k < row.top || chipState(row.key, v))
    return { id: row.id, key: row.key, label: row.label, all: row.all, shown, top: row.top, on }
  })
)
const firstRows = computed(() => facets.value.filter((f) => FIRST_ROWS.has(f.id) || f.on))
const moreRows = computed(() => facets.value.filter((f) => !FIRST_ROWS.has(f.id) && !f.on))
const shownRows = computed(() => (settings.moreFilters ? [...firstRows.value, ...moreRows.value] : firstRows.value))
/** ``genre:"dance-pop"`` -> ``Genre: dance-pop``, ``-tag:"x"`` -> ``not Tags: x`` (the active filters' row). */
function chipLabel(chip: string): string {
  const parts = chipParts(chip)
  if (!parts) return chip
  const facet = facetOf(parts.key, parts.value)
  const label = parts.key === 'plenio' ? 'Plenio version' : (facet?.label ?? parts.key)
  return `${parts.exclude ? 'not ' : ''}${label}: ${valueLabel(facet, parts.value)}`
}
/** A click keeps only the songs with that value (again: off); ``exclude`` (a right click) leaves them out. */
function toggleChip(key: string, value: string, exclude = false): void {
  // the kept array itself changes, so the settings save it
  chips.value.splice(0, chips.value.length, ...toggleFilterChip(chips.value, key, value, exclude))
}
function filterByTag(tag: string): void {
  if (!chips.value.includes(`tag:"${tag}"`)) toggleChip('tag', tag)
}

// --- suggestions while typing, a saved filter, tags for the songs shown ---------------------------------------
const typing = ref(false)
const pick = ref(-1)
const suggestions = computed(() => (typing.value ? suggest(query.value, library.value, context.value) : []))
watch(query, () => (pick.value = -1))
function take(text: string): void {
  query.value = text
  pick.value = -1
  void nextTick(() => {
    input.value?.focus()
    input.value?.setSelectionRange(text.length, text.length)
  })
}
function onSearchKey(event: KeyboardEvent): void {
  const list = suggestions.value
  if (!list.length) return
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault()
    pick.value = (pick.value + (event.key === 'ArrowDown' ? 1 : -1) + list.length) % list.length
  } else if ((event.key === 'Enter' || event.key === 'Tab') && pick.value >= 0) {
    event.preventDefault()
    take(list[pick.value].query)
  } else if (event.key === 'Escape') {
    typing.value = false
  }
}
function stopTyping(): void {
  window.setTimeout(() => (typing.value = false), 150)
}
const naming = ref(false)
const filterName = ref('')
function keepFilter(): void {
  const saved = saveFilter(filterName.value || [query.value.trim(), ...chips.value.map(chipLabel)].filter(Boolean).join(', ').slice(0, 60), filter.value)
  naming.value = false
  filterName.value = ''
  say(`Saved: “${saved.name}” - in the sidebar`, 3000)
}
const tagging = ref(false)

// the featured song: one of the newest dozen, a different one each visit
const featured = ref<SongSummary | null>(null)
function feature(): void {
  const pool = library.value.slice(0, 12)
  featured.value = pool.length ? pool[Math.floor(Math.random() * pool.length)] : null
}
watch(library, feature)
onMounted(feature)

const totals = computed(() => ({
  songs: library.value.length,
  time: library.value.reduce((sum, s) => sum + s.seconds, 0),
  favs: state.favorites.length,
}))

const titles: Record<string, string> = { all: 'Your songs', favorites: 'Favourites', top: 'Most played', recent: 'Recently played' }
function play(song: SongSummary): void {
  // the song that plays: its card's button pauses and plays it (it showed pause, and started it anew)
  if (current.value?.id === song.id) return toggleCurrent()
  void playSongs(songs.value.map((s) => s.id), songs.value.indexOf(song))
}
function playAll(shuffle = false): void {
  const ids = songs.value.map((s) => s.id)
  if (shuffle) settings.shuffle = true
  void playSongs(ids, shuffle ? Math.floor(Math.random() * ids.length) : 0)
}
/** The card of the song that plays, when it is among these songs - the list grows by Show more's steps until it
 * holds it (back from a song's page with 1000 songs, the page shows where it plays, not the top). */
async function cardOfCurrent(): Promise<HTMLElement | null> {
  const id = current.value?.id
  const at = id ? songs.value.findIndex((s) => s.id === id) : -1
  if (!id || at < 0) return null
  if (at >= limit.value) limit.value = FIRST + Math.ceil((at + 1 - FIRST) / MORE) * MORE
  await nextTick()
  return root.value?.querySelector<HTMLElement>(`[data-song="${CSS.escape(id)}"]`) ?? null
}
defineExpose({ focus: () => input.value?.focus(), cardOfCurrent, filterByTag })
</script>

<template>
  <div ref="root" class="library">
    <section v-if="collection === 'all' && featured && !query" class="hero">
      <div class="hero-art"><CoverArt :song="featured" live rounded /></div>
      <div class="hero-text">
        <small>Featured</small>
        <h1>{{ featured.title }}</h1>
        <p>{{ [featured.genre, featured.mood, featured.model].filter(Boolean).join(' · ') }}</p>
        <div class="actions">
          <button class="primary" @click="playSongs([featured.id, ...songs.filter((s) => s.id !== featured!.id).map((s) => s.id)])"><Icon name="play" /> Play</button>
          <button class="ghost" @click="playAll(true)"><Icon name="shuffle" /> Shuffle all</button>
          <button class="ghost" @click="feature"><Icon name="dice" /> Another</button>
        </div>
        <p class="stats">{{ countOf(totals.songs, 'song') }} · {{ countOf(Math.round(totals.time / 60), 'minute') }} of music · {{ countOf(totals.favs, 'favourite') }}</p>
      </div>
    </section>
    <h1 v-else class="heading">{{ titles[collection] }}</h1>

    <div class="tools">
      <label class="search">
        <Icon name="search" />
        <input ref="input" v-model="query" placeholder="Search titles, lyrics, genres, #tags … try  bpm:>100  key:Am  is:fav" @focus="typing = true" @input="typing = true" @blur="stopTyping" @keydown="onSearchKey" />
        <button v-if="query" class="icon-btn" @click="query = ''"><Icon name="close" :size="16" /></button>
        <div v-if="suggestions.length" class="suggest" @mousedown.prevent>
          <button v-for="(s, k) in suggestions" :key="s.query" :class="{ on: k === pick }" @click="take(s.query)"><b>{{ s.label }}</b><small>{{ s.hint }}</small></button>
        </div>
      </label>
      <select v-if="collection === 'all' || collection === 'favorites'" v-model="settings.sort" title="Sort">
        <option value="newest">Newest</option>
        <option value="oldest">Oldest</option>
        <option value="title">Title</option>
        <option value="length">Length</option>
        <option value="bpm">Tempo</option>
        <option value="loudness">Loudness</option>
        <option value="plays">Most played</option>
        <option value="recent">Recently played</option>
      </select>
      <div class="views">
        <button class="icon-btn" :class="{ on: settings.view === 'grid' }" title="Grid" @click="settings.view = 'grid'"><Icon name="grid" /></button>
        <button class="icon-btn" :class="{ on: settings.view === 'list' }" title="List" @click="settings.view = 'list'"><Icon name="list" /></button>
      </div>
      <button class="ghost" :disabled="!songs.length" @click="playAll()"><Icon name="play" :size="16" /> Play {{ songs.length }}</button>
      <button v-if="!isPortable" class="ghost" :disabled="!songs.length" title="These songs as one HTML file that plays by itself - to send to others" @click="shareFor = { songs: songs.map((s) => s.id), title: '' }"><Icon name="download" :size="16" /> Share…</button>
      <button class="ghost" :class="{ on: tagging }" :disabled="!songs.length" :title="`Give the ${songs.length} songs shown a tag, or take one off them`" @click="tagging = !tagging"><Icon name="tag" :size="16" /> Tag…</button>
      <button v-if="filtered" class="ghost reset" title="Clear the search and every filter" @click="resetFilters"><Icon name="close" :size="16" /> Reset filters</button>
    </div>

    <div v-if="tagging" class="tagging">
      <p>Tags for the <b>{{ countOf(songs.length, 'song') }}</b> shown{{ filtered ? ' (as filtered)' : '' }}:</p>
      <TagEditor :ids="songs.map((s) => s.id)" autofocus @filter="filterByTag" />
      <button class="icon-btn" title="Close" @click="tagging = false"><Icon name="close" :size="16" /></button>
    </div>

    <div v-if="filtered" class="active">
      <span class="label">Filtered</span>
      <button v-if="query.trim()" class="chip on" title="Clear the search" @click="query = ''">“{{ query.trim() }}” <Icon name="close" :size="12" /></button>
      <button v-for="chip in chips" :key="chip" class="chip on" :class="{ out: chip.startsWith('-') }" title="Remove this filter" @click="chips.splice(chips.indexOf(chip), 1)">
        {{ chipLabel(chip) }} <Icon name="close" :size="12" />
      </button>
      <small>{{ songs.length }} of {{ countOf(base.length, 'song') }}</small>
      <form v-if="naming" class="keep" @submit.prevent="keepFilter">
        <input v-model="filterName" maxlength="80" placeholder="A name for this filter" @keydown.esc="naming = false" />
        <button class="ghost small" type="submit">Save</button>
      </form>
      <button v-else-if="collection === 'all'" class="link" title="Keep this search and these filters under a name - the sidebar lists them" @click="naming = true">Save this filter…</button>
    </div>

    <div class="facets">
      <div v-for="facet in shownRows" :key="facet.id" class="facet" :class="{ wide: opened[facet.id] }">
        <span class="label">{{ facet.label }}</span>
        <div class="values">
          <input v-if="opened[facet.id] && facet.all.length > 16" v-model="lookFor[facet.id]" class="look" :placeholder="`Find a ${facet.label.toLowerCase().replace(/s$/, '')} …`" />
          <button
            v-for="[value, count] in facet.shown"
            :key="value"
            class="chip"
            :class="{ on: chipState(facet.key, value) === 'in', out: chipState(facet.key, value) === 'out' }"
            :title="chipState(facet.key, value) === 'out' ? 'Left out - click to stop leaving them out' : `Click: only these songs · right-click: leave them out`"
            @click="toggleChip(facet.key, value, chipState(facet.key, value) === 'out')"
            @contextmenu.prevent="toggleChip(facet.key, value, true)"
          >
            {{ valueLabel(facetOf(facet.key, value), value) }} <small v-if="chipState(facet.key, value) !== 'out'">{{ count }}</small>
          </button>
          <button v-if="!opened[facet.id] && facet.all.length > facet.shown.length" class="link more-values" @click="opened[facet.id] = true">+ {{ facet.all.length - facet.shown.length }} more</button>
          <button v-else-if="opened[facet.id]" class="link more-values" @click="opened[facet.id] = false; lookFor[facet.id] = ''">fewer</button>
        </div>
      </div>
      <div class="facet-foot">
        <button v-if="moreRows.length" class="link" @click="settings.moreFilters = !settings.moreFilters">{{ settings.moreFilters ? 'Fewer filters' : `More filters: ${moreRows.map((f) => f.label.toLowerCase()).join(', ')}` }}</button>
        <small>Click a chip to keep only those songs, right-click to leave them out. The numbers: how many of the songs shown.</small>
      </div>
    </div>

    <p v-if="!songs.length" class="empty">
      {{ library.length ? 'No song matches - try fewer words or filters.' : 'No Plenio songs in this folder yet. Export one with Export Release, or start the player with --folder.' }}
      <button v-if="library.length && filtered" class="ghost reset-empty" @click="resetFilters">Reset filters</button>
    </p>
    <TransitionGroup tag="div" :class="settings.view === 'grid' ? 'grid' : 'rows'" name="cards">
      <SongCard
        v-for="(song, i) in shown"
        :key="song.id"
        :data-song="song.id"
        :song="song"
        :index="i"
        :list="settings.view === 'list'"
        :snippet="lyricsSnippet(song, terms)"
        :style="{ animationDelay: `${Math.min(i, 24) * 25}ms` }"
        @play="play(song)"
        @menu="menu = { song, x: $event.clientX, y: $event.clientY }"
        @tag="filterByTag"
      />
    </TransitionGroup>
    <button v-if="songs.length > shown.length" class="ghost more" @click="limit += MORE">Show {{ Math.min(MORE, songs.length - shown.length) }} more</button>
    <p class="foot">{{ songs.length }} of {{ countOf(base.length, 'song') }} · {{ formatTime(songs.reduce((t, s) => t + s.seconds, 0)) }}</p>
    <SongMenu v-if="menu" :song="menu.song" :x="menu.x" :y="menu.y" @close="menu = null" />
  </div>
</template>

<style scoped>
.library {
  padding: 26px 34px 40px;
}
.hero {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 30px;
  align-items: center;
  padding: 26px;
  border-radius: 26px;
  background: radial-gradient(circle at 15% 20%, color-mix(in srgb, var(--accent) 35%, transparent), transparent 60%), linear-gradient(135deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.01));
  border: 1px solid rgba(255, 255, 255, 0.06);
  margin-bottom: 26px;
  overflow: hidden;
}
.hero-art {
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.5);
  border-radius: 16px;
}
.hero small {
  font: 700 11px var(--font);
  letter-spacing: 2px;
  text-transform: uppercase;
  color: var(--accent);
}
.hero h1 {
  font: 800 clamp(28px, 3.6vw, 52px) / 1.05 var(--font);
  margin: 8px 0;
  letter-spacing: -0.6px;
}
.hero p {
  color: rgba(255, 255, 255, 0.7);
  margin: 0 0 18px;
}
.stats {
  font-size: 12px;
  color: var(--muted) !important;
  margin: 16px 0 0 !important;
}
.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.heading {
  font: 800 34px var(--font);
  margin: 6px 0 20px;
}
.tools {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.search {
  flex: 1;
  min-width: 260px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 12px;
  height: 42px;
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--muted);
  transition: border-color 0.2s, box-shadow 0.2s;
}
.search:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--accent) 18%, transparent);
}
.search {
  position: relative;
}
.search input {
  flex: 1;
  min-width: 0;
  background: none;
  border: 0;
  outline: none;
  color: #fff;
  font: 14px var(--font);
}
.suggest {
  position: absolute;
  z-index: 30;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  display: grid;
  padding: 6px;
  border-radius: 14px;
  background: rgba(20, 18, 30, 0.98);
  border: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.55);
}
.suggest button {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 7px 10px;
  border: 0;
  border-radius: 8px;
  background: none;
  color: #ddd;
  cursor: pointer;
  font: 13px var(--font);
  text-align: left;
}
.suggest button b {
  font: 600 13px var(--mono);
  color: #fff;
}
.suggest button small {
  color: var(--muted);
}
.suggest button:hover,
.suggest button.on {
  background: color-mix(in srgb, var(--accent) 20%, transparent);
}
.tagging {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  margin-bottom: 14px;
  border-radius: 14px;
  border: 1px solid color-mix(in srgb, var(--accent) 40%, transparent);
  background: color-mix(in srgb, var(--accent) 7%, transparent);
}
.tagging p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
.tagging .tag-editor {
  flex: 1;
}
.chip.out {
  border-color: rgba(255, 120, 120, 0.7);
  background: rgba(255, 90, 90, 0.12);
  color: #ffb4b4;
  text-decoration: line-through;
}
.link {
  background: none;
  border: 0;
  padding: 0;
  color: var(--accent);
  cursor: pointer;
  font: 12px var(--font);
}
.more-values {
  margin-left: 4px;
}
.look {
  width: 170px;
  height: 28px;
  padding: 0 10px;
  border-radius: 99px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: #fff;
  font: 12px var(--font);
}
.facet-foot {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  align-items: center;
  margin-top: 2px;
  padding-left: 102px;
}
.facet-foot small {
  color: var(--muted);
  font-size: 11px;
}
.keep {
  display: flex;
  gap: 6px;
}
.keep input {
  height: 30px;
  width: 220px;
  padding: 0 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--accent);
  color: #fff;
  font: 13px var(--font);
}
.ghost.small {
  height: 30px;
  padding: 0 12px;
  font-size: 12px;
}
select {
  height: 38px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.06);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.08);
  padding: 0 10px;
  font: 13px var(--font);
}
.views {
  display: flex;
  gap: 2px;
}
.facets {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 20px;
}
.facet {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 6px;
  align-items: start;
}
.facet .values {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.facet .label {
  padding-top: 7px;
  font: 600 11px var(--font);
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.6px;
}
.chip small {
  opacity: 0.55;
  margin-left: 2px;
}
.active {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin: -4px 0 12px;
}
.active .label {
  width: 96px;
  font: 600 11px var(--font);
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.6px;
}
.active small {
  color: var(--muted);
  font-size: 12px;
  margin-left: 4px;
}
.reset {
  border-color: color-mix(in srgb, var(--accent) 60%, transparent);
}
.reset-empty {
  margin: 14px auto 0;
  display: flex;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
  gap: 16px;
}
.rows {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.empty {
  color: var(--muted);
  padding: 40px 0;
  text-align: center;
}
.more {
  margin: 24px auto 0;
  display: flex;
}
.foot {
  text-align: center;
  color: var(--muted);
  font-size: 12px;
  margin-top: 24px;
}
.cards-move {
  transition: transform 0.4s cubic-bezier(0.2, 0.8, 0.2, 1);
}
/* a card that leaves goes at once (its entry animation made the list wait half a second, the old cards still
   showing beside the new) */
.cards-leave-active {
  animation: none;
  transition: none;
}
@media (max-width: 760px) {
  .hero {
    grid-template-columns: 1fr;
  }
  .facet {
    grid-template-columns: 1fr;
  }
  .active .label {
    width: 100%;
  }
  .facet-foot {
    padding-left: 0;
  }
}
</style>
