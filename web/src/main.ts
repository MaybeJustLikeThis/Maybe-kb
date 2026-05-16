import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import './assets/base.css'

import OverviewPage from './pages/OverviewPage.vue'
import SourcePage from './pages/SourcePage.vue'
import NoteDetail from './pages/NoteDetail.vue'
import SearchPage from './pages/SearchPage.vue'
import ChatPage from './pages/ChatPage.vue'
import ManagePage from './pages/ManagePage.vue'

const routes = [
  { path: '/', component: OverviewPage },
  { path: '/source/:name', component: SourcePage, props: true },
  { path: '/source/:name/:fileId', component: NoteDetail, props: true },
  { path: '/note/:fileId', component: NoteDetail, props: true },
  { path: '/manage', component: ManagePage },
  { path: '/search', component: SearchPage },
  { path: '/chat', component: ChatPage },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

createApp(App).use(router).mount('#app')
