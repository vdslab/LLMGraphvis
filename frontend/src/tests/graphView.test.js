import { describe, expect, it } from 'vitest';
import {
  labelCandidates,
  labelText,
  placeLabels,
  viewportTransform,
} from '../utils/graphView';

describe('labelText', () => {
  it('shortens with an ellipsis only past max length', () => {
    expect(labelText('Beethoven', 5)).toBe('Beet…');
    expect(labelText('Bach', 5)).toBe('Bach');
    expect(labelText(42)).toBe('42');
  });
});

describe('labelCandidates', () => {
  const nodes = [
    { id: 'a', size: 5, show_label: true },
    { id: 'b', size: 50, show_label: false },
    { id: 'c', size: 1, show_label: true, highlighted: true },
  ];

  it('follows the backend choice, highlighted first then larger', () => {
    expect(labelCandidates(nodes).map((n) => n.id)).toEqual(['c', 'a']);
  });

  it('lets the Labels button force every label on', () => {
    expect(labelCandidates(nodes, { showLabels: true })).toHaveLength(3);
  });

  it('draws nothing without a backend choice or the button', () => {
    expect(labelCandidates([{ id: 'a' }, { id: 'b' }])).toEqual([]);
  });
});

describe('placeLabels', () => {
  it('drops a label that would overlap one already placed', () => {
    const project = (n) => [n.x, n.y];
    const visible = placeLabels(
      [
        { id: 'first', label: 'Mozart', x: 100, y: 100 },
        { id: 'clash', label: 'Haydn', x: 104, y: 101 },
        { id: 'apart', label: 'Bach', x: 400, y: 100 },
      ],
      project,
    );
    expect([...visible]).toEqual(['first', 'apart']);
  });
});

describe('viewportTransform', () => {
  const viewBox = { x: -1000, y: -1000, width: 2000, height: 2000 };
  const nodes = [
    { id: 'a', x: 0, y: 0 },
    { id: 'b', x: 200, y: 0 },
    { id: 'far', x: -900, y: 900 },
  ];

  it('centres the framed nodes and zooms in', () => {
    const t = viewportTransform({ mode: 'nodes', node_ids: ['a', 'b'], padding: 0 }, nodes, viewBox);
    expect(t.k).toBeGreaterThan(1);
    // The midpoint of a and b lands on the centre of the viewBox.
    expect(t.k * 100 + t.x).toBeCloseTo(0);
    expect(t.k * 0 + t.y).toBeCloseTo(0);
  });

  it('resets to identity for fit and ignores unknown nodes', () => {
    expect(viewportTransform({ mode: 'fit' }, nodes, viewBox)).toEqual({ k: 1, x: 0, y: 0 });
    expect(viewportTransform({ mode: 'nodes', node_ids: ['zz'] }, nodes, viewBox)).toBeNull();
  });
});
