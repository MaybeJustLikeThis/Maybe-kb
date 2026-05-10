import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import './assets/base.css'

import NoteList from './pages/NoteList.vue'
import NoteDetail from './pages/NoteDetail.vue'
import SearchPage from './pages/SearchPage.vue'
import ChatPage from './pages/ChatPage.vue'
import DashboardPage from './pages/DashboardPage.vue'

const routes = [
  { path: '/', component: DashboardPage },
  { path: '/notes', component: NoteList },
  { path: '/note/:fileId', component: NoteDetail, props: true },
  { path: '/search', component: SearchPage },
  { path: '/chat', component: ChatPage },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

createApp(App).use(router).mount('#app')
