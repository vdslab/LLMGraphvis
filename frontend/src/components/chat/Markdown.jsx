import { lazy, Suspense } from 'react';
import MarkdownBody from './MarkdownBody';

const MathMarkdown = lazy(() => import('./MathMarkdown'));

export default function Markdown({ children }) {
  if (!String(children ?? '').includes('$')) return <MarkdownBody>{children}</MarkdownBody>;
  return (
    <Suspense fallback={<MarkdownBody>{children}</MarkdownBody>}>
      <MathMarkdown>{children}</MathMarkdown>
    </Suspense>
  );
}
