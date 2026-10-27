<script setup lang="ts">
/**
 * Settings (owner's request 2026-10-16): what the player keeps and where - everything is saved on this
 * computer by the player's server, not in the browser - when it last saved, a backup to download, a restore,
 * a fresh start; where *Open in ComfyUI* goes; the folders it reads (several, chosen here, each with or
 * without other music - owner's request 2026-10-16); and stopping a player that runs without a window (one
 * started from ComfyUI).
 */
import { computed, onMounted, ref } from 'vue'

import { api, type ComfyFound, type FoldersAnswer } from '../api'
import { version as pageVersion } from '../../../package.json'
import { allTags, comfyuiAddress, deleteTag, go, info, lastSaved, library, reloadLibrary, remote, renameTag, replaceState, rescan, saveError, say, settings, state } from '../store'
import { countOf } from '../timing'
import FolderBrowser from './FolderBrowser.vue'
import Icon from './Icon.vue'
import LyricsPanel from './LyricsPanel.vue'
import NetworkAccess from './NetworkAccess.vue'
import { isPortable, portable } from '../portable'

const shelf = ref<FoldersAnswer | null>(null)
const browsing = ref(false)
const savingFolders = ref(false)
const folderError = ref('')

async function readFolders(): Promise<void> {
  try {
    shelf.value = await api.folders()
  } catch (error) {
    folderError.value = error instanceof Error ? error.message : String(error)
  }
}
/** Save the folders (``null``: back to the ones the player started with) and read the library again. */
async function saveFolders(list: { path: string; other: boolean }[] | null): Promise<void> {
  savingFolders.value = true
  folderError.value = ''
  try {
    shelf.value = await api.setFolders(list)
    await reloadLibrary()
    say(`${countOf(library.value.length, 'song')} in ${countOf(shelf.value.folders.length, 'folder')}`, 3000)
  } catch (error) {
    folderError.value = error instanceof Error ? error.message : String(error)
  } finally {
    savingFolders.value = false
  }
}
const current = (): { path: string; other: boolean }[] => (shelf.value?.folders ?? []).map((f) => ({ path: f.path, other: f.other }))
function addFolder(path: string): void {
  browsing.value = false
  if (current().some((f) => f.path === path)) return say('That folder is already in the list')
  void saveFolders([...current(), { path, other: false }])
}
function removeFolder(path: string): void {
  void saveFolders(current().filter((f) => f.path !== path))
}
function toggleOther(path: string): void {
  void saveFolders(current().map((f) => (f.path === path ? { ...f, other: !f.other } : f)))
}
onMounted(readFolders)

// the videos made (Save as a video on a song's page)
const videos = ref<{ folder: string; files: { name: string; size: number; mtime: number }[] } | null>(null)
onMounted(async () => {
  videos.value = await api.videos().catch(() => null)
})
const megabytes = (bytes: number): string => `${Math.max(1, Math.round(bytes / 2 ** 20))} MB`
// the players made to share
const shared = ref<{ folder: string; files: { name: string; size: number; mtime: number }[] } | null>(null)
onMounted(async () => {
  shared.value = await api.packages().catch(() => null)
})

// your tags: renamed (into another: the two become one) or taken off every song
const renaming = ref('')
const newName = ref('')
function startRename(tag: string): void {
  renaming.value = tag
  newName.value = tag
}
function finishRename(): void {
  if (renaming.value && newName.value.trim()) {
    renameTag(renaming.value, newName.value)
    say(`#${renaming.value} is #${newName.value.trim()} now`, 2500)
  }
  renaming.value = ''
}
function forgetTag(tag: string, count: number): void {
  if (window.confirm(`Take #${tag} off ${countOf(count, 'song')}?`)) deleteTag(tag)
}
function songsTagged(tag: string): void {
  settings.filters.all = { query: '', chips: [`tag:"${tag}"`] }
  go('/')
}

const found = ref<ComfyFound | null>(null)
const looking = ref(false)
const confirmReset = ref(false)
const stopped = ref(false)
const file = ref<HTMLInputElement | null>(null)

const kept = computed(() => [
  ['Playlists', countOf(state.playlists.length, 'playlist')],
  ['Favourites', countOf(state.favorites.length, 'song')],
  ['Tags', `${countOf(allTags.value.length, 'tag')} on ${countOf(Object.keys(state.tags).length, 'song')}`],
  ['Saved filters', countOf(settings.savedFilters.length, 'filter')],
  ['Play counts', countOf(Object.keys(state.plays).length, 'song')],
  ['Visuals', `${settings.visuals.mode}, ${countOf(settings.visuals.pool.length, 'visual')} ticked, ${countOf(Object.keys(settings.visuals.songs).length, 'song')} with its own`],
  ['Sound', `volume ${Math.round(settings.volume * 100)} %, crossfade ${settings.crossfade} s, speed ${settings.rate}×`],
  ['Library', `sorted by ${settings.sort}, ${settings.view} view, ${countOf(Object.values(settings.filters).filter((f) => f.query.trim() || f.chips.length).length, 'view')} filtered`],
  ['Views', `Now playing opens on ${settings.npView}, a song's page on ${settings.songTab}`],
  ['Where you stopped', settings.resume ? 'the queue and the moment in the song' : '-'],
])
const savedAt = computed(() => (lastSaved.value ? lastSaved.value.toLocaleTimeString() : 'nothing changed since the page opened'))

async function look(): Promise<void> {
  looking.value = true
  try {
    const target = await comfyuiAddress()
    found.value = target ? (await api.comfyui(target)).found : null
  } finally {
    looking.value = false
  }
}
onMounted(look)

function backup(): void {
  const data = JSON.stringify({ ...JSON.parse(JSON.stringify(state)), settings: JSON.parse(JSON.stringify(settings)) }, null, 1)
  const link = document.createElement('a')
  link.href = URL.createObjectURL(new Blob([data], { type: 'application/json' }))
  link.download = `plenio-player-backup-${new Date().toISOString().slice(0, 10)}.json`
  link.click()
  URL.revokeObjectURL(link.href)
}
async function restore(event: Event): Promise<void> {
  const chosen = (event.target as HTMLInputElement).files?.[0]
  if (!chosen) return
  try {
    const data = JSON.parse(await chosen.text())
    if (!data || typeof data !== 'object' || !('playlists' in data || 'settings' in data)) throw new Error('not a Plenio Player backup')
    await replaceState(data)
    say(`Restored: ${countOf(state.playlists.length, 'playlist')}, ${countOf(state.favorites.length, 'favourite')}`, 3000)
  } catch (error) {
    say(`Could not restore ${chosen.name}: ${error instanceof Error ? error.message : String(error)}`, 6000)
  } finally {
    if (file.value) file.value.value = ''
  }
}
async function reset(): Promise<void> {
  confirmReset.value = false
  await replaceState(null)
  say('Started afresh', 2500)
}
async function stop(): Promise<void> {
  await api.quit().catch(() => {})
  stopped.value = true
}
</script>

<template>
  <div class="settings">
    <h1>Settings</h1>
    <!-- which player answers (owner's request 2026-10-17); a page left open across an update says so -->
    <p class="version">
      <Icon name="info" :size="15" />
      <template v-if="isPortable"><b>Shared with the Plenio Player {{ portable?.plenio }}</b></template>
      <template v-else><b>Plenio Player {{ info?.version ?? '…' }}</b> is running<template v-if="remote"> - on the computer you came from by the network</template></template>
      <span v-if="!isPortable && info && info.version !== pageVersion" class="stale">· this page is {{ pageVersion }} - reload it (Ctrl+F5)</span>
    </p>

    <div v-if="stopped" class="block stopped">
      <h3>The player has stopped</h3>
      <p>Start it again with the <b>Plenio Player</b> button in ComfyUI, with <code>Plenio Player.bat</code> in the Plenio folder, or with <code>python plenio_player.py</code>.</p>
    </div>

    <section v-if="isPortable" class="block">
      <h3><Icon name="music" /> This shared player</h3>
      <p class="lead">“{{ portable?.title }}” - {{ countOf(library.length, 'song') }}, shared {{ portable?.created.slice(0, 10) }} with the Plenio Player {{ portable?.plenio }}. It plays by itself in this browser, without installing anything; your playlists, favourites and settings are kept in this browser.</p>
      <p class="hint">Making songs, opening them in ComfyUI, Live Play's new songs from ComfyUI and saving videos are the Plenio Player's: <a href="https://github.com/jplenio/Plenio-Music-Production-System" target="_blank" rel="noopener">Plenio</a>.</p>
    </section>

    <section class="block">
      <h3><Icon name="check" /> {{ isPortable ? 'Kept in this browser' : 'Kept on this computer' }}</h3>
      <p class="lead">
        Everything you set here - and everything below - is saved by the player itself, half a second after each change and when the page closes. It stays when you
        close the browser, restart the computer, start the player from ComfyUI or by hand, or open it in another browser.
      </p>
      <dl>
        <template v-for="[k, v] in kept" :key="k"><dt>{{ k }}</dt><dd>{{ v }}</dd></template>
      </dl>
      <p class="where">
        <Icon name="folder" :size="14" /> <code>{{ info?.state ?? '~/.plenio/player/state.json' }}</code>
      </p>
      <p class="saved" :class="{ bad: saveError }">{{ saveError ? `Not saved: ${saveError}` : `Last saved: ${savedAt}` }}</p>
      <div class="row">
        <button class="ghost" @click="backup"><Icon name="download" :size="16" /> Download a backup</button>
        <label class="ghost">
          <Icon name="refresh" :size="16" /> Restore a backup…
          <input ref="file" type="file" accept="application/json,.json" hidden @change="restore" />
        </label>
        <button v-if="!confirmReset" class="ghost" @click="confirmReset = true"><Icon name="trash" :size="16" /> Start afresh…</button>
        <button v-else class="ghost danger" @click="reset">Yes - forget playlists, favourites, plays and settings</button>
      </div>
      <p class="hint">The songs themselves are not in the backup: they stay in their folders.</p>
    </section>

    <NetworkAccess v-if="!isPortable" />

    <section v-if="!isPortable && !remote" class="block">
      <h3><Icon name="external" /> ComfyUI</h3>
      <p class="lead">A song's page opens the song's workflow in ComfyUI, with its lyrics, score and settings, to work on it - and ComfyUI itself opens here, in the browser, when it runs.</p>
      <p class="status" :class="{ ok: found }">
        {{ looking ? 'Looking for ComfyUI …' : found ? `ComfyUI ${found.version} at ${found.url}` : 'ComfyUI is not running on this computer (or not at the address below).' }}
      </p>
      <label class="field">
        Address <input v-model.lazy="settings.comfyui" :placeholder="info?.comfyui || 'found by itself (127.0.0.1:8188, 127.0.0.1:8000)'" @change="look" />
      </label>
      <div class="row-buttons">
        <a v-if="found" class="ghost small" :href="found.url" target="_blank" rel="noopener"><Icon name="external" :size="14" /> Open ComfyUI</a>
        <button class="ghost small" :disabled="looking" @click="look"><Icon name="refresh" :size="14" /> Look again</button>
      </div>
    </section>

    <section v-if="!isPortable" class="block">
      <h3><Icon name="folder" /> Songs</h3>
      <p class="lead">The player reads every release record (<code>.plenio.json</code>) below these folders: {{ countOf(library.length, 'song') }}.</p>
      <p v-if="remote" class="hint">The folders are chosen on the computer the player runs on.</p>
      <ul class="shelf">
        <li v-for="f in shelf?.folders ?? []" :key="f.path" :class="{ missing: !f.exists }">
          <div class="where">
            <code>{{ f.path }}</code>
            <small>{{ f.exists ? countOf(f.songs, 'Plenio song') : 'not there (a drive not connected?)' }}<template v-if="f.other">, {{ countOf(f.other_songs, 'other song') }}</template></small>
          </div>
          <label class="other" title="Also play audio files in this folder that were not made with Plenio (FLAC, MP3, WAV, OGG, Opus, M4A). They are marked as other music and have what their files have.">
            <input type="checkbox" :checked="f.other" :disabled="savingFolders || remote" @change="toggleOther(f.path)" /> also other music
          </label>
          <button v-if="!remote" class="icon-btn" title="Do not read this folder any more (its files stay)" :disabled="savingFolders || (shelf?.folders.length ?? 0) < 2" @click="removeFolder(f.path)"><Icon name="close" :size="14" /></button>
        </li>
      </ul>
      <p v-if="folderError" class="error">{{ folderError }}</p>
      <div class="row-buttons">
        <button v-if="!remote" class="ghost small" :disabled="savingFolders" @click="browsing = true"><Icon name="plus" :size="14" /> Add a folder…</button>
        <button class="ghost small" @click="rescan().then(readFolders).then(() => say('Library read again'))"><Icon name="refresh" :size="14" /> Look for new songs</button>
        <button v-if="shelf?.chosen && !remote" class="ghost small" :disabled="savingFolders" :title="`Back to ${shelf.started_with.join(', ')}`" @click="saveFolders(null)">Back to the start's folders</button>
      </div>
      <p class="hint">
        Songs made with Plenio come first; <b>also other music</b> plays the other audio files of a folder too, marked as <i>other music</i> - with their tags, cover and lyrics, without notation or <i>Open in ComfyUI</i>.
        The folders are kept with the player (<code>library.json</code>), also when ComfyUI starts it. Removed songs go to <code>{{ info?.retired ?? '_retired' }}</code> in their folder, which the player does not read.
      </p>
      <FolderBrowser v-if="browsing" @choose="addFolder" @close="browsing = false" />
    </section>

    <section class="block">
      <h3><Icon name="tag" /> Tags</h3>
      <p class="lead">Tags of your own: give them on a song's page, in a song's ⋯ menu, or to every song a filter shows (<b>Tag…</b> on the songs' page); find them with <code>#tag</code> or the filter row <i>Tags</i>. {{ allTags.length ? '' : 'None yet.' }}</p>
      <ul v-if="allTags.length" class="tag-list">
        <li v-for="[tag, count] in allTags" :key="tag">
          <form v-if="renaming === tag" @submit.prevent="finishRename">
            <input v-model="newName" maxlength="40" @keydown.esc="renaming = ''" @blur="finishRename" />
          </form>
          <button v-else class="name" title="The songs with this tag" @click="songsTagged(tag)">#{{ tag }} <small>{{ count }}</small></button>
          <button class="icon-btn" title="Rename (into another tag: the two become one)" @click="startRename(tag)"><Icon name="edit" :size="14" /></button>
          <button class="icon-btn" title="Take it off every song" @click="forgetTag(tag, count)"><Icon name="trash" :size="14" /></button>
        </li>
      </ul>
    </section>

    <section class="block">
      <h3><Icon name="mic" /> Lyrics</h3>
      <p class="lead">How the lyrics look while a song plays: the font, the size, the colour - and how each syllable comes in as it is sung.</p>
      <LyricsPanel />
    </section>

    <section v-if="!isPortable" class="block">
      <h3><Icon name="download" /> Shared players</h3>
      <p class="lead">Songs to give away: one HTML file with the player and the songs, which plays by itself - <b>Share…</b> in a view or a playlist, or <b>Share as a player…</b> at the bottom of the sidebar. {{ shared?.files.length ? countOf(shared.files.length, 'player') + ' so far:' : 'None yet.' }}</p>
      <ul v-if="shared?.files.length" class="videos">
        <li v-for="f in shared.files.slice(0, 12)" :key="f.name">
          <span>{{ f.name }} <small>{{ megabytes(f.size) }} · {{ new Date(f.mtime * 1000).toLocaleString() }}</small></span>
          <a class="icon-btn" :href="`/packages/${encodeURIComponent(f.name)}`" target="_blank" rel="noopener" title="Try it"><Icon name="play" :size="16" /></a>
          <a class="icon-btn" :href="`/packages/${encodeURIComponent(f.name)}?download=1`" :download="f.name" title="Download"><Icon name="download" :size="16" /></a>
        </li>
      </ul>
      <button v-if="!remote" class="ghost small" @click="api.openPackages().catch((e) => say(e.message, 5000))"><Icon name="folder" :size="14" /> Open the folder</button>
    </section>

    <section v-if="!isPortable" class="block">
      <h3><Icon name="layers" /> Videos</h3>
      <p class="lead">A song as an MP4 video - its visual, lyrics and notation: <b>Video…</b> on a song's page. {{ videos?.files.length ? countOf(videos.files.length, 'video') + ' so far:' : 'None yet.' }}</p>
      <ul v-if="videos?.files.length" class="videos">
        <li v-for="v in videos.files.slice(0, 12)" :key="v.name">
          <span>{{ v.name }} <small>{{ megabytes(v.size) }} · {{ new Date(v.mtime * 1000).toLocaleString() }}</small></span>
          <a class="icon-btn" :href="`/videos/${encodeURIComponent(v.name)}`" target="_blank" rel="noopener" title="Watch"><Icon name="play" :size="16" /></a>
          <a class="icon-btn" :href="`/videos/${encodeURIComponent(v.name)}?download=1`" :download="v.name" title="Download"><Icon name="download" :size="16" /></a>
        </li>
      </ul>
      <button v-if="!remote" class="ghost small" @click="api.openVideos().catch((e) => say(e.message, 5000))"><Icon name="folder" :size="14" /> Open the videos folder</button>
      <p v-if="videos" class="hint"><code>{{ videos.folder }}</code></p>
    </section>

    <section v-if="!isPortable && !remote" class="block">
      <h3><Icon name="info" /> The player</h3>
      <p class="lead">Plenio Player {{ info?.version }} - a program of its own, which runs without ComfyUI. Started from ComfyUI it has no window: stop it here.</p>
      <button class="ghost danger" @click="stop">Stop the player</button>
    </section>
  </div>
</template>

<style scoped>
.version {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin: -6px 0 18px;
  color: var(--muted);
  font-size: 14px;
}
.version b {
  color: #fff;
}
.version .stale {
  color: #ffb86b;
}
.settings {
  padding: 26px 34px 40px;
  max-width: 980px;
}
h1 {
  font: 800 34px var(--font);
  margin: 6px 0 18px;
}
.block {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 18px 20px;
  margin-bottom: 16px;
}
.block h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 8px;
  font: 700 16px var(--font);
}
.lead {
  margin: 0 0 12px;
  color: rgba(255, 255, 255, 0.75);
  line-height: 1.5;
}
dl {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 5px 18px;
  margin: 0 0 12px;
  font-size: 13px;
}
dt {
  color: var(--muted);
}
dd {
  margin: 0;
}
code {
  font: 12px var(--mono);
  word-break: break-all;
}
.where,
.saved {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 6px 0;
  font-size: 12px;
  color: var(--muted);
}
.saved {
  color: #7fe0a0;
}
.saved.bad {
  color: #ff8f8f;
}
.row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}
.row label {
  cursor: pointer;
}
.small {
  height: 32px;
  font-size: 12px;
}
.danger {
  color: #ff8f8f;
  border-color: rgba(255, 120, 120, 0.5);
}
.hint {
  color: var(--muted);
  font-size: 12px;
  margin: 10px 0;
}
.status {
  font-size: 13px;
  color: #ffb36b;
}
.status.ok {
  color: #7fe0a0;
}
.field {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 8px 0;
  font-size: 13px;
  color: var(--muted);
}
.field input {
  flex: 1;
  max-width: 420px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 8px;
  color: #fff;
  padding: 7px 10px;
  font: 13px var(--mono);
}
.shelf {
  list-style: none;
  margin: 0 0 10px;
  padding: 0;
  display: grid;
  gap: 6px;
}
.shelf li {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 10px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.shelf li.missing {
  border-color: rgba(255, 150, 90, 0.4);
}
.shelf .where {
  flex: 1;
  min-width: 0;
  display: grid;
}
.shelf code {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.shelf small {
  color: var(--muted);
}
.shelf .other {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
}
.videos {
  list-style: none;
  margin: 0 0 10px;
  padding: 0;
  display: grid;
  gap: 4px;
}
.videos li {
  display: flex;
  align-items: center;
  gap: 8px;
}
.videos span {
  flex: 1;
  min-width: 0;
}
.videos small {
  color: var(--muted);
  margin-left: 6px;
}
.row-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tag-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
}
.tag-list li {
  display: flex;
  align-items: center;
  gap: 2px;
}
.tag-list .name {
  border: 0;
  background: none;
  color: #fff;
  cursor: pointer;
  font: 600 13px var(--font);
}
.tag-list .name small {
  color: var(--muted);
  font-weight: 400;
}
.tag-list .icon-btn {
  width: 26px;
  height: 26px;
}
.tag-list input {
  width: 160px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid var(--accent);
  border-radius: 8px;
  color: #fff;
  padding: 4px 8px;
  font: 13px var(--font);
}
.error {
  color: #ff9a9a;
}
.stopped {
  border-color: #ffb36b;
}
</style>
