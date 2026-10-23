import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import Markdown from '../components/chat/Markdown';

describe('Markdown', () => {
  it('renders inline math', () => {
    const { container } = render(<Markdown>{'A $\\rightarrow$ B'}</Markdown>);
    expect(container.querySelector('.katex')).not.toBeNull();
    expect(container.textContent).not.toContain('$');
  });

  it('shows a model-drawn HTML swatch as one colour chip and no markup', () => {
    const { container } = render(
      <Markdown>{'<span style="background-color:#1f77b4"></span> `#1f77b4`'}</Markdown>,
    );
    expect(container.querySelectorAll('.color-chip')).toHaveLength(1);
    expect(container.textContent).not.toContain('<span');
  });
});
