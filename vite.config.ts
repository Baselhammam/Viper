import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// WHY a dev-server proxy instead of direct browser calls to api.anthropic.com:
// it keeps the API key server-side. The key is read here (Node side) from a
// NON-VITE_ env var on purpose — VITE_-prefixed vars get inlined into the client
// bundle, which is exactly what we want to avoid. Local-dev only.
export default defineConfig(({ mode }) => {
  // Third arg '' disables the prefix filter so we can read ANTHROPIC_API_KEY
  // (not just VITE_* vars) from the .env file.
  const env = loadEnv(mode, process.cwd(), '')
  const apiKey = env.ANTHROPIC_API_KEY ?? ''

  // Upstream TLS is verified by default. Set ANTHROPIC_PROXY_INSECURE_TLS=1 ONLY
  // when developing behind a TLS-intercepting proxy (corporate MITM / sandbox)
  // that presents an untrusted cert for api.anthropic.com — otherwise the upstream
  // handshake fails with "unable to verify the first certificate" (502). Dev-only.
  const verifyUpstreamTls = env.ANTHROPIC_PROXY_INSECURE_TLS !== '1'

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/api/anthropic': {
          target: 'https://api.anthropic.com',
          changeOrigin: true,
          secure: verifyUpstreamTls,
          rewrite: (path) => path.replace(/^\/api\/anthropic/, ''),
          configure: (proxy) => {
            // Inject auth server-side on every forwarded request, so the key
            // never reaches the browser.
            proxy.on('proxyReq', (proxyReq) => {
              proxyReq.setHeader('x-api-key', apiKey)
              proxyReq.setHeader('anthropic-version', '2023-06-01')
            })
          },
        },
      },
    },
  }
})
