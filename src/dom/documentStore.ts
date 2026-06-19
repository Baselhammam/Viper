import { CLICK_SCRIPT } from './injectClickScript'

export type SwapResult =
  | { ok: true; outerHTML: string }
  | { ok: false; error: string }

// Holds the canonical page as a parsed DOM Document. All element edits are DOM
// operations (querySelector + replaceChild) rather than string surgery; the
// document is serialized to a string only to feed the iframe srcdoc.
export class DocumentStore {
  private doc: Document

  constructor(html: string) {
    this.doc = new DOMParser().parseFromString(html, 'text/html')
  }

  /**
   * Replace the element carrying `eid` with the model's `replacementHtml`.
   *
   * The replacement is validated before swapping — it must parse to exactly one
   * top-level element with the SAME tag as the original — so a malformed response
   * can't silently corrupt the document. The original data-eid is then force-applied
   * to the replacement's root so the element stays addressable on the next click;
   * we don't trust the model to preserve the attribute, and that invariant is what
   * keeps swap-by-eid working.
   */
  swapByEid(eid: string, replacementHtml: string): SwapResult {
    const target = this.doc.querySelector(`[data-eid="${eid}"]`)
    if (!target) return { ok: false, error: `No element with data-eid "${eid}".` }

    const parsed = new DOMParser().parseFromString(replacementHtml, 'text/html')
    const elements = parsed.body.children
    if (elements.length !== 1) {
      return {
        ok: false,
        error: `Expected exactly 1 replacement element, got ${elements.length}.`,
      }
    }
    const replacement = elements[0]
    if (replacement.tagName !== target.tagName) {
      return {
        ok: false,
        error:
          `Replacement changed the tag ` +
          `(<${target.tagName.toLowerCase()}> → <${replacement.tagName.toLowerCase()}>); not swapping.`,
      }
    }

    replacement.setAttribute('data-eid', eid)
    // importNode adopts the element into this.doc before it can be inserted.
    const imported = this.doc.importNode(replacement, true)
    target.replaceWith(imported)
    return { ok: true, outerHTML: imported.outerHTML }
  }

  /** Serialize to a full HTML document string, with the click script injected. */
  serialize(): string {
    const html = '<!doctype html>' + this.doc.documentElement.outerHTML
    return html.replace('</body>', `${CLICK_SCRIPT}</body>`)
  }
}
