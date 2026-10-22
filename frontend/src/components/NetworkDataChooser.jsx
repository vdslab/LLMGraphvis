import { ExternalLink, Network, Upload } from 'lucide-react';
import './NetworkDataChooser.css';

const NetworkDataChooser = ({
  samples,
  catalogStatus,
  catalogError,
  busy,
  loadingSampleId,
  onUpload,
  onSelectSample,
  fileInputRef,
}) => (
  <section className="network-chooser" aria-labelledby="network-chooser-title">
    <div className="network-chooser__intro">
      <div className="network-chooser__icon" aria-hidden>
        <Network size={24} />
      </div>
      <div>
        <h2 id="network-chooser-title">Choose a network to explore</h2>
        <p>Upload your own GraphML data, or start instantly with a classic network.</p>
      </div>
    </div>

    <input
      ref={fileInputRef}
      className="network-chooser__file-input"
      type="file"
      accept=".graphml,.xml"
      onChange={onUpload}
      tabIndex={-1}
    />
    <button
      type="button"
      className="btn btn-primary network-chooser__upload"
      onClick={() => fileInputRef.current?.click()}
      disabled={busy}
    >
      <Upload size={17} aria-hidden />
      {busy && !loadingSampleId ? 'Importing GraphML…' : 'Upload GraphML'}
    </button>

    <div className="network-chooser__divider" aria-hidden>
      <span>or try a sample</span>
    </div>

    {catalogStatus === 'loading' && (
      <p className="network-chooser__status" role="status">
        Loading sample networks…
      </p>
    )}

    {catalogStatus === 'error' && (
      <p className="network-chooser__status network-chooser__status--error" role="alert">
        {catalogError || 'Sample networks could not be loaded.'}
      </p>
    )}

    {samples.length > 0 && (
      <div className="network-chooser__samples">
        {samples.map((sample) => {
          const isLoading = loadingSampleId === sample.id;
          return (
            <article className="network-chooser__sample" key={sample.id}>
              <button
                type="button"
                className="network-chooser__sample-button"
                onClick={() => onSelectSample(sample.id)}
                disabled={busy}
                aria-label={`Load ${sample.name} sample network`}
              >
                <span className="network-chooser__sample-name">
                  {isLoading ? `Loading ${sample.name}…` : sample.name}
                </span>
                <span className="network-chooser__sample-description">
                  {sample.description}
                </span>
                <span className="network-chooser__sample-stats">
                  <span>{sample.node_count} nodes</span>
                  <span>{sample.edge_count} edges</span>
                </span>
              </button>
              <a
                className="network-chooser__source"
                href={sample.source_url}
                target="_blank"
                rel="noreferrer"
                aria-label={`Open the source for ${sample.name}`}
              >
                Dataset source <ExternalLink size={12} aria-hidden />
              </a>
            </article>
          );
        })}
      </div>
    )}
  </section>
);

export default NetworkDataChooser;
