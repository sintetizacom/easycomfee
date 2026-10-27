<script setup lang="ts">
/**
 * The Plenio Player: the sidebar, the page of the route (the library and its smart lists, a song, the
 * playlists, a playlist), the bar at the bottom, the queue from the right and Now playing over everything.
 * Keyboard: Space, arrows, F, V, N, L, S, R, B, M, Q, /, 1-4, Esc, ? - shown with ?.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import LibraryView from './components/LibraryView.vue'
import NowPlaying from './components/NowPlaying.vue'
import PlayerBar from './components/PlayerBar.vue'
import PlaylistView from './components/PlaylistView.vue'
import PlaylistsView from './components/PlaylistsView.vue'
import SettingsView from './components/SettingsView.vue'
import LiveView from './components/LiveView.vue'
import JobsView from './components/JobsView.vue'
import VideoDialog from './components/VideoDialog.vue'
import ShareDialog from './components/ShareDialog.vue'
import QueuePanel from './components/QueuePanel.vue'
import RemoveDialog from './components/RemoveDialog.vue'
import Sidebar from './components/Sidebar.vue'
import SongView from './components/SongView.vue'
import Icon from './components/Icon.vue'
import GuestWayIn from './components/GuestWayIn.vue'
import { guestBig, loadGuests } from './guests'
import { api } from './api'
import { engine } from './engine'
import { paletteStyle } from './now'
import {
  current,
  go,
  library,
  loadError,
  loading,
  next,
  openCurrentPage,
  nowPlayingOpen,
  previous,
  removing,
  route,
  say,
  setVolume,
  toast,
  settings,
  toggleAB,
  toggleFavorite,
  videoFor,
  shareFor,
  toggleMute,
} from './store'
import { loadMyPresets } from './visuals/drop'
import { loadJobs, videosAtWork } from './jobs'
import './live'
import { isPortable } from './portable'

const queueOpen = ref(false)
const help = ref(false)
/** The bar's height: the queue ends above it (the bar is taller in a narrow window). */
const bar = ref<InstanceType<typeof PlayerBar> | null>(null)
const barHeight = ref(96)
let barWatch: ResizeObserver | undefined
/** The sidebar as a drawer in a narrow window (below 860 px it has no room of its own); a new page closes it. */
const drawer = ref(false)
const main = ref<HTMLElement | null>(null)
const libraryView = ref<InstanceType<typeof LibraryView> | null>(null)
const nowPlaying = ref<InstanceType<typeof NowPlaying> | null>(null)

const page = computed(() => {
  const [, first = '', second = ''] = route.value.split('/')
  if (first === 'song' && second) return { kind: 'song' as const, id: decodeURIComponent(second) }
  if (first === 'playlist' && second) return { kind: 'playlist' as const, id: decodeURIComponent(second) }
  if (first === 'playlists') return { kind: 'playlists' as const }
  if (first === 'settings') return { kind: 'settings' as const }
  if (first === 'live') return { kind: 'live' as const }
  if (first === 'jobs') return { kind: 'jobs' as const }
  if (first === 'favorites' || first === 'top' || first === 'recent') return { kind: 'library' as const, collection: first as 'favorites' | 'top' | 'recent' }
  return { kind: 'library' as const, collection: 'all' as const }
})
watch(page, () => (drawer.value = false))
// a page opens at its top - except a library page you come back to, which is where you left it; and when the
// song that plays is not in sight there, the page goes to it (owner's request 2026-10-17: back from a song's
// page with 1000 songs, the place of the song that plays - not the top again)
const scrolls = new Map<string, number>()
watch(route, (now, before) => {
  if (before !== undefined && main.value) scrolls.set(before, main.value.scrollTop)
  const keep = !now.startsWith('/song/') && !now.startsWith('/record/')
  void nextTick(async () => {
    const box = main.value
    if (!box) return
    box.scrollTo({ top: keep ? (scrolls.get(now) ?? 0) : 0, behavior: 'instant' as ScrollBehavior })
    const card = page.value.kind === 'library' ? await libraryView.value?.cardOfCurrent() : null
    if (!card) return
    const at = card.getBoundingClientRect()
    const view = box.getBoundingClientRect()
    if (at.top < view.top || at.bottom > view.bottom) card.scrollIntoView({ block: 'center', behavior: 'instant' as ScrollBehavior })
    card.classList.add('found')
    window.setTimeout(() => card.classList.remove('found'), 1400)
  })
})

// ComfyUI's Export Release opens the player at a song by its record file: #/record/<path> -> its page
watch(
  [route, library],
  async ([path]) => {
    if (!path.startsWith('/record/') || !library.value.length) return
    const record = decodeURIComponent(path.slice('/record/'.length))
    try {
      const { id } = await api.find(record)
      go(`/song/${id}`, true)
    } catch {
      go('/', true)
      say('That song is not in the library (yet) - Look for new songs, or check the folders in Settings.', 5000)
    }
  },
  { immediate: true }
)

const KEYS: [string, string][] = [
  ['Space', 'Play / pause'],
  ['← →', 'Back / ahead 5 seconds'],
  ['Shift ← →', 'Previous / next song'],
  ['↑ ↓', 'Louder / quieter'],
  ['F', 'Now playing'],
  ['Shift F', 'Only the visual, full screen'],
  ['I', 'The page of the song that plays'],
  ['1 – 4', 'Stage, lyrics, notation, visual'],
  ['V', 'The visuals’ settings'],
  ['N', 'Another visual'],
  ['L', 'Favourite'],
  ['S', 'Shuffle'],
  ['R', 'Repeat: the whole playlist, this song, off'],
  ['B', 'A/B: master or unmastered take'],
  ['M', 'Mute'],
  ['Q', 'The queue'],
  ['/', 'Search'],
  ['Esc', 'Close'],
]

function onKey(event: KeyboardEvent): void {
  const target = event.target as HTMLElement
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable
  if (event.key === 'Escape') {
    // Esc leaves a text field first; a list (select) that was chosen from does not hold it back
    if (typing && target.tagName !== 'SELECT') (target as HTMLInputElement).blur()
    else if (guestBig.value) guestBig.value = false
    else if (removing.value) removing.value = null
    else if (help.value) help.value = false
    else if (queueOpen.value) queueOpen.value = false
    else if (nowPlayingOpen.value) nowPlayingOpen.value = false
    return
  }
  if (typing || event.ctrlKey || event.metaKey || event.altKey) return
  const key = event.key.length === 1 ? event.key.toLowerCase() : event.key
  switch (key) {
    case ' ':
      event.preventDefault()
      void engine.toggle()
      break
    case 'ArrowLeft':
      event.preventDefault()
      if (event.shiftKey) void previous()
      else engine.seek(engine.time - 5)
      break
    case 'ArrowRight':
      event.preventDefault()
      if (event.shiftKey) void next()
      else engine.seek(engine.time + 5)
      break
    case 'ArrowUp':
    case 'ArrowDown':
      event.preventDefault()
      setVolume(settings.volume + (key === 'ArrowUp' ? 0.05 : -0.05))
      say(`Volume ${Math.round(settings.volume * 100)} %`)
      break
    case 'f':
      if (event.shiftKey) visualFullscreen()
      else nowPlayingOpen.value = !nowPlayingOpen.value
      break
    case 'v':
      nowPlayingOpen.value = true
      void nextTick(() => nowPlaying.value?.togglePanel())
      break
    case 'n':
      nowPlaying.value?.nextVisual()
      break
    case '1':
    case '2':
    case '3':
    case '4':
      nowPlayingOpen.value = true
      void nextTick(() => nowPlaying.value?.setView((['stage', 'lyrics', 'notation', 'visual'] as const)[Number(key) - 1]))
      break
    case 'i':
      openCurrentPage()
      break
    case 'l':
      if (current.value) {
        toggleFavorite(current.value.id)
        say('♥')
      }
      break
    case 's':
      settings.shuffle = !settings.shuffle
      say(settings.shuffle ? 'Shuffle on' : 'Shuffle off')
      break
    case 'r':
      settings.repeat = settings.repeat === 'all' ? 'one' : settings.repeat === 'one' ? 'off' : 'all'
      say({ all: 'Repeat: the whole playlist', one: 'Repeat: this song', off: 'Repeat off' }[settings.repeat])
      break
    case 'b':
      toggleAB()
      break
    case 'm':
      toggleMute()
      break
    case 'q':
      queueOpen.value = !queueOpen.value
      break
    case '/':
      event.preventDefault()
      nowPlayingOpen.value = false
      if (page.value.kind !== 'library') go('/')
      void nextTick(() => libraryView.value?.focus())
      break
    case '?':
      help.value = !help.value
      break
  }
}
function visualFullscreen(): void {
  nowPlayingOpen.value = true
  void nextTick(() => nowPlaying.value?.visualFullscreen())
}

/** A video in the queue is drawn by this page: closing it stops the video, so the browser asks first. */
function beforeLeave(event: BeforeUnloadEvent): void {
  if (!videosAtWork.value) return
  event.preventDefault()
  event.returnValue = ''
}

// the listener's own Plenio Drop presets: read now, and again every few seconds (a file saved shows at once)
let presetTimer: number | undefined
onMounted(() => {
  window.addEventListener('keydown', onKey)
  window.addEventListener('beforeunload', beforeLeave)
  // the shared players the player is making or made (also before this page opened)
  void loadJobs()
  const el = bar.value?.$el as HTMLElement | undefined
  if (el && typeof ResizeObserver !== 'undefined') {
    barWatch = new ResizeObserver(() => (barHeight.value = Math.round(el.getBoundingClientRect().height)))
    barWatch.observe(el)
  }
  void loadMyPresets()
  // the guests' access as it was left: on, the page tells the guests what plays again
  void loadGuests()
  if (!isPortable) presetTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void loadMyPresets()
  }, 3000)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('beforeunload', beforeLeave)
  barWatch?.disconnect()
  clearInterval(presetTimer)
})
</script>

<template>
  <div class="app" :class="{ 'no-side': !settings.sidebar }" :style="[paletteStyle, { '--bar-height': `${barHeight}px` }]">
    <div class="ambient" />
    <Sidebar v-if="settings.sidebar" class="sidebar" :class="{ open: drawer }" />
    <button class="menu-btn icon-btn" :class="{ open: drawer }" :title="drawer ? 'Close the menu' : 'Menu: songs, playlists, Live Play, settings'" @click="drawer = !drawer"><Icon :name="drawer ? 'close' : 'list'" /></button>
    <div v-if="drawer" class="drawer-veil" @click="drawer = false" />
    <main ref="main" class="main">
      <div v-if="loading && !library.length" class="splash">
        <span class="logo"><i /><i /><i /><i /><i /></span>
        <p>Looking for your songs …</p>
      </div>
      <div v-else-if="loadError" class="splash error">
        <p>The player’s server does not answer: {{ loadError }}</p>
        <p class="hint">Start it with <code>python -m plenio.player</code>.</p>
      </div>
      <template v-else>
        <SongView v-if="page.kind === 'song'" :id="page.id" />
        <PlaylistView v-else-if="page.kind === 'playlist'" :id="page.id" />
        <PlaylistsView v-else-if="page.kind === 'playlists'" />
        <SettingsView v-else-if="page.kind === 'settings'" />
        <LiveView v-else-if="page.kind === 'live'" />
        <JobsView v-else-if="page.kind === 'jobs'" />
        <LibraryView v-else ref="libraryView" :key="page.collection" :collection="page.collection" />
      </template>
    </main>
    <PlayerBar ref="bar" class="playerbar" @queue="queueOpen = !queueOpen" @visual="visualFullscreen" />
    <VideoDialog v-if="videoFor" :song="videoFor" @close="videoFor = null" />
    <ShareDialog v-if="shareFor" :songs="shareFor.songs" :title="shareFor.title" @close="shareFor = null" />
    <Transition name="slide"><QueuePanel v-if="queueOpen" class="queue" @close="queueOpen = false" /></Transition>
    <Transition name="np"><NowPlaying v-if="nowPlayingOpen" ref="nowPlaying" /></Transition>
    <Transition name="fade">
      <div v-if="help" class="help" @click="help = false">
        <div class="keys" @click.stop>
          <h3>Keys</h3>
          <dl><template v-for="[k, what] in KEYS" :key="k"><dt><kbd>{{ k }}</kbd></dt><dd>{{ what }}</dd></template></dl>
          <p class="hint">Search: words find titles, lyrics, genres, moods; fields narrow it - <code>genre:jazz</code> <code>bpm:&gt;110</code> <code>key:Am</code> <code>model:yue</code> <code>lang:german</code> <code>is:fav</code> <code>has:pdf</code> <code>#party</code> <code>is:unplayed</code> <code>-word</code> <code>"a phrase"</code>. A filter chip: click keeps only those songs, right-click leaves them out.</p>
        </div>
      </div>
    </Transition>
    <Transition name="fade"><GuestWayIn v-if="guestBig" big /></Transition>
    <Transition name="fade"><div v-if="toast" class="toast">{{ toast }}</div></Transition>
    <Transition name="fade"><RemoveDialog v-if="removing" :song="removing" @close="removing = null" @done="say" /></Transition>
  </div>
</template>

<style scoped>
.app {
  position: fixed;
  inset: 0;
  display: grid;
  /* minmax(0, ...): a wide child scrolls or wraps inside the page instead of widening it */
  grid-template-columns: 240px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr) auto;
  grid-template-areas: 'side main' 'bar bar';
  background: #0a0910;
}
.app.no-side {
  grid-template-columns: minmax(0, 1fr);
  grid-template-areas: 'main' 'bar';
}
.ambient {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: radial-gradient(1200px 600px at 75% -10%, color-mix(in srgb, var(--accent) 22%, transparent), transparent 70%),
    radial-gradient(900px 500px at 0% 110%, color-mix(in srgb, var(--accent2) 14%, transparent), transparent 70%), var(--deep);
  transition: background 1.2s;
}
.sidebar {
  grid-area: side;
  position: relative;
  min-height: 0;
}
.main {
  grid-area: main;
  position: relative;
  overflow-y: auto;
  min-height: 0;
  scroll-behavior: smooth;
}
.playerbar {
  grid-area: bar;
  position: relative;
  z-index: 10;
}
.app .queue {
  position: fixed;
  top: 0;
  right: 0;
  bottom: var(--bar-height, 96px);
  height: auto;
  z-index: 40;
}
.splash {
  height: 100%;
  display: grid;
  place-content: center;
  justify-items: center;
  color: var(--muted);
  gap: 14px;
}
.splash.error {
  color: #ff9a9a;
}
.splash .logo {
  display: flex;
  gap: 5px;
  align-items: flex-end;
  height: 40px;
}
.splash .logo i {
  width: 7px;
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(var(--accent), var(--accent2));
  transform-origin: bottom;
  animation: bounce 1s ease-in-out infinite;
}
.splash .logo i:nth-child(2) {
  animation-delay: -0.2s;
}
.splash .logo i:nth-child(3) {
  animation-delay: -0.4s;
}
.splash .logo i:nth-child(4) {
  animation-delay: -0.6s;
}
.splash .logo i:nth-child(5) {
  animation-delay: -0.8s;
}
.hint {
  color: var(--muted);
  font-size: 12px;
  line-height: 1.6;
}
.help {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(6px);
}
.keys {
  width: min(560px, 92vw);
  background: rgba(18, 16, 28, 0.97);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 18px;
  padding: 20px 24px;
}
.keys h3 {
  margin: 0 0 12px;
}
.keys dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 16px;
  margin: 0 0 12px;
  font-size: 13px;
}
.keys dd {
  margin: 0;
  color: rgba(255, 255, 255, 0.8);
}
kbd,
code {
  font: 12px var(--mono);
  background: rgba(255, 255, 255, 0.08);
  border-radius: 5px;
  padding: 1px 6px;
}
.toast {
  position: fixed;
  left: 50%;
  top: 40px;
  transform: translateX(-50%);
  z-index: 95;
  padding: 8px 16px;
  border-radius: 99px;
  background: rgba(20, 18, 30, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.1);
  font: 600 13px var(--font);
}
.slide-enter-active,
.slide-leave-active {
  transition: transform 0.35s cubic-bezier(0.2, 0.8, 0.2, 1), opacity 0.35s;
}
.slide-enter-from,
.slide-leave-to {
  transform: translateX(40px);
  opacity: 0;
}
.np-enter-active,
.np-leave-active {
  transition: opacity 0.45s, transform 0.55s cubic-bezier(0.2, 0.8, 0.2, 1);
}
.np-enter-from,
.np-leave-to {
  opacity: 0;
  transform: translateY(40px) scale(0.98);
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
@keyframes bounce {
  0%,
  100% {
    transform: scaleY(0.3);
  }
  50% {
    transform: scaleY(1);
  }
}
.menu-btn,
.drawer-veil {
  display: none;
}
/* a narrow window: the sidebar becomes a drawer behind the menu button (it had no way back before) */
@media (max-width: 860px) {
  .app {
    grid-template-columns: minmax(0, 1fr);
    grid-template-areas: 'main' 'bar';
  }
  .sidebar {
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    width: 260px;
    z-index: 45;
    background: #120f1c;
    transform: translateX(-105%);
    transition: transform 0.22s ease;
    box-shadow: 20px 0 60px rgba(0, 0, 0, 0.5);
  }
  .sidebar.open {
    transform: none;
  }
  .menu-btn {
    display: grid;
    position: fixed;
    top: 10px;
    left: 10px;
    z-index: 46;
    background: rgba(18, 15, 28, 0.85);
    backdrop-filter: blur(8px);
  }
  /* open: beside the drawer, not over its logo */
  .menu-btn.open {
    left: 270px;
  }
  .drawer-veil {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 44;
    background: rgba(0, 0, 0, 0.45);
  }
  .main > * {
    padding-top: 56px;
  }
}
</style>
