import "dotenv/config";
import express from "express";
import cors from "cors";
import path from "path";
import { fileURLToPath } from "url";
import { nanoid } from "nanoid";
import { openDb, PIPELINE_STEPS, seedStepsForProject } from "./db.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, "..", "data");
const DB_PATH = process.env.SQLITE_PATH || path.join(DATA_DIR, "anime-os.db");
const PORT = Number(process.env.PORT || 8787);
/** 可选：设置后所有变更类接口需带 X-Service-Token（与 OpenClaw/N8N、Vite 代理共用同一值） */
const SERVICE_TOKEN = process.env.SERVICE_TOKEN || "";

const db = openDb(DB_PATH);
const app = express();
app.use(cors({ origin: true }));
app.use(express.json({ limit: "2mb" }));

function requireServiceToken(req, res, next) {
  if (!SERVICE_TOKEN) return next();
  const h = req.headers["x-service-token"];
  if (h !== SERVICE_TOKEN) {
    return res.status(401).json({ error: "未授权：缺少或错误的 X-Service-Token" });
  }
  next();
}

function parseJsonArray(s, fallback = []) {
  try {
    const v = JSON.parse(s || "[]");
    return Array.isArray(v) ? v : fallback;
  } catch {
    return fallback;
  }
}

/** 健康检查 */
app.get("/health", (_req, res) => {
  res.json({ ok: true, service: "anime-os-api", steps: PIPELINE_STEPS.map((s) => s.key) });
});

/** 流水线步骤定义（供前端 / Agent 对齐） */
app.get("/v1/pipeline", (_req, res) => {
  res.json({ steps: PIPELINE_STEPS });
});

/** 创建项目 */
app.post("/v1/projects", requireServiceToken, (req, res) => {
  const title = String(req.body?.title || "").trim() || "未命名项目";
  const idea = String(req.body?.idea || "").trim();
  const id = nanoid();
  const now = new Date().toISOString();
  db.prepare(
    `INSERT INTO projects (id, title, idea, status, current_step_key, locked_step_keys, created_at, updated_at)
     VALUES (?, ?, ?, 'draft', 'outline', ?, ?, ?)`
  ).run(id, title, idea, "[]", now, now);
  seedStepsForProject(db, id);
  const row = db.prepare("SELECT * FROM projects WHERE id = ?").get(id);
  res.status(201).json({ project: row });
});

/** 项目列表 */
app.get("/v1/projects", (_req, res) => {
  const rows = db.prepare("SELECT * FROM projects ORDER BY updated_at DESC").all();
  res.json({ projects: rows });
});

/** 单项目 + 各步骤状态 */
app.get("/v1/projects/:id", (req, res) => {
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(req.params.id);
  if (!project) return res.status(404).json({ error: "项目不存在" });
  const steps = db
    .prepare("SELECT * FROM steps WHERE project_id = ? ORDER BY step_key")
    .all(req.params.id);
  res.json({ project, steps });
});

/** 更新项目元信息（标题、创意、当前步骤） */
app.patch("/v1/projects/:id", requireServiceToken, (req, res) => {
  const id = req.params.id;
  const existing = db.prepare("SELECT * FROM projects WHERE id = ?").get(id);
  if (!existing) return res.status(404).json({ error: "项目不存在" });
  const title =
    req.body?.title !== undefined ? String(req.body.title).trim() : existing.title;
  const idea = req.body?.idea !== undefined ? String(req.body.idea) : existing.idea;
  const current_step_key =
    req.body?.current_step_key !== undefined
      ? String(req.body.current_step_key)
      : existing.current_step_key;
  const now = new Date().toISOString();
  db.prepare(
    `UPDATE projects SET title = ?, idea = ?, current_step_key = ?, updated_at = ? WHERE id = ?`
  ).run(title, idea, current_step_key, now, id);
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(id);
  res.json({ project });
});

/** 锁定某些步骤（后续生成应只读这些结果） */
app.post("/v1/projects/:id/locks", requireServiceToken, (req, res) => {
  const id = req.params.id;
  const existing = db.prepare("SELECT * FROM projects WHERE id = ?").get(id);
  if (!existing) return res.status(404).json({ error: "项目不存在" });
  const keys = req.body?.step_keys;
  if (!Array.isArray(keys)) {
    return res.status(400).json({ error: "body.step_keys 须为字符串数组" });
  }
  const now = new Date().toISOString();
  db.prepare(`UPDATE projects SET locked_step_keys = ?, updated_at = ? WHERE id = ?`).run(
    JSON.stringify(keys),
    now,
    id
  );
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(id);
  res.json({ project, locked_step_keys: parseJsonArray(project.locked_step_keys) });
});

/**
 * 写入某一步产物（OpenClaw / N8N / 人工均可调用）
 * body: { status?, artifact?, error_message? }
 */
app.put("/v1/projects/:id/steps/:stepKey", requireServiceToken, (req, res) => {
  const { id, stepKey } = req.params;
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(id);
  if (!project) return res.status(404).json({ error: "项目不存在" });
  const validKeys = new Set(PIPELINE_STEPS.map((s) => s.key));
  if (!validKeys.has(stepKey)) {
    return res.status(400).json({ error: `未知步骤: ${stepKey}` });
  }
  const stepRow = db
    .prepare("SELECT * FROM steps WHERE project_id = ? AND step_key = ?")
    .get(id, stepKey);
  if (!stepRow) return res.status(404).json({ error: "步骤行不存在" });

  const status = req.body?.status
    ? String(req.body.status)
    : stepRow.status || "pending";
  const artifact =
    req.body?.artifact !== undefined
      ? JSON.stringify(req.body.artifact)
      : stepRow.artifact_json;
  const error_message =
    req.body?.error_message !== undefined
      ? String(req.body.error_message || "")
      : stepRow.error_message;
  const now = new Date().toISOString();

  db.prepare(
    `UPDATE steps SET status = ?, artifact_json = ?, error_message = ?, updated_at = ? WHERE id = ?`
  ).run(status, artifact, error_message, now, stepRow.id);
  db.prepare(`UPDATE projects SET updated_at = ? WHERE id = ?`).run(now, id);

  const step = db.prepare("SELECT * FROM steps WHERE id = ?").get(stepRow.id);
  res.json({ step });
});

/** 供 OpenClaw 拉取上下文（含已锁定步骤摘要） */
app.get("/v1/projects/:id/context", (req, res) => {
  const project = db.prepare("SELECT * FROM projects WHERE id = ?").get(req.params.id);
  if (!project) return res.status(404).json({ error: "项目不存在" });
  const steps = db.prepare("SELECT * FROM steps WHERE project_id = ?").all(req.params.id);
  const locked = parseJsonArray(project.locked_step_keys);
  const byKey = Object.fromEntries(steps.map((s) => [s.step_key, s]));
  const lockedArtifacts = {};
  for (const k of locked) {
    const row = byKey[k];
    if (row?.artifact_json) {
      try {
        lockedArtifacts[k] = JSON.parse(row.artifact_json);
      } catch {
        lockedArtifacts[k] = row.artifact_json;
      }
    }
  }
  res.json({
    project: {
      id: project.id,
      title: project.title,
      idea: project.idea,
      current_step_key: project.current_step_key,
      locked_step_keys: locked,
    },
    steps: steps.map((s) => ({
      step_key: s.step_key,
      status: s.status,
      error_message: s.error_message,
      has_artifact: Boolean(s.artifact_json),
    })),
    locked_artifacts: lockedArtifacts,
  });
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`anime-os-api listening on :${PORT}, db=${DB_PATH}`);
});
