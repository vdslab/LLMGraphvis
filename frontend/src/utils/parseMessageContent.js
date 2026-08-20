/**
 * Split a stored chat message into renderable blocks.
 *
 * A message is one Markdown string, so everything that is not prose is marked
 * up inside it. The producing side is `backend/app/services/llm/markup.py` and
 * the `<thought>` tags written by the agent engine; the two are one contract.
 *
 *   <thought>…</thought>                    model reasoning, and only that
 *   <steps>…</steps>                        a fixed backend pipeline log
 *   <collapsible title="…" open="true">…</collapsible>
 *   <tool_execution_marker index="N"/>      position of the Nth tool call
 *
 * Messages arrive by streaming, so every closing tag is optional: an unclosed
 * block consumes the rest of the text and is reported with `complete: false`,
 * which lets the renderer show it as still-running instead of dropping it.
 */

const BLOCK_PATTERN = new RegExp(
  [
    '<thought>([\\s\\S]*?)(<\\/thought>|$)',
    '<steps>([\\s\\S]*?)(<\\/steps>|$)',
    '<collapsible([^>]*)>([\\s\\S]*?)(<\\/collapsible>|$)',
    '<tool_execution_marker\\s+index="(\\d+)"\\s*\\/>',
  ].join('|'),
  'gi',
);

// Some OpenAI-compatible models vary the reserved tag's casing/spacing, and
// some gateways HTML-escape it before it reaches the browser. Canonicalise
// only this engine-owned tag before parsing so none of those forms leaks into
// the visible Markdown response.
const normalizeThoughtTags = (content) => content
  .replace(/&lt;\s*(\/?)\s*thought\s*&gt;/gi, '<$1thought>')
  .replace(/<\s*(\/?)\s*thought\s*>/gi, '<$1thought>');

const attribute = (attrs, name) => {
  const match = new RegExp(`${name}="([^"]*)"`).exec(attrs || '');
  return match ? match[1] : '';
};

/**
 * @param {string} content
 * @returns {Array<object>} blocks, in document order
 */
export function parseMessageContent(content) {
  if (!content) return [];

  const normalizedContent = normalizeThoughtTags(content);

  const blocks = [];
  let lastIndex = 0;
  let match;

  const pushText = (text) => {
    if (text && text.trim()) blocks.push({ type: 'text', content: text.trim() });
  };

  BLOCK_PATTERN.lastIndex = 0;
  while ((match = BLOCK_PATTERN.exec(normalizedContent)) !== null) {
    const [
      full,
      thought,
      thoughtClose,
      steps,
      stepsClose,
      collapsibleAttrs,
      collapsibleBody,
      collapsibleClose,
      toolIndex,
    ] = match;

    pushText(normalizedContent.slice(lastIndex, match.index));
    lastIndex = match.index + full.length;

    if (thought !== undefined) {
      blocks.push({
        type: 'thought',
        content: thought.trim(),
        complete: Boolean(thoughtClose),
      });
    } else if (steps !== undefined) {
      blocks.push({
        type: 'steps',
        steps: steps
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean),
        complete: Boolean(stepsClose),
      });
    } else if (collapsibleBody !== undefined) {
      blocks.push({
        type: 'collapsible',
        title: attribute(collapsibleAttrs, 'title') || 'Details',
        open: attribute(collapsibleAttrs, 'open') === 'true',
        content: collapsibleBody.trim(),
        complete: Boolean(collapsibleClose),
      });
    } else if (toolIndex !== undefined) {
      blocks.push({ type: 'tool', index: Number(toolIndex) });
    }
  }

  pushText(normalizedContent.slice(lastIndex));
  return blocks;
}

export default parseMessageContent;
