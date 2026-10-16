import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const projectRoot = fileURLToPath(new URL('../..', import.meta.url))

/** Stops the test backend. The development containers are left running. */
export default function globalTeardown(): void {
  if (process.env.E2E_KEEP_BACKEND) {
    return
  }
  execFileSync('docker', ['compose', '--profile', 'e2e', 'stop', 'backend-e2e'], {
    cwd: projectRoot,
    stdio: 'inherit',
  })
}
