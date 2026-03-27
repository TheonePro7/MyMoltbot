import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import "./style.css";
import App from "./App.vue";
import Home from "./views/Home.vue";
import Project from "./views/Project.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "home", component: Home },
    { path: "/p/:id", name: "project", component: Project, props: true },
  ],
});

createApp(App).use(router).mount("#app");
