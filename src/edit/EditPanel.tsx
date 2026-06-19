import { useState } from 'react'
import type { CSSProperties, FormEvent } from 'react'
import type { SelectedElement } from '../types'

interface Props {
  selected: SelectedElement | null
  before: string | null
  after: string | null
  busy: boolean
  error: string | null
  onSubmit: (instruction: string) => void
}

export function EditPanel({ selected, before, after, busy, error, onSubmit }: Props) {
  const [instruction, setInstruction] = useState('')

  if (!selected) {
    return (
      <div style={panelStyle}>
        <p style={{ color: '#666' }}>Click an element in the preview to edit it.</p>
      </div>
    )
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    const trimmed = instruction.trim()
    if (trimmed && !busy) onSubmit(trimmed)
  }

  return (
    <div style={panelStyle}>
      <h3 style={{ margin: '0 0 4px' }}>Editing</h3>
      <code style={{ fontSize: 12, color: '#2563eb' }}>data-eid="{selected.eid}"</code>

      <form onSubmit={submit} style={{ marginTop: 12 }}>
        <input
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder='e.g. "make this blue"'
          disabled={busy}
          style={inputStyle}
        />
        <button type="submit" disabled={busy || !instruction.trim()} style={buttonStyle}>
          {busy ? 'Editing…' : 'Apply'}
        </button>
      </form>

      {error && <p style={{ color: '#c00', fontSize: 13 }}>{error}</p>}

      <Section title="Before" html={before} />
      <Section title="After" html={after} />
    </div>
  )
}

function Section({ title, html }: { title: string; html: string | null }) {
  return (
    <div style={{ marginTop: 16 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: '#444' }}>{title}</div>
      <pre style={preStyle}>{html ?? '—'}</pre>
    </div>
  )
}

const panelStyle: CSSProperties = {
  width: 360,
  padding: 20,
  borderLeft: '1px solid #e2e2e2',
  overflow: 'auto',
  fontFamily: 'system-ui, sans-serif',
  boxSizing: 'border-box',
}
const inputStyle: CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  fontSize: 14,
  boxSizing: 'border-box',
  border: '1px solid #ccc',
  borderRadius: 6,
}
const buttonStyle: CSSProperties = {
  marginTop: 8,
  padding: '8px 14px',
  fontSize: 14,
  border: 'none',
  borderRadius: 6,
  background: '#1a1a1a',
  color: '#fff',
  cursor: 'pointer',
}
const preStyle: CSSProperties = {
  margin: '4px 0 0',
  padding: 10,
  background: '#f5f5f5',
  borderRadius: 6,
  fontSize: 12,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
}
