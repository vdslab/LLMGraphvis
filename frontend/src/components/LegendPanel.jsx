import { useNetworkStore } from '../stores/networkStore';
import './LegendPanel.css';

const swatchStyle = {
  display: 'inline-block',
  width: '12px',
  height: '12px',
  borderRadius: '4px',
  marginRight: '8px',
  border: '1px solid rgba(0,0,0,0.12)',
  verticalAlign: 'middle',
  flexShrink: 0,
};

const rowStyle = {
  display: 'flex',
  alignItems: 'center',
  fontSize: '0.75rem',
  color: 'var(--md-sys-color-on-surface-variant)',
  marginBottom: '4px',
};

const sectionStyle = {
  marginBottom: '10px',
};

const sectionTitleStyle = {
  fontSize: '0.6875rem',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: 'var(--md-sys-color-outline)',
  marginBottom: '6px',
};

const formatValue = (value) =>
  typeof value === 'number'
    ? Number(value.toPrecision(4)).toLocaleString(undefined, {
        maximumSignificantDigits: 4,
      })
    : value ?? '';

// ADR 0029: a numeric mapping may be log- or rank-scaled, and values beyond an
// explicit range are drawn like its ends.
const scaleNote = (mapping) => (
  mapping.transform === 'log' ? ' (log scale)'
    : mapping.transform === 'rank' ? ' (by rank)' : ''
);
const lowEnd = (mapping, value) =>
  `${mapping.value_min != null ? '≤ ' : ''}${formatValue(value)}`;
const highEnd = (mapping, value) =>
  `${mapping.value_max != null ? '≥ ' : ''}${formatValue(value)}`;

const issueLabels = {
  node_overlap: 'Some nodes overlap',
  outliers_compress_core: 'Outlying nodes squeeze the center',
  clumped: 'Nodes cluster in a small area',
  uneven_edge_lengths: 'Connected nodes have uneven spacing',
  distorted_aspect: 'The layout is stretched',
};

const percent = (value) => typeof value === 'number'
  ? `${Math.round(value * 100)}%` : '—';

const LegendPanel = () => {
  const legend = useNetworkStore((state) => state.legend);
  const quality = useNetworkStore((state) => state.layoutQuality);

  if (!legend || (!legend.node_color && !legend.node_size && !legend.layout)) {
    return null;
  }

  const nodeColor = legend.node_color;
  const nodeSize = legend.node_size;
  const layout = legend.layout;

  return (
    <div
      className="fade-in"
      style={{
        position: 'absolute',
        bottom: '16px',
        left: '16px',
        zIndex: 5,
        backgroundColor: 'rgba(255, 255, 255, 0.94)',
        backdropFilter: 'blur(16px)',
        border: '1px solid var(--md-sys-color-outline-subtle)',
        borderRadius: 'var(--md-sys-shape-lg)',
        padding: '12px 16px',
        boxShadow: 'var(--md-sys-elevation-2)',
        maxWidth: '240px',
        maxHeight: '55vh',
        overflowY: 'auto',
        fontFamily: 'inherit',
      }}
    >
      {nodeColor &&
        nodeColor.type?.toLowerCase() === 'categorical' &&
        nodeColor.mapping && (
          <div style={sectionStyle}>
            <div style={sectionTitleStyle}>Color: {nodeColor.attribute}</div>
            {nodeColor.palette && (
              <div style={{ ...rowStyle, fontSize: '0.6875rem', color: 'var(--md-sys-color-outline)' }}>
                Palette: {nodeColor.palette}
              </div>
            )}
            {Object.entries(nodeColor.mapping).map(([category, color]) => (
              <div key={category} style={rowStyle}>
                <span style={{ ...swatchStyle, backgroundColor: color }} />
                <span style={{ fontWeight: 500, color: 'var(--md-sys-color-on-surface)' }}>
                  {category}
                </span>
              </div>
            ))}
          </div>
        )}

      {nodeColor && nodeColor.type?.toLowerCase() === 'linear' && (
        <div style={sectionStyle}>
          <div style={sectionTitleStyle}>Color: {nodeColor.attribute}{scaleNote(nodeColor)}</div>
          <div
            style={{
              height: '10px',
              borderRadius: 'var(--md-sys-shape-xs)',
              background: `linear-gradient(to right, ${(nodeColor.gradient?.length ? nodeColor.gradient : ['#d3d3d3', '#333333']).join(', ')})`,
              border: '1px solid rgba(0,0,0,0.12)',
            }}
          />
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '0.6875rem',
              color: 'var(--md-sys-color-on-surface-variant)',
              marginTop: '4px',
              fontFamily: 'var(--font-family-code)',
            }}
          >
            <span>{lowEnd(nodeColor, nodeColor.min)}</span>
            <span>{highEnd(nodeColor, nodeColor.max)}</span>
          </div>
        </div>
      )}

      {nodeSize && (
        <div style={sectionStyle}>
          <div style={sectionTitleStyle}>Size: {nodeSize.attribute}{scaleNote(nodeSize)}</div>
          {(nodeSize.data_min !== undefined || nodeSize.data_max !== undefined) && (
            <div style={rowStyle}>
              <span style={{ fontFamily: 'var(--font-family-code)', fontSize: '0.75rem' }}>
                {nodeSize.data_min !== undefined ? lowEnd(nodeSize, nodeSize.data_min) : '?'}
                {' – '}
                {nodeSize.data_max !== undefined ? highEnd(nodeSize, nodeSize.data_max) : '?'}
              </span>
            </div>
          )}
        </div>
      )}

      {layout && (
        <div>
          <div style={sectionTitleStyle}>Layout</div>
          <div
            style={{
              ...rowStyle,
              fontWeight: 600,
              color: 'var(--md-sys-color-primary)',
              fontFamily: 'var(--font-family-brand)',
              fontSize: '0.8125rem',
              marginBottom: 0,
            }}
          >
            {layout}
          </div>
          {quality && (
            <>
              <div style={{ ...rowStyle, marginTop: '6px' }}>
                {quality.issues?.length
                  ? issueLabels[quality.issues[0]] || 'Check the layout details'
                  : 'No major readability issues detected'}
              </div>
              <details className="layout-quality" aria-label="Layout readability details">
                <summary>Readability details</summary>
                {quality.issues?.length > 1 && (
                  <ul>
                    {quality.issues.slice(1).map((issue) => (
                      <li key={issue}>{issueLabels[issue] || issue}</li>
                    ))}
                  </ul>
                )}
                <dl>
                  <dt>Nodes overlapping</dt><dd>{percent(quality.node_overlap)}</dd>
                  <dt>Edge crossings</dt>
                  <dd>{formatValue(quality.crossings)}{quality.crossings_sampled ? ' (estimated)' : ''}</dd>
                  {quality.core_extent != null && (
                    <><dt>Central area used</dt><dd>{percent(quality.core_extent)}</dd></>
                  )}
                  {quality.edge_length_cv != null && (
                    <><dt>Edge length variation</dt><dd>{formatValue(quality.edge_length_cv)}</dd></>
                  )}
                  <dt>Shape stretch</dt><dd>{formatValue(quality.aspect)}×</dd>
                </dl>
                <p>Use these measures to compare layouts of this network.</p>
              </details>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default LegendPanel;
