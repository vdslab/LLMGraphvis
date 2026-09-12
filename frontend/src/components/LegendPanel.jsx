import { useNetworkStore } from '../stores/networkStore';

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

const LegendPanel = () => {
  const legend = useNetworkStore((state) => state.legend);

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
          <div style={sectionTitleStyle}>Color: {nodeColor.attribute}</div>
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
            <span>{formatValue(nodeColor.min)}</span>
            <span>{formatValue(nodeColor.max)}</span>
          </div>
        </div>
      )}

      {nodeSize && (
        <div style={sectionStyle}>
          <div style={sectionTitleStyle}>Size: {nodeSize.attribute}</div>
          {(nodeSize.data_min !== undefined || nodeSize.data_max !== undefined) && (
            <div style={rowStyle}>
              <span style={{ fontFamily: 'var(--font-family-code)', fontSize: '0.75rem' }}>
                {formatValue(nodeSize.data_min) || '?'}
                {' – '}
                {formatValue(nodeSize.data_max) || '?'}
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
        </div>
      )}
    </div>
  );
};

export default LegendPanel;
