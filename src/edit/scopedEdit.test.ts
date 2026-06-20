import { describe, expect, it, vi } from 'vitest'

const create = vi.fn()
vi.mock('./anthropicClient', () => ({
  anthropic: { messages: { create } },
}))

const { scopedEdit } = await import('./scopedEdit')

describe('scopedEdit', () => {
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

  it('throws when no tool_use block is returned', async () => {
    create.mockResolvedValueOnce({ content: [{ type: 'text', text: 'oops' }] })

    await expect(scopedEdit('<p>old</p>', 'x')).rejects.toThrow(
      'Model did not return a replace_element tool call.',
    )
  })

  it('throws when the tool call has no html', async () => {
    create.mockResolvedValueOnce({
      content: [{ type: 'tool_use', name: 'replace_element', input: {} }],
    })

    await expect(scopedEdit('<p>old</p>', 'x')).rejects.toThrow(
      'replace_element returned no HTML.',
    )
  })
})
