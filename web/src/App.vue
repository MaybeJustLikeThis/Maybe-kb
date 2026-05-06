<template>
  <div class="min-h-screen flex">
    <div class="w-64 bg-gray-800 text-white p-4 flex-shrink-0">
      <h1 class="text-xl font-bold mb-6">
        <router-link to="/" class="hover:text-blue-300">KB</router-link>
      </h1>
      <nav class="space-y-2">
        <router-link to="/" class="block py-2 px-3 rounded hover:bg-gray-700">Notes</router-link>
        <router-link to="/search" class="block py-2 px-3 rounded hover:bg-gray-700">Search</router-link>
        <router-link to="/chat" class="block py-2 px-3 rounded hover:bg-gray-700">Chat</router-link>
      </nav>
    </div>
    <main class="flex-1 p-6">
      <router-view />
    </main>
  </div>
</template>
