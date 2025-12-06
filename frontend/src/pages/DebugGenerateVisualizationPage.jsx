import React, { useState } from 'react';
import axios from 'axios';
import NetworkGraph from '../components/NetworkGraph';

const DebugGenerateVisualizationPage = () => {
    const [requestBody, setRequestBody] = useState(JSON.stringify({
        network_id: 1,
        layout_name: "spring",
        // Example optional params
        // node_size_config: { attribute: "pagerank", min: 5, max: 20 },
        // node_color_config: { attribute: "community", scale_type: "CATEGORICAL" },
        // focus_network_id: null,
        // context_config: null,
        // focus_config: null
    }, null, 2));
    const [response, setResponse] = useState(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleSubmit = async () => {
        setLoading(true);
        setError(null);
        setResponse(null);
        try {
            const body = JSON.parse(requestBody);
            // Call the proxied endpoint
            const res = await axios.post('/nx-api/tools/generate_visualization', body);
            setResponse(res.data);
        } catch (err) {
            console.error(err);
            setError(err.message + (err.response ? ': ' + JSON.stringify(err.response.data) : ''));
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ padding: '20px', height: '100vh', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>
            <h1 style={{ marginBottom: '10px' }}>Debug: Generate Visualization</h1>
            <div style={{ display: 'flex', gap: '20px', flex: 1, minHeight: 0 }}>
                <div style={{ flex: '0 0 400px', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ marginBottom: '5px', fontWeight: 'bold' }}>Request Body (JSON):</div>
                    <textarea
                        style={{ flex: 1, fontFamily: 'monospace', padding: '10px', resize: 'none' }}
                        value={requestBody}
                        onChange={(e) => setRequestBody(e.target.value)}
                    />
                    <button 
                        onClick={handleSubmit} 
                        disabled={loading}
                        style={{ 
                            marginTop: '10px', 
                            padding: '10px', 
                            backgroundColor: loading ? '#ccc' : '#007bff', 
                            color: 'white', 
                            border: 'none', 
                            cursor: loading ? 'default' : 'pointer',
                            borderRadius: '4px'
                        }}
                    >
                        {loading ? 'Sending...' : 'Send Request'}
                    </button>
                    {error && <div style={{ color: 'red', marginTop: '10px', whiteSpace: 'pre-wrap' }}>{error}</div>}
                </div>
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', border: '1px solid #ccc', borderRadius: '4px', overflow: 'hidden' }}>
                    {response && (
                        <>
                            <div style={{ padding: '10px', borderBottom: '1px solid #eee', background: '#f9f9f9', height: '200px', overflow: 'auto' }}>
                                <strong>Response JSON:</strong>
                                <pre style={{ fontSize: '12px', margin: 0 }}>{JSON.stringify(response, null, 2)}</pre>
                            </div>
                            <div style={{ flex: 1, position: 'relative' }}>
                                {/* Check if response has nodes/links to render */}
                                {response.nodes && response.links ? (
                                    <NetworkGraph nodes={response.nodes} links={response.links} />
                                ) : (
                                    <div style={{ padding: '20px', color: '#666' }}>No visualization data (nodes/links) found in response.</div>
                                )}
                            </div>
                        </>
                    )}
                    {!response && !error && (
                        <div style={{ padding: '20px', color: '#999', textAlign: 'center', marginTop: 'auto', marginBottom: 'auto' }}>
                            Visualization will appear here
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default DebugGenerateVisualizationPage;
