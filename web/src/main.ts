import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './style.css'

import NoteList from './pages/NoteList.vue'
import NoteDetail from './pages/NoteDetail.vue'
import SearchPage from './pages/SearchPage.vue'

const routes = [
  { path: '/', component: NoteList },
  { path: '/note/:fileId', component: NoteDetail, props: true },
  { path: '/search', component: SearchPage },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

createApp(App).use(router).mount('#app')
