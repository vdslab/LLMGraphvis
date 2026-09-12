import React from 'react';
import { X, Sparkles, Tag, Info } from 'lucide-react';

const NodeDetailsPanel = ({ selectedNode, onClose, onAskAboutNode }) => {
  if (!selectedNode) return null;

  const { id, label, details } = selectedNode;
  const attributes = details?.attributes || {};
  const description = details?.description;

  return (
    <div
      className="fade-in"
      style={{
        position: 'absolute',
        right: '20px',
        top: '20px',
        width: '320px',
        backgroundColor: 'rgba(255, 255, 255, 0.95)',
        backdropFilter: 'blur(16px)',
        boxShadow: 'var(--md-sys-elevation-3)',
        border: '1px solid var(--md-sys-color-outline-subtle)',
        padding: '20px 22px',
        zIndex: 1000,
        borderRadius: 'var(--md-sys-shape-xl)',
        overflowY: 'auto',
        maxHeight: '80vh',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              borderRadius: 'var(--md-sys-shape-sm)',
              backgroundColor: 'var(--md-sys-color-primary-container)',
              color: 'var(--md-sys-color-on-primary-container)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Tag size={16} />
          </div>
          <h3
            style={{
              margin: 0,
              fontSize: '1.0625rem',
              fontWeight: 700,
              fontFamily: 'var(--font-family-brand)',
              color: 'var(--md-sys-color-on-surface)',
            }}
          >
            Node Details
          </h3>
        </div>
        <button
          onClick={onClose}
          className="btn btn-ghost"
          style={{
            padding: '4px',
            width: '28px',
            height: '28px',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          aria-label="Close details"
        >
          <X size={16} />
        </button>
      </div>

      {/* Node Identifiers */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '6px',
          padding: '12px 14px',
          borderRadius: 'var(--md-sys-shape-md)',
          backgroundColor: 'var(--md-sys-color-surface-container)',
          marginBottom: '16px',
        }}
      >
        <div style={{ fontSize: '0.8125rem', color: 'var(--md-sys-color-on-surface-variant)' }}>
          <span style={{ fontWeight: 600, color: 'var(--md-sys-color-outline)' }}>ID:</span>{' '}
          <code
            style={{
              fontFamily: 'var(--font-family-code)',
              backgroundColor: 'var(--md-sys-color-surface-container-highest)',
              padding: '2px 6px',
              borderRadius: 'var(--md-sys-shape-xs)',
              fontSize: '0.75rem',
            }}
          >
            {id}
          </code>
        </div>
        <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--md-sys-color-on-surface)' }}>
          <span style={{ fontWeight: 600, color: 'var(--md-sys-color-outline)', fontSize: '0.8125rem' }}>Label:</span>{' '}
          {label}
        </div>
      </div>

      {/* Action Button */}
      <div style={{ marginBottom: '16px' }}>
        <button
          onClick={() => {
            if (onAskAboutNode) onAskAboutNode();
          }}
          className="btn btn-primary"
          style={{
            width: '100%',
            padding: '0.625rem 1rem',
            fontSize: '0.875rem',
            boxShadow: 'var(--md-sys-elevation-2)',
          }}
        >
          <Sparkles size={15} />
          <span>Ask about this node</span>
        </button>
      </div>

      {description && (
        <div
          style={{
            marginBottom: '16px',
            padding: '12px',
            backgroundColor: 'var(--md-sys-color-surface-container)',
            borderRadius: 'var(--md-sys-shape-md)',
            borderLeft: '3px solid var(--md-sys-color-primary)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.75rem',
              fontWeight: 700,
              color: 'var(--md-sys-color-outline)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              marginBottom: '4px',
            }}
          >
            <Info size={12} />
            <span>Description</span>
          </div>
          <p
            style={{
              margin: 0,
              fontSize: '0.8125rem',
              color: 'var(--md-sys-color-on-surface)',
              lineHeight: 1.5,
            }}
          >
            {description}
          </p>
        </div>
      )}

      {Object.keys(attributes).length > 0 && (
        <div>
          <div
            style={{
              fontSize: '0.75rem',
              fontWeight: 700,
              color: 'var(--md-sys-color-outline)',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              marginBottom: '8px',
            }}
          >
            Attributes
          </div>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'auto 1fr',
              gap: '6px 12px',
              padding: '10px 12px',
              backgroundColor: 'var(--md-sys-color-surface-container-low)',
              borderRadius: 'var(--md-sys-shape-md)',
              border: '1px solid var(--md-sys-color-outline-subtle)',
            }}
          >
            {Object.entries(attributes).map(([key, value]) => (
              <React.Fragment key={key}>
                <div
                  style={{
                    color: 'var(--md-sys-color-on-surface-variant)',
                    fontSize: '0.75rem',
                    fontWeight: 600,
                  }}
                >
                  {key}:
                </div>
                <div
                  style={{
                    fontSize: '0.75rem',
                    color: 'var(--md-sys-color-on-surface)',
                    fontFamily:
                      typeof value === 'number'
                        ? 'var(--font-family-code)'
                        : 'inherit',
                    wordBreak: 'break-all',
                  }}
                >
                  {String(value)}
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default NodeDetailsPanel;
