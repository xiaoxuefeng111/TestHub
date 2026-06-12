module.exports = {
  root: true,
  env: {
    browser: true,
    es2022: true,
    node: true,
  },
  extends: [
    "eslint:recommended",
    "plugin:vue/vue3-recommended",
    "@vue/eslint-config-prettier",
  ],
  parserOptions: {
    ecmaVersion: "latest",
    sourceType: "module",
  },
  ignorePatterns: [
    "dist/",
    "node_modules/",
    "src/views/app-automation/elements/components/CaptureElementDialog.vue",
  ],
  rules: {
    "vue/multi-word-component-names": "off",
    "vue/no-v-html": "off",
    "no-unused-vars": "off",
    "vue/no-unused-vars": "off",
    "no-useless-catch": "off",
    "no-dupe-keys": "off",
    "no-useless-escape": "off",
    "vue/no-template-shadow": "off",
  },
};
