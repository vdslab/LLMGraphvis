import { useNetworkStore } from '../stores/networkStore';

const swatchStyle = {
  display: 'inline-block',
  width: '10px',
  height: '10px',
  borderRadius: '3px',
  marginRight: '6px',
  border: '1px solid rgba(0,0,0,0.15)',
  verticalAlign: 'middle'
};

const rowStyle = {
  display: 'flex',
  alignItems: 'center',
  fontSize: '12px',
  color: 'var(--text-secondary)',
  marginBottom: '2px'
};

const sectionStyle = {
  marginBottom: '8px'
};

const sectionTitleStyle = {
  fontSize: '11px',
  fontWeight: 700,
  textTransform: 'uppercase',
  letterSpacing: '0.02em',
  color: 'var(--text-secondary)',
  marginBottom: '4px'
};

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
      style={{
        position: 'absolute',
        bottom: '10px',
        left: '10px',
        zIndex: 5,
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        border: '1px solid var(--border-color)',
        borderRadius: '8px',
        padding: '10px 12px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        maxWidth: '220px',
        fontFamily: 'inherit'
      }}
    >
      {nodeColor && (nodeColor.type?.toLowerCase() === 'categorical') && nodeColor.mapping && (
        <div style={sectionStyle}>
          <div style={sectionTitleStyle}>Color: {nodeColor.attribute}</div>
          {Object.entries(nodeColor.mapping).map(([category, color]) => (
            <div key={category} style={rowStyle}>
              <span style={{ ...swatchStyle, backgroundColor: color }} />
              <span>{category}</span>
            </div>
          ))}
        </div>
      )}

      {nodeColor && (nodeColor.type?.toLowerCase() === 'linear') && (
        <div style={sectionStyle}>
          <div style={sectionTitleStyle}>Color: {nodeColor.attribute}</div>
          <div
            style={{
              height: '10px',
              borderRadius: '4px',
              background: `linear-gradient(to right, ${(nodeColor.gradient && nodeColor.gradient[0]) || '#d3d3d3'}, ${(nodeColor.gradient && nodeColor.gradient[1]) || '#333333'})`,
              border: '1px solid rgba(0,0,0,0.15)'
            }}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px' }}>
            <span>{nodeColor.min !== undefined && nodeColor.min !== null ? nodeColor.min : ''}</span>
            <span>{nodeColor.max !== undefined && nodeColor.max !== null ? nodeColor.max : ''}</span>
          </div>
        </div>
      )}

      {nodeSize && (
        <div style={sectionStyle}>
          <div style={sectionTitleStyle}>Size: {nodeSize.attribute}</div>
          {(nodeSize.data_min !== undefined || nodeSize.data_max !== undefined) && (
            <div style={rowStyle}>
              <span>
                {nodeSize.data_min !== undefined && nodeSize.data_min !== null ? nodeSize.data_min : '?'}
                {' – '}
                {nodeSize.data_max !== undefined && nodeSize.data_max !== null ? nodeSize.data_max : '?'}
              </span>
            </div>
          )}
        </div>
      )}

      {layout && (
        <div>
          <div style={sectionTitleStyle}>Layout</div>
          <div style={rowStyle}>{layout}</div>
        </div>
      )}
    </div>
  );
};

export default LegendPanel;
