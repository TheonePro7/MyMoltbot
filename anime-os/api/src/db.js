import Database from "better-sqlite3";
import path from "path";
import fs from "fs";
import { nanoid } from "nanoid";

/** 流水线步骤顺序（与业务约定一致，勿随意改 key） */
export const PIPELINE_STEPS = [
  { key: "outline", label: "大纲", order: 0 },
  { key: "script", label: "剧本", order: 1 },
  { key: "storyboard", label: "分镜脚本", order: 2 },
  { key: "char_sheet", label: "角色设定", order: 3 },
  { key: "keyframes", label: "关键帧", order: 4 },
  { key: "video", label: "视频片段", order: 5 },
  { key: "assemble", label: "成片合成", order: 6 },
];

export function openDb(filePath) {
  const dir = path.dirname(filePath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const db = new Database(filePath);
  db.pragma("journal_mode = WAL");
  db.exec(`
    CREATE TABLE IF NOT EXISTS projects (
      id TEXT PRIMARY KEY,
      title TEXT NOT NULL,
      idea TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'draft',
      current_step_key TEXT,
      locked_step_keys TEXT NOT NULL DEFAULT '[]',
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS steps (
      id TEXT PRIMARY KEY,
      project_id TEXT NOT NULL,
      step_key TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'pending',
      artifact_json TEXT,
      error_message TEXT,
      updated_at TEXT NOT NULL,
      UNIQUE(project_id, step_key),
      FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    CREATE INDEX IF NOT EXISTS idx_steps_project ON steps(project_id);
  `);
  return db;
}

/** 为新项目初始化各步骤行（幂等） */
export function seedStepsForProject(db, projectId) {
  const insert = db.prepare(
    `INSERT OR IGNORE INTO steps (id, project_id, step_key, status, updated_at)
     VALUES (?, ?, ?, 'pending', ?)`
  );
  const now = new Date().toISOString();
  for (const s of PIPELINE_STEPS) {
    insert.run(nanoid(), projectId, s.key, now);
  }
}
