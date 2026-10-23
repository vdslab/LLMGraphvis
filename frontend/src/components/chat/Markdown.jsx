import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import remarkColorPreview from '../../utils/remarkColorPreview';

const PLUGINS = [remarkGfm, remarkBreaks, remarkMath, remarkColorPreview];
// `throwOnError: false` shows a malformed formula as red source instead of
// failing the whole message.
const REHYPE_PLUGINS = [[rehypeKatex, { throwOnError: false }]];

/**
 * Renders a hex colour as a swatch followed by its code.
 *
 * The colour is read from the hast node's `data-color` property — the shape
 * `remarkColorPreview` writes through `data.hProperties`. Reading it off the
 * rendered children instead only works when the code is the sole child, which
 * is why the swatch used to come out transparent inside emphasis or a table.
 */
const ColorSwatch = ({ node, children }) => {
  const color = node?.properties?.['data-color'];
  if (!color) return <span>{children}</span>;

  return (
    <span className="color-chip" title={color}>
      <span className="color-chip__swatch" style={{ backgroundColor: color }} />
      <span className="color-chip__code">{color}</span>
    </span>
  );
};

const COMPONENTS = {
  a: ({ node, href, children, ...props }) => {
    if (href === '#color-preview') {
      return <ColorSwatch node={node}>{children}</ColorSwatch>;
    }
    return (
      <a href={href} {...props} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  },
};

const Markdown = ({ children }) => (
  <div className="markdown-content">
    <ReactMarkdown
      remarkPlugins={PLUGINS}
      rehypePlugins={REHYPE_PLUGINS}
      components={COMPONENTS}
    >
      {children}
    </ReactMarkdown>
  </div>
);

export default Markdown;
