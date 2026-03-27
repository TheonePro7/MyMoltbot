import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const serviceToken = env.ANIME_OS_SERVICE_TOKEN || "";

  return {
    plugins: [vue()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8787",
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ""),
          configure(proxy) {
            proxy.on("proxyReq", (proxyReq) => {
              // 开发时由本机环境变量注入，不把 Token 写进前端打包产物
              if (serviceToken) proxyReq.setHeader("X-Service-Token", serviceToken);
            });
          },
        },
      },
    },
  };
});
