import { useCallback, useRef, useState } from 'react'
import { DocumentStore } from './dom/documentStore'
import { SEED_HTML } from './seed'
import { PreviewFrame } from './preview/PreviewFrame'
import { EditPanel } from './edit/EditPanel'
import { scopedEdit } from './edit/scopedEdit'
import type { SelectedElement } from './types'

export default function App() {
  // The canonical document is a mutable instance, not React state — `srcdoc` is the
  // serialized snapshot that drives re-renders. useState's lazy initializer (not a
  // ref) creates it once, on the initial render.
  const [store] = useState(() => new DocumentStore(SEED_HTML))
  const [srcdoc, setSrcdoc] = useState(() => store.serialize())
  const [selected, setSelected] = useState<SelectedElement | null>(null)
  const [before, setBefore] = useState<string | null>(null)
  const [after, setAfter] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const handleSelect = useCallback((next: SelectedElement) => {
    setSelected(next)
    setBefore(next.outerHTML)
    setAfter(null)
    setError(null)
  }, [])

  const handleSubmit = useCallback(
    async (instruction: string) => {
      if (!selected) return

      // Cancel any in-flight edit so a rapid re-submit doesn't race.
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setBusy(true)
      setError(null)
      try {
        const { html } = await scopedEdit(selected.outerHTML, instruction, controller.signal)
        if (abortRef.current !== controller) return // superseded by a newer request

        const result = store.swapByEid(selected.eid, html)
        if (!result.ok) throw new Error(result.error)

        setAfter(result.outerHTML)
        setSrcdoc(store.serialize())
        // Keep the selection pointed at the new outerHTML for chained edits.
        setSelected({ eid: selected.eid, outerHTML: result.outerHTML })
      } catch (err) {
        if (controller.signal.aborted) return // aborted edits are expected, not errors
        setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (abortRef.current === controller) setBusy(false)
      }
    },
    [selected, store],
  )

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100vw' }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <PreviewFrame srcdoc={srcdoc} onSelect={handleSelect} />
      </div>
      <EditPanel
        selected={selected}
        before={before}
        after={after}
        busy={busy}
        error={error}
        onSubmit={handleSubmit}
      />
    </div>
  )
}
