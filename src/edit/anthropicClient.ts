import Anthropic from '@anthropic-ai/sdk'

// LOCAL-DEV ONLY. The browser talks to the Vite dev-server proxy at /api/anthropic
// (see vite.config.ts), which injects the real ANTHROPIC_API_KEY server-side. The
// apiKey below is a placeholder that never authenticates anything — the proxy
// overrides the x-api-key header before the request leaves the dev server.
//
// dangerouslyAllowBrowser is still required because the SDK refuses to run in a
// browser otherwise (its guard is environment-based, not key-based). It is safe
// here precisely because no real key is present client-side.
export const anthropic = new Anthropic({
  baseURL: '/api/anthropic',
  apiKey: 'proxy-injected',
  dangerouslyAllowBrowser: true,
})
