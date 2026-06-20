// Tests for DocumentStore — the safety net around swap-by-eid. The model's output
// is untrusted, so these lock in the validation invariants that keep a bad response
// from silently corrupting the document. They run against jsdom's DOMParser (see
// vitest.config.ts), the same API the store uses in the browser.
import { describe, expect, it } from 'vitest'
import { DocumentStore } from './documentStore'

const PAGE = `<!doctype html><html><body>
  <h1 data-eid="a">Title</h1>
  <p data-eid="b">Body</p>
</body></html>`

describe('DocumentStore.swapByEid', () => {
  // Happy path: the swap lands AND the original data-eid is re-applied to the
  // replacement, which is the invariant that keeps the element addressable on the
  // next click (we don't trust the model to preserve the attribute itself).
  it('swaps in the replacement and re-applies the original data-eid', () => {
    const store = new DocumentStore(PAGE)
    const result = store.swapByEid('a', '<h1>New Title</h1>')

    expect(result.ok).toBe(true)
    if (!result.ok) throw new Error('unreachable')
    expect(result.outerHTML).toContain('New Title')
    expect(result.outerHTML).toContain('data-eid="a"')
  })

  // A stale/unknown eid must fail cleanly rather than throw or no-op silently.
  it('rejects an unknown eid', () => {
    const store = new DocumentStore(PAGE)
    const result = store.swapByEid('missing', '<h1>x</h1>')

    expect(result.ok).toBe(false)
  })

  // The model must return exactly one top-level element; multiple roots are rejected
  // so a malformed response can't inject extra siblings into the page.
  it('rejects a replacement that is not exactly one top-level element', () => {
    const store = new DocumentStore(PAGE)
    const result = store.swapByEid('a', '<h1>one</h1><h1>two</h1>')

    expect(result.ok).toBe(false)
  })

  // The replacement must keep the original tag — swapping <h1> for <div> is treated
  // as a corrupt edit, not an allowed change.
  it('rejects a replacement that changes the tag', () => {
    const store = new DocumentStore(PAGE)
    const result = store.swapByEid('a', '<div>wrong tag</div>')

    expect(result.ok).toBe(false)
  })

  // serialize() must inject the click script inside the document (before </body>),
  // otherwise the rendered iframe would have no click-to-select listener.
  it('serializes with the click script injected before </body>', () => {
    const store = new DocumentStore(PAGE)
    const html = store.serialize()

    expect(html.indexOf('<script')).toBeLessThan(html.indexOf('</body>'))
  })
})
