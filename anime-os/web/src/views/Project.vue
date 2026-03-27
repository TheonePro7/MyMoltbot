<template>
  <div class="max-w-4xl mx-auto px-6 py-10">
    <router-link to="/" class="text-xs text-cyan-500 hover:text-cyan-400 mb-6 inline-block">← 返回列表</router-link>

    <div v-if="loading" class="text-slate-400 text-sm">加载中…</div>
    <p v-else-if="loadErr" class="text-red-400 text-sm">{{ loadErr }}</p>

    <template v-else-if="project">
      <div class="mb-8">
        <h1 class="text-2xl font-semibold text-white">{{ project.title }}</h1>
        <label class="block mt-4 text-xs text-slate-500 uppercase tracking-wide">创意 / 需求（自然语言）</label>
        <textarea
          v-model="ideaDraft"
          rows="4"
          class="mt-1 w-full rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500"
          placeholder="写清风格、时长、受众等，供 OpenClaw 与各步骤 Agent 使用"
        />
        <div class="flex flex-wrap gap-2 mt-3">
          <button
            type="button"
            class="rounded-lg bg-slate-700 hover:bg-slate-600 text-sm px-4 py-2"
            :disabled="saving"
            @click="saveIdea"
          >
            保存创意
          </button>
          <span v-if="saveMsg" class="text-xs text-emerald-400 self-center">{{ saveMsg }}</span>
        </div>
      </div>

      <h2 class="text-lg font-medium text-slate-200 mb-3">流水线步骤</h2>
      <p class="text-slate-500 text-sm mb-4">
        锁定后的步骤，Agent 生成时应视为只读事实源（由 API 的 <code class="text-cyan-600">locked_step_keys</code> 记录）。
      </p>

      <ul class="space-y-2">
        <li
          v-for="s in stepRows"
          :key="s.step_key"
          class="rounded-lg border border-slate-800 bg-slate-900/40 px-4 py-3 flex flex-wrap items-center gap-3"
        >
          <span class="font-medium text-slate-200 w-28">{{ labelFor(s.step_key) }}</span>
          <span
            class="text-xs px-2 py-0.5 rounded"
            :class="statusClass(s.status)"
          >{{ s.status }}</span>
          <label class="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
            <input v-model="lockSel[s.step_key]" type="checkbox" class="rounded border-slate-600" />
            锁定
          </label>
          <button
            type="button"
            class="ml-auto text-xs text-cyan-500 hover:text-cyan-400"
            @click="toggleExpand(s.step_key)"
          >
            {{ expanded[s.step_key] ? "收起" : "查看/编辑 JSON" }}
          </button>
        </li>
      </ul>

      <div class="mt-6 flex flex-wrap gap-2">
        <button
          type="button"
          class="rounded-lg bg-cyan-700 hover:bg-cyan-600 text-sm px-4 py-2"
          :disabled="locking"
          @click="saveLocks"
        >
          保存锁定状态
        </button>
        <span v-if="lockMsg" class="text-xs text-emerald-400 self-center">{{ lockMsg }}</span>
      </div>

      <div v-if="activeStepKey" class="mt-8 rounded-xl border border-slate-800 bg-slate-900/60 p-4">
        <h3 class="text-sm font-medium text-slate-300 mb-2">{{ labelFor(activeStepKey) }} · 产物 JSON</h3>
        <textarea
          v-model="artifactDrafts[activeStepKey]"
          rows="14"
          class="w-full font-mono text-xs rounded-lg bg-slate-950 border border-slate-700 px-3 py-2 text-cyan-100/90"
        />
        <div class="flex gap-2 mt-3">
          <button
            type="button"
            class="rounded-lg bg-emerald-700 hover:bg-emerald-600 text-sm px-4 py-2"
            :disabled="stepSaving"
            @click="saveArtifact(activeStepKey)"
          >
            保存本步产物
          </button>
          <span v-if="stepSaveMsg" class="text-xs text-emerald-400 self-center">{{ stepSaveMsg }}</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue";
import { apiGet, apiSend } from "../api.js";

const props = defineProps({ id: { type: String, required: true } });

const loading = ref(true);
const loadErr = ref("");
const project = ref(null);
const steps = ref([]);
const pipeline = ref([]);

const ideaDraft = ref("");
const saving = ref(false);
const saveMsg = ref("");

const lockSel = reactive({});
const lockedKeys = ref([]);
const locking = ref(false);
const lockMsg = ref("");

const expanded = reactive({});
const artifactDrafts = reactive({});
const stepSaving = ref(false);
const stepSaveMsg = ref("");

const stepRows = computed(() => {
  const order = pipeline.value.map((s) => s.key);
  const list = [...steps.value];
  list.sort((a, b) => order.indexOf(a.step_key) - order.indexOf(b.step_key));
  return list;
});

const activeStepKey = computed(() => {
  const k = Object.keys(expanded).find((key) => expanded[key]);
  return k || null;
});

function labelFor(key) {
  const p = pipeline.value.find((x) => x.key === key);
  return p?.label || key;
}

function statusClass(st) {
  if (st === "done") return "bg-emerald-900/50 text-emerald-300";
  if (st === "error") return "bg-red-900/40 text-red-300";
  if (st === "running") return "bg-amber-900/40 text-amber-200";
  return "bg-slate-800 text-slate-400";
}

function syncLocksFromProject() {
  lockedKeys.value = JSON.parse(project.value?.locked_step_keys || "[]");
  const keys =
    pipeline.value.length > 0
      ? pipeline.value.map((p) => p.key)
      : steps.value.map((s) => s.step_key);
  for (const k of keys) {
    lockSel[k] = lockedKeys.value.includes(k);
  }
}

function syncArtifactsFromSteps() {
  for (const s of steps.value) {
    if (s.artifact_json) {
      try {
        const o = JSON.parse(s.artifact_json);
        artifactDrafts[s.step_key] = JSON.stringify(o, null, 2);
      } catch {
        artifactDrafts[s.step_key] = String(s.artifact_json);
      }
    } else {
      artifactDrafts[s.step_key] = "{\n  \n}";
    }
  }
}

async function load() {
  loading.value = true;
  loadErr.value = "";
  try {
    const meta = await apiGet("/v1/pipeline");
    pipeline.value = meta.steps || [];
    const data = await apiGet(`/v1/projects/${props.id}`);
    project.value = data.project;
    steps.value = data.steps || [];
    ideaDraft.value = data.project.idea || "";
    syncLocksFromProject();
    syncArtifactsFromSteps();
  } catch (e) {
    loadErr.value = e.message || String(e);
  } finally {
    loading.value = false;
  }
}

async function saveIdea() {
  saving.value = true;
  saveMsg.value = "";
  try {
    await apiSend("PATCH", `/v1/projects/${props.id}`, { idea: ideaDraft.value });
    saveMsg.value = "已保存";
    setTimeout(() => (saveMsg.value = ""), 2000);
  } catch (e) {
    saveMsg.value = e.message || String(e);
  } finally {
    saving.value = false;
  }
}

async function saveLocks() {
  locking.value = true;
  lockMsg.value = "";
  const keys = Object.keys(lockSel).filter((k) => lockSel[k]);
  try {
    await apiSend("POST", `/v1/projects/${props.id}/locks`, { step_keys: keys });
    lockMsg.value = "锁定已更新";
    await load();
    setTimeout(() => (lockMsg.value = ""), 2000);
  } catch (e) {
    lockMsg.value = e.message || String(e);
  } finally {
    locking.value = false;
  }
}

function toggleExpand(key) {
  const next = !expanded[key];
  Object.keys(expanded).forEach((k) => {
    expanded[k] = false;
  });
  expanded[key] = next;
}

async function saveArtifact(stepKey) {
  stepSaving.value = true;
  stepSaveMsg.value = "";
  let artifact;
  try {
    artifact = JSON.parse(artifactDrafts[stepKey] || "{}");
  } catch (e) {
    stepSaveMsg.value = "JSON 格式错误：" + (e.message || e);
    stepSaving.value = false;
    return;
  }
  try {
    await apiSend("PUT", `/v1/projects/${props.id}/steps/${stepKey}`, {
      status: "done",
      artifact,
    });
    stepSaveMsg.value = "已保存";
    await load();
    setTimeout(() => (stepSaveMsg.value = ""), 2000);
  } catch (e) {
    stepSaveMsg.value = e.message || String(e);
  } finally {
    stepSaving.value = false;
  }
}

watch(
  () => props.id,
  () => load(),
  { immediate: true }
);
</script>
