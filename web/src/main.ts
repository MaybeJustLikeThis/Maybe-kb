import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './style.css'
import './assets/base.css'

const routes = [
  { path: '/', component: () => import('./pages/OverviewPage.vue') },
  { path: '/source/:name', component: () => import('./pages/SourcePage.vue'), props: true },
  { path: '/source/:name/:fileId', component: () => import('./pages/NoteDetail.vue'), props: true },
  { path: '/note/:fileId', component: () => import('./pages/NoteDetail.vue'), props: true },
  { path: '/manage', component: () => import('./pages/ManagePage.vue') },
  { path: '/search', component: () => import('./pages/SearchPage.vue') },
  { path: '/chat', component: () => import('./pages/ChatPage.vue') },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

createApp(App).use(router).mount('#app')
