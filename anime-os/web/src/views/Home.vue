<template>
  <div class="max-w-3xl mx-auto px-6 py-10">
    <h1 class="text-2xl font-semibold text-white mb-2">项目列表</h1>
    <p class="text-slate-400 text-sm mb-8">
      所有漫剧项目只在此维护；OpenClaw / N8N 通过同一套 API 读写步骤产物。
    </p>

    <form
      class="flex flex-col sm:flex-row gap-3 mb-10 p-4 rounded-xl border border-slate-800 bg-slate-900/50"
      @submit.prevent="create"
    >
      <input
        v-model="title"
        type="text"
        placeholder="项目标题"
        class="flex-1 rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500"
      />
      <button
        type="submit"
        class="rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-sm font-medium px-4 py-2 disabled:opacity-50"
        :disabled="loading"
      >
        新建项目
      </button>
    </form>

    <p v-if="err" class="text-red-400 text-sm mb-4">{{ err }}</p>

    <ul v-if="projects.length" class="space-y-2">
      <li v-for="p in projects" :key="p.id">
        <router-link
          :to="{ name: 'project', params: { id: p.id } }"
          class="block rounded-lg border border-slate-800 bg-slate-900/40 hover:border-cyan-900/80 px-4 py-3 transition"
        >
          <div class="font-medium text-slate-100">{{ p.title }}</div>
          <div class="text-xs text-slate-500 mt-1 truncate">{{ p.idea || "（暂无创意描述）" }}</div>
        </router-link>
      </li>
    </ul>
    <p v-else class="text-slate-500 text-sm">暂无项目，请先新建。</p>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { apiGet, apiSend } from "../api.js";

const projects = ref([]);
const title = ref("");
const loading = ref(false);
const err = ref("");

async function load() {
  err.value = "";
  const data = await apiGet("/v1/projects");
  projects.value = data.projects || [];
}

async function create() {
  loading.value = true;
  err.value = "";
  try {
    await apiSend("POST", "/v1/projects", {
      title: title.value || "未命名项目",
      idea: "",
    });
    title.value = "";
    await load();
  } catch (e) {
    err.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>
