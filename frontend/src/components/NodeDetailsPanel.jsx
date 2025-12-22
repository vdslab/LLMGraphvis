import React from 'react';

const NodeDetailsPanel = ({ selectedNode, onClose }) => {
  if (!selectedNode) return null;

  const { id, label, details } = selectedNode;
  const attributes = details?.attributes || {};
  const description = details?.description;

  return (
    <div style={{
      position: 'absolute',
      right: '20px',
      top: '20px',
      width: '300px',
      backgroundColor: 'white',
      boxShadow: '-2px 0 5px rgba(0,0,0,0.1)',
      padding: '20px',
      zIndex: 1000,
      borderRadius: '8px',
      overflowY: 'auto',
      maxHeight: '80vh'
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <h3 style={{ margin: 0, fontSize: '1.2rem' }}>Node Details</h3>
        <button 
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            fontSize: '1.5rem',
            cursor: 'pointer',
            padding: '0',
            lineHeight: '1'
          }}
        >
          ×
        </button>
      </div>

      <div style={{ marginBottom: '15px' }}>
        <strong>ID:</strong> {id} <br />
        <strong>Label:</strong> {label}
      </div>

      {description && (
        <div style={{ marginBottom: '15px', padding: '10px', backgroundColor: '#f5f5f5', borderRadius: '4px' }}>
          <strong>Description:</strong>
          <p style={{ margin: '5px 0 0 0', fontSize: '0.9rem' }}>{description}</p>
        </div>
      )}

      {Object.keys(attributes).length > 0 && (
        <div style={{ marginBottom: '15px' }}>
          <strong>Attributes:</strong>
          <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '8px 15px', marginTop: '10px' }}>
            {Object.entries(attributes).map(([key, value]) => (
              <React.Fragment key={key}>
                <div style={{ color: '#666', fontSize: '0.9rem' }}>{key}:</div>
                <div style={{ fontSize: '0.9rem', wordBreak: 'break-all' }}>{String(value)}</div>
              </React.Fragment>
            ))}
          </div>
        </div>
      )}

      {/* Visual Properties removed as per user request */ }
    </div>
  );
};

export default NodeDetailsPanel;
