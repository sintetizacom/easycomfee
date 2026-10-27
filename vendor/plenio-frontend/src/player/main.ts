/** The Plenio Player's page (built into plenio/player/static, served by ``python -m plenio.player``). */
import { createApp } from 'vue'

import App from './App.vue'
import { load } from './store'
import './styles.css'

createApp(App).mount('#app')
void load()
