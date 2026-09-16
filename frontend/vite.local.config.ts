import { sites } from "@openai/sites-vite-plugin";
import vinext from "vinext";
import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "127.0.0.1",
    port: 4173,
    watch: { useFsEvents: false, usePolling: true },
  },
  plugins: [vinext(), sites()],
});
