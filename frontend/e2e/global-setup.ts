import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const projectRoot = fileURLToPath(new URL('../..', import.meta.url))

/**
 * Starts the backend the browser tests use. Recreating the container also
 * recreates its database, so every run starts empty.
 */
export default function globalSetup(): void {
  execFileSync(
    'docker',
    ['compose', '--profile', 'e2e', 'up', '--detach', '--build', '--force-recreate', '--wait', 'backend-e2e'],
    { cwd: projectRoot, stdio: 'inherit' },
  )
}
