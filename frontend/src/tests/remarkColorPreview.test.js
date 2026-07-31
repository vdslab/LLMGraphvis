import { describe, it, expect } from 'vitest';
import { unified } from 'unified';
import remarkParse from 'remark-parse';
import remarkGfm from 'remark-gfm';
import remarkRehype from 'remark-rehype';
import remarkColorPreview from '../utils/remarkColorPreview';

const swatches = (markdown) => {
  const processor = unified()
    .use(remarkParse)
    .use(remarkGfm)
    .use(remarkColorPreview)
    .use(remarkRehype);
  const tree = processor.runSync(processor.parse(markdown));

  const found = [];
  const walk = (node) => {
    if (node.tagName === 'a' && node.properties?.href === '#color-preview') {
      found.push(node.properties['data-color']);
    }
    (node.children || []).forEach(walk);
  };
  walk(tree);
  return found;
};

describe('remarkColorPreview', () => {
  it('marks a bare hex colour', () => {
    expect(swatches('Community 0 is #ff7f0e.')).toEqual(['#ff7f0e']);
  });

  it('marks a hex colour written as inline code', () => {
    // This is the form the agent actually uses when reporting a palette, and
    // the one the original text-only visitor missed entirely.
    expect(swatches('Community 0 is `#1f77b4`.')).toEqual(['#1f77b4']);
  });

  it('marks every colour in a list', () => {
    expect(swatches('- `#1f77b4`\n- `#ff7f0e`\n- `#2ca02c`')).toEqual([
      '#1f77b4',
      '#ff7f0e',
      '#2ca02c',
    ]);
  });

  it('marks colours inside table cells and emphasis', () => {
    expect(swatches('| c |\n| --- |\n| `#2ca02c` |')).toEqual(['#2ca02c']);
    expect(swatches('**#d62728** matters')).toEqual(['#d62728']);
  });

  it('marks several colours in one paragraph', () => {
    expect(swatches('#111111 and #222 and #333333')).toEqual([
      '#111111',
      '#222',
      '#333333',
    ]);
  });

  it('reads the full 6 digits rather than the first 3', () => {
    expect(swatches('#1f77b4')).toEqual(['#1f77b4']);
  });

  it('leaves a code snippet that merely contains a colour intact', () => {
    expect(swatches('`color: #1f77b4;`')).toEqual([]);
  });

  it('ignores headings and non-colour hashes', () => {
    expect(swatches('# Heading\n\nsee #community and #12345')).toEqual([]);
  });
});
