import { anthropic } from './anthropicClient'
import type { ScopedEditResult } from '../types'

// Tiny scoped edits run on the current Haiku model to prove the cost story: we
// send ONLY the one element + the instruction, and receive ONLY its replacement —
// the whole document is never re-sent or regenerated.
const SCOPED_EDIT_MODEL = 'claude-haiku-4-5'
const TOOL_NAME = 'replace_element'

const SYSTEM_PROMPT =
  "You edit a single HTML element. You are given one element's outerHTML and an " +
  'instruction describing a change to it. Apply ONLY that change. Return the complete ' +
  "replacement element via the replace_element tool. Preserve the element's tag, its " +
  'data-eid attribute, and any content the instruction does not ask you to change. ' +
  'Return exactly one top-level element — no surrounding prose, no markdown fences.'

/**
 * Send one element + an instruction to the model and get back its replacement.
 *
 * Forced tool use (tool_choice) guarantees structured output — an `html` string —
 * so we never have to parse prose or strip markdown fences from the response.
 * `signal` lets a newer request abort an in-flight one.
 */
export async function scopedEdit(
  outerHTML: string,
  instruction: string,
  signal?: AbortSignal,
): Promise<ScopedEditResult> {
  const response = await anthropic.messages.create(
    {
      model: SCOPED_EDIT_MODEL,
      max_tokens: 1024,
      system: SYSTEM_PROMPT,
      tools: [
        {
          name: TOOL_NAME,
          description: 'Return the full replacement element as an HTML string.',
          input_schema: {
            type: 'object',
            properties: {
              html: {
                type: 'string',
                description: 'The complete outerHTML of the replacement element.',
              },
            },
            required: ['html'],
          },
        },
      ],
      tool_choice: { type: 'tool', name: TOOL_NAME },
      messages: [
        {
          role: 'user',
          content: `Element:\n${outerHTML}\n\nInstruction: ${instruction}`,
        },
      ],
    },
    { signal },
  )

  const toolUse = response.content.find((block) => block.type === 'tool_use')
  if (!toolUse || toolUse.type !== 'tool_use') {
    throw new Error('Model did not return a replace_element tool call.')
  }
  const html = (toolUse.input as { html?: unknown }).html
  if (typeof html !== 'string' || html.trim() === '') {
    throw new Error('replace_element returned no HTML.')
  }
  return { html }
}
