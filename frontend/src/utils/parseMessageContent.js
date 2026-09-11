import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkDirective from 'remark-directive';
import { visit } from 'unist-util-visit';

/**
 * Split one persisted Markdown message into typed chat blocks.
 *
 * New messages use CommonMark directives. Legacy HTML-like tags remain readable
 * so existing conversations do not change when reloaded.
 *
 *   :::thought ... :::
 *   :::steps ... :::
 *   :::collapsible{title="…" open="true"} ... :::
 *   ::tool-execution{index="N"}
 */

const DIRECTIVE_PARSER = unified().use(remarkParse).use(remarkDirective);

const LEGACY_BLOCK_PATTERN = new RegExp(
  [
    '<thought>([\\s\\S]*?)(<\\/thought>|$)',
    '<steps>([\\s\\S]*?)(<\\/steps>|$)',
    '<collapsible([^>]*)>([\\s\\S]*?)(<\\/collapsible>|$)',
    '<tool_execution_marker\\s+index="(\\d+)"\\s*\\/>',
    '(<visualization[_-]output\\b[^>]*(?:\\/?>|$))',
  ].join('|'),
  'gi',
);

const normalizeLegacyTags = (content) => content
  .replace(/&lt;\s*(\/?)\s*thought\s*&gt;/gi, '<$1thought>')
  .replace(/<\s*(\/?)\s*thought\s*>/gi, '<$1thought>')
  .replace(
    /&lt;\s*(visualization[_-]output\b[\s\S]*?\/?\s*)&gt;/gi,
    '<$1>',
  );

const legacyAttribute = (attrs, name) => {
  const match = new RegExp(`${name}="([^"]*)"`).exec(attrs || '');
  return match ? match[1] : '';
};

const directiveBody = (source, node) => {
  const first = node.children?.[0]?.position?.start?.offset;
  const last = node.children?.at(-1)?.position?.end?.offset;
  if (!Number.isInteger(first) || !Number.isInteger(last)) return '';
  return source.slice(first, last).trim();
};

const stepsBlock = (body, complete = true) => ({
  type: 'steps',
  steps: body
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean),
  complete,
});

const collectDirectiveRanges = (source) => {
  let tree;
  try {
    tree = DIRECTIVE_PARSER.parse(source);
  } catch {
    return [];
  }

  const ranges = [];
  visit(tree, (node, _index, parent) => {
    const start = node.position?.start?.offset;
    const end = node.position?.end?.offset;
    if (!Number.isInteger(start) || !Number.isInteger(end)) return;

    // Chat control blocks are document-level. A directive inside ordinary
    // Markdown content remains ordinary Markdown instead of stealing text.
    if (parent?.type === 'root' && node.type === 'containerDirective') {
      const body = directiveBody(source, node);
      if (node.name === 'thought') {
        ranges.push({ start, end, block: { type: 'thought', content: body, complete: true } });
      } else if (node.name === 'steps') {
        ranges.push({ start, end, block: stepsBlock(body) });
      } else if (node.name === 'collapsible') {
        ranges.push({
          start,
          end,
          block: {
            type: 'collapsible',
            title: node.attributes?.title || 'Details',
            open: node.attributes?.open === 'true',
            content: body,
            complete: true,
          },
        });
      }
    }

    if (
      parent?.type === 'root'
      && node.type === 'leafDirective'
      && node.name === 'tool-execution'
    ) {
      const toolIndex = Number(node.attributes?.index);
      if (Number.isInteger(toolIndex) && toolIndex >= 0) {
        ranges.push({ start, end, block: { type: 'tool', index: toolIndex } });
      }
    }

    // Some models invent this internal-looking HTML tag. It has never been a
    // frontend/backend contract, so hide it instead of showing implementation
    // syntax to the user. Arbitrary HTML is not enabled or executed.
    if (
      node.type === 'html'
      && /^<visualization[_-]output\b/i.test(node.value.trim())
    ) {
      ranges.push({ start, end, block: null });
    }
  });
  return ranges;
};

const collectLegacyRanges = (source) => {
  const ranges = [];
  let match;
  LEGACY_BLOCK_PATTERN.lastIndex = 0;
  while ((match = LEGACY_BLOCK_PATTERN.exec(source)) !== null) {
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
      visualizationOutput,
    ] = match;

    let block = null;
    if (thought !== undefined) {
      block = { type: 'thought', content: thought.trim(), complete: Boolean(thoughtClose) };
    } else if (steps !== undefined) {
      block = stepsBlock(steps, Boolean(stepsClose));
    } else if (collapsibleBody !== undefined) {
      block = {
        type: 'collapsible',
        title: legacyAttribute(collapsibleAttrs, 'title') || 'Details',
        open: legacyAttribute(collapsibleAttrs, 'open') === 'true',
        content: collapsibleBody.trim(),
        complete: Boolean(collapsibleClose),
      };
    } else if (toolIndex !== undefined) {
      block = { type: 'tool', index: Number(toolIndex) };
    } else if (visualizationOutput === undefined) {
      continue;
    }
    ranges.push({ start: match.index, end: match.index + full.length, block });
  }
  return ranges;
};

/**
 * @param {string} content
 * @returns {Array<object>} blocks, in document order
 */
export function parseMessageContent(content) {
  if (!content) return [];
  const source = normalizeLegacyTags(content);
  const candidates = [
    ...collectDirectiveRanges(source),
    ...collectLegacyRanges(source),
  ].sort((a, b) => a.start - b.start || b.end - a.end);

  const blocks = [];
  let cursor = 0;
  const pushText = (text) => {
    if (text && text.trim()) blocks.push({ type: 'text', content: text.trim() });
  };

  for (const range of candidates) {
    if (range.start < cursor) continue;
    pushText(source.slice(cursor, range.start));
    if (range.block) blocks.push(range.block);
    cursor = range.end;
  }
  pushText(source.slice(cursor));
  return blocks;
}

export default parseMessageContent;
