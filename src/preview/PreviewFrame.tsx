import { useEffect, useRef } from 'react'
import type { SelectedElement } from '../types'

interface Props {
  srcdoc: string
  onSelect: (selected: SelectedElement) => void
}

export function PreviewFrame({ srcdoc, onSelect }: Props) {
  const iframeRef = useRef<HTMLIFrameElement>(null)

  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      // A srcdoc + sandboxed (no allow-same-origin) iframe has a null/opaque
      // origin, so we can't match an origin string. Verify the message came from
      // OUR iframe's window instead.
      if (event.source !== iframeRef.current?.contentWindow) return
      const data = event.data
      if (!data || data.source !== 'scoped-edit-preview') return
      onSelect({ eid: String(data.eid), outerHTML: String(data.outerHTML) })
    }
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [onSelect])

  return (
    <iframe
      ref={iframeRef}
      title="preview"
      // allow-scripts lets the injected click handler run. We intentionally omit
      // allow-same-origin, keeping the frame at a null origin (sandboxed).
      sandbox="allow-scripts"
      srcDoc={srcdoc}
      style={{ width: '100%', height: '100%', border: 'none', background: '#fff' }}
    />
  )
}
