// Pure helpers behind NetworkGraph's view channels (ADR 0023): which labels
// are drawn, which survive overlap, and where a viewport instruction points.
// Kept free of D3 selections so they can be tested without a DOM layout.

export const DEFAULT_LABEL_PX = 11;
export const SCALE_EXTENT = [0.1, 12];
// Framing a single node (zero extent) shows this share of the canvas around it.
const MIN_FRAME_SHARE = 0.12;
// Rough glyph width relative to font size; enough to thin overlaps without
// measuring text, which would force a layout per label.
const CHAR_WIDTH = 0.6;

export function labelText(label, maxLength) {
  const text = label == null ? '' : String(label);
  if (!maxLength || text.length <= maxLength) return text;
  return `${text.slice(0, Math.max(1, maxLength - 1))}…`;
}

// The backend decides per-node visibility once the agent has chosen one
// (`show_label`); the canvas's Labels button still forces every label on.
export function labelCandidates(nodes, { showLabels = false } = {}) {
  const backendDecides = nodes.some((n) => n.show_label !== undefined);
  const chosen = nodes.filter((n) => showLabels || (backendDecides && n.show_label));
  // Highlighted first, then larger nodes: the order in which overlaps are won.
  return chosen.sort(
    (a, b) =>
      Number(Boolean(b.highlighted)) - Number(Boolean(a.highlighted)) ||
      (b.size || 0) - (a.size || 0),
  );
}

// Greedy overlap removal in screen space. `project` maps a node to screen
// pixels; returns the ids whose label stays visible.
export function placeLabels(candidates, project, { fontPx = DEFAULT_LABEL_PX, maxLength } = {}) {
  const placed = [];
  const visible = new Set();
  for (const node of candidates) {
    const [x, y] = project(node);
    const width = labelText(node.label, maxLength).length * fontPx * CHAR_WIDTH;
    const box = {
      x0: x - width / 2,
      x1: x + width / 2,
      y0: y - fontPx * 1.9,
      y1: y - fontPx * 0.6,
    };
    const hit = placed.some(
      (p) => box.x0 < p.x1 && box.x1 > p.x0 && box.y0 < p.y1 && box.y1 > p.y0,
    );
    if (!hit) {
      placed.push(box);
      visible.add(node.id);
    }
  }
  return visible;
}

// The zoom transform {k, x, y} that frames a viewport instruction inside the
// SVG's viewBox, or null when there is nothing to frame.
export function viewportTransform(directive, nodes, viewBox) {
  if (!directive) return null;
  if (directive.mode === 'fit') return { k: 1, x: 0, y: 0 };
  const wanted = new Set(directive.node_ids || []);
  const targets = nodes.filter((n) => wanted.has(n.id));
  if (!targets.length) return null;

  const xs = targets.map((n) => n.x);
  const ys = targets.map((n) => n.y);
  const minSide = Math.min(viewBox.width, viewBox.height) * MIN_FRAME_SHARE;
  const pad = 1 + 2 * (directive.padding ?? 0.15);
  const w = Math.max(Math.max(...xs) - Math.min(...xs), minSide) * pad;
  const h = Math.max(Math.max(...ys) - Math.min(...ys), minSide) * pad;
  const cx = (Math.max(...xs) + Math.min(...xs)) / 2;
  const cy = (Math.max(...ys) + Math.min(...ys)) / 2;

  const raw = Math.min(viewBox.width / w, viewBox.height / h);
  const k = Math.min(SCALE_EXTENT[1], Math.max(SCALE_EXTENT[0], raw));
  const centerX = viewBox.x + viewBox.width / 2;
  const centerY = viewBox.y + viewBox.height / 2;
  return { k, x: centerX - k * cx, y: centerY - k * cy };
}
