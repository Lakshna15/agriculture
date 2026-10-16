import { defineConfig, devices } from '@playwright/test'

// The browser tests run the real frontend against a separate backend
// container (backend-e2e in docker-compose.yml) with its own throwaway
// database, so they never touch development data.
const frontendPort = 5174
const e2eBackendPort = process.env.E2E_BACKEND_PORT ?? '8001'

// On Windows the installed Microsoft Edge is used, so no browser has to be
// downloaded. Elsewhere, set PLAYWRIGHT_CHANNEL or install Playwright's Chromium.
const browserChannel =
  process.env.PLAYWRIGHT_CHANNEL ?? (process.platform === 'win32' ? 'msedge' : undefined)

export default defineConfig({
  testDir: './e2e',
  // The flows share one backend, so they run one at a time.
  workers: 1,
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  reporter: [['list'], ['html', { open: 'never' }]],
  globalSetup: './e2e/global-setup.ts',
  globalTeardown: './e2e/global-teardown.ts',
  timeout: 60_000,
  use: {
    baseURL: `http://localhost:${frontendPort}`,
    // "Today" for pickup dates is decided in the marketplace's time zone, so
    // the browser uses the same one.
    timezoneId: process.env.MARKETPLACE_TIMEZONE ?? 'America/New_York',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], channel: browserChannel },
    },
  ],
  webServer: {
    command: `npm run dev -- --port ${frontendPort} --strictPort`,
    url: `http://localhost:${frontendPort}`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: { API_PROXY_TARGET: `http://localhost:${e2eBackendPort}` },
  },
})
