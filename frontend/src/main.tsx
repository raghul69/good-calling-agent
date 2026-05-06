import './index.css'
import { hydratePublicEnvFromApi } from './lib/hydratePublicEnv'

await hydratePublicEnvFromApi()

const { ensureDevEnvOrThrow } = await import('./lib/env')
ensureDevEnvOrThrow()

const { StrictMode } = await import('react')
const { createRoot } = await import('react-dom/client')
const { default: App } = await import('./App.tsx')

const rootEl = document.getElementById('root')
if (!rootEl) {
  throw new Error('Missing #root element')
}

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
