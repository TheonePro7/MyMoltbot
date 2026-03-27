<template>
  <div class="min-h-screen flex flex-col">
    <header
      class="border-b border-slate-800 bg-slate-900/80 backdrop-blur px-6 py-4 flex items-center justify-between"
    >
      <router-link to="/" class="text-lg font-semibold tracking-tight text-cyan-400 hover:text-cyan-300">
        Anime OS
      </router-link>
      <span class="text-xs text-slate-500">漫剧流水线 · 单一控制台</span>
    </header>
    <main class="flex-1">
      <router-view />
    </main>
  </div>
</template>

<script setup></script>
