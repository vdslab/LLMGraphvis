import { visit } from 'unist-util-visit';

/**
 * Turn hex colour codes in the agent's prose into swatch markers.
 *
 * Each match becomes a link with the sentinel url `#color-preview` and a
 * `data-color` property; the renderer in `components/chat/Markdown.jsx` draws
 * the swatch. A link is used because it survives remark → rehype without the
 * plugin needing to know anything about hast.
 *
 * Both `#1f77b4` and `` `#1f77b4` `` are matched. The backticked form is the
 * one that matters in practice — the agent reports palettes as inline code, and
 * an inlineCode node holds its own value rather than a child text node, so a
 * text-only visitor silently misses every colour the app actually produces.
 */

// 6- or 3-digit hex. 6 is tried first so `#1f77b4` is not read as `#1f7`.
const COLOR_PATTERN = /#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b/g;

const swatch = (color, { code = false } = {}) => ({
  type: 'link',
  title: null,
  url: '#color-preview',
  children: [{ type: code ? 'inlineCode' : 'text', value: color }],
  data: { hProperties: { 'data-color': color } },
});

export default function remarkColorPreview() {
  return (tree) => {
    visit(tree, ['text', 'inlineCode'], (node, index, parent) => {
      if (!parent || index === null || !node.value) return;

      COLOR_PATTERN.lastIndex = 0;
      if (!COLOR_PATTERN.test(node.value)) return;

      // `#1f77b4` on its own: replace the node, keeping the code styling.
      // Inline code holding anything else (a snippet that merely contains a
      // colour) is left alone — splitting it would break the code run.
      if (node.type === 'inlineCode') {
        const trimmed = node.value.trim();
        if (new RegExp(`^${COLOR_PATTERN.source}$`).test(trimmed)) {
          parent.children.splice(index, 1, swatch(trimmed, { code: true }));
          return index + 1;
        }
        return;
      }

      const value = node.value;
      const children = [];
      let lastIndex = 0;
      let match;

      COLOR_PATTERN.lastIndex = 0;
      while ((match = COLOR_PATTERN.exec(value)) !== null) {
        if (match.index > lastIndex) {
          children.push({ type: 'text', value: value.slice(lastIndex, match.index) });
        }
        children.push(swatch(match[0]));
        lastIndex = match.index + match[0].length;
      }

      if (lastIndex < value.length) {
        children.push({ type: 'text', value: value.slice(lastIndex) });
      }

      parent.children.splice(index, 1, ...children);
      // Continue past the nodes just inserted; revisiting them would loop.
      return index + children.length;
    });
  };
}
