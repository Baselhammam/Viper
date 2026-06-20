import { describe, expect, it } from 'vitest'
import { DocumentStore } from './documentStore'

const PAGE = `<!doctype html><html><body>
  <h1 data-eid="a">Title</h1>
  <p data-eid="b">Body</p>
</body></html>`

describe('DocumentStore.swapByEid', () => {
  it('swaps in the replacement and re-applies the original data-eid', () => {
    const store = new DocumentStore(PAGE)
    const result = store.swapByEid('a', '<h1>New Title</h1>')

    expect(result.ok).toBe(true)
    if (!result.ok) throw new Error('unreachable')
    expect(result.outerHTML).toContain('New Title')
    expect(result.outerHTML).toContain('data-eid="a"')
  })

  it('rejects an unknown eid', () => {
    const store = new DocumentStore(PAGE)
    const result = store.swapByEid('missing', '<h1>x</h1>')

    expect(result.ok).toBe(false)
  })

  it('rejects a replacement that is not exactly one top-level element', () => {
    const store = new DocumentStore(PAGE)
    const result = store.swapByEid('a', '<h1>one</h1><h1>two</h1>')

    expect(result.ok).toBe(false)
  })

  it('rejects a replacement that changes the tag', () => {
    const store = new DocumentStore(PAGE)
    const result = store.swapByEid('a', '<div>wrong tag</div>')

    expect(result.ok).toBe(false)
  })

  it('serializes with the click script injected before </body>', () => {
    const store = new DocumentStore(PAGE)
    const html = store.serialize()

    expect(html.indexOf('<script')).toBeLessThan(html.indexOf('</body>'))
  })
})
