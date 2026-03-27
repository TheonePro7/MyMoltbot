/**
 * 统一走同源 /api；开发时由 Vite 代理并注入 X-Service-Token，生产由 Nginx 注入（勿把 Token 写进前端打包）。
 */
const base = "/api";

export async function apiGet(path) {
  const r = await fetch(`${base}${path}`);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

export async function apiSend(method, path, body) {
  const r = await fetch(`${base}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
