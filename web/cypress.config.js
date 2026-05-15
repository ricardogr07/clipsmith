const { defineConfig } = require("cypress");
const reactPlugin = require("@vitejs/plugin-react");
const path = require("path");

const react = reactPlugin.default ?? reactPlugin;

module.exports = defineConfig({
  component: {
    devServer: {
      framework: "react",
      bundler: "vite",
      viteConfig: {
        plugins: [react()],
        define: {
          "process.env": "{}",
        },
        resolve: {
          alias: {
            "@": path.resolve(__dirname, "./"),
            "next/link": path.resolve(__dirname, "./cypress/mocks/next-link.jsx"),
          },
        },
      },
    },
    specPattern: "cypress/component/**/*.cy.tsx",
    supportFile: "cypress/support/component.ts",
  },
  e2e: {
    baseUrl: "http://localhost:3000",
    specPattern: "cypress/e2e/**/*.cy.ts",
    supportFile: "cypress/support/e2e.ts",
  },
});
