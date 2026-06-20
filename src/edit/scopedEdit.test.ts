// Tests for scopedEdit — the response-parsing layer over the Anthropic SDK. We mock
// the SDK client so these run offline and deterministically (no API key, no network):
// each test feeds a canned `messages.create` response and asserts how scopedEdit
// interprets it. This exercises our parsing/validation, not the model itself.
import { describe, expect, it, vi } from 'vitest'

// `create` stands in for anthropic.messages.create; the vi.mock below swaps the real
// SDK module for this fake so importing scopedEdit picks up the mock.
const create = vi.fn()
vi.mock('./anthropicClient', () => ({
  anthropic: { messages: { create } },
}))

// Imported AFTER the mock is registered so scopedEdit binds to the fake client.
const { scopedEdit } = await import('./scopedEdit')

describe('scopedEdit', () => {
  // Happy path: a well-formed tool_use block yields its html, and we also assert the
  // request forces the replace_element tool (the mechanism that guarantees structured
  // output instead of prose we'd have to parse).
  it('returns the html from the replace_element tool call', async () => {
    create.mockResolvedValueOnce({
      content: [{ type: 'tool_use', name: 'replace_element', input: { html: '<p>new</p>' } }],
    })

    const result = await scopedEdit('<p>old</p>', 'make it new')

    expect(result).toEqual({ html: '<p>new</p>' })
    expect(create).toHaveBeenCalledWith(
      expect.objectContaining({ tool_choice: { type: 'tool', name: 'replace_element' } }),
      expect.objectContaining({ signal: undefined }),
    )
  })

  // If the model replies with prose instead of calling the tool, we must surface a
  // clear error rather than return garbage downstream.
  it('throws when no tool_use block is returned', async () => {
    create.mockResolvedValueOnce({ content: [{ type: 'text', text: 'oops' }] })

    await expect(scopedEdit('<p>old</p>', 'x')).rejects.toThrow(
      'Model did not return a replace_element tool call.',
    )
  })

  // A tool call with a missing/empty html field is also an error, not an empty swap.
  it('throws when the tool call has no html', async () => {
    create.mockResolvedValueOnce({
      content: [{ type: 'tool_use', name: 'replace_element', input: {} }],
    })

    await expect(scopedEdit('<p>old</p>', 'x')).rejects.toThrow(
      'replace_element returned no HTML.',
    )
  })
})
