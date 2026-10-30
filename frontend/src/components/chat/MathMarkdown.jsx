import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import 'katex/dist/katex.min.css';
import MarkdownBody from './MarkdownBody';

const REMARK = [remarkMath];
const REHYPE = [[rehypeKatex, { throwOnError: false }]];

export default function MathMarkdown({ children }) {
  return <MarkdownBody remarkPlugins={REMARK} rehypePlugins={REHYPE}>{children}</MarkdownBody>;
}
