import { defineConfig } from "@playwright/test";

// E2E against a production build (dev's HMR socket can block hydration). Locally it reuses an
// already-running server on :3000; in CI it builds and starts one. The API must be reachable at
// NEXT_PUBLIC_API_URL for the data-dependent assertions.
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  use: { baseURL: "http://127.0.0.1:3000" },
  webServer: {
    command: "NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run build && NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run start -- -p 3000",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: true,
    timeout: 180000,
  },
});
