import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import * as ElementPlusIconsVue from "@element-plus/icons-vue";
import axios from "axios";
import i18n from "./locales";

import App from "./App.vue";
import router from "./router";
import "./assets/css/global.scss";

axios.defaults.xsrfCookieName = "csrftoken";
axios.defaults.xsrfHeaderName = "X-CSRFToken";
axios.defaults.withCredentials = true;

const app = createApp(App);

const pinia = createPinia();
app.use(pinia);

async function init() {
  for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component);
  }

  app.use(router);
  app.use(i18n);
  app.use(ElementPlus);
  app.mount("#app");
}

init();
