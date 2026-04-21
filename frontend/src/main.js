import { createApp } from 'vue'
import { Quasar } from 'quasar'
import '@quasar/extras/roboto-font/roboto-font.css'
import '@quasar/extras/material-icons/material-icons.css'
import 'quasar/src/css/index.sass'
import App from './App.vue'

const app = createApp(App)
app.use(Quasar, { plugins: {} })
app.mount('#app')
