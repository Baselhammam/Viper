export interface SelectedElement {
  /** The clicked element's data-eid. Stable across edits — see DocumentStore.swapByEid. */
  eid: string
  /** The element's current outerHTML (what we send to the model). */
  outerHTML: string
}

export interface ScopedEditResult {
  /** outerHTML of the replacement element returned by the model. */
  html: string
}
