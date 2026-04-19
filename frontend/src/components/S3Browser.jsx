import { useState } from 'react';
import { listS3Files } from '../api/api';

const FILE_ICONS = { csv: '📄', excel: '📊' };

export default function S3Browser({ bucket, setBucket, onFileSelect, selectedFile, onProcess, loading, history, onHistorySelect }) {
  const [localBucket, setLocalBucket] = useState(bucket || '');
  const [files, setFiles] = useState([]);
  const [fetching, setFetching] = useState(false);
  const [error, setError] = useState('');
  const [connected, setConnected] = useState(false);

  async function handleConnect(e) {
    e.preventDefault();
    const b = localBucket.trim();
    if (!b) return;
    setFetching(true);
    setError('');
    try {
      const { data } = await listS3Files(b);
      setFiles(data.files);
      setBucket(b);
      setConnected(true);
      if (data.files.length === 0) setError('No CSV or Excel files found in this bucket.');
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to connect to S3.');
      setConnected(false);
      setFiles([]);
    } finally {
      setFetching(false);
    }
  }

  return (
    <>
      {/* S3 Connection */}
      <div className="sidebar-section">
        <h2>S3 Connection</h2>
        <form onSubmit={handleConnect}>
          <div className="input-row">
            <input
              type="text"
              placeholder="Bucket name"
              value={localBucket}
              onChange={(e) => setLocalBucket(e.target.value)}
              disabled={fetching}
            />
            <button type="submit" className="btn-primary" disabled={fetching || !localBucket.trim()}>
              {fetching ? <><span className="spinner" />…</> : 'Connect'}
            </button>
          </div>
        </form>
        {error && <p style={{ color: 'var(--error)', fontSize: 12, marginTop: 8 }}>{error}</p>}
      </div>

      {/* File list */}
      {connected && files.length > 0 && (
        <div className="sidebar-section" style={{ flex: 1 }}>
          <h2>Files ({files.length})</h2>
          <div className="file-list">
            {files.map((f) => (
              <div
                key={f.key}
                className={`file-item ${selectedFile?.key === f.key ? 'selected' : ''}`}
                onClick={() => onFileSelect(f)}
              >
                <span className="file-icon">{FILE_ICONS[f.file_type] || '📄'}</span>
                <div className="file-info">
                  <div className="file-name" title={f.name}>{f.name}</div>
                  <div className="file-meta">{f.size_display}</div>
                </div>
              </div>
            ))}
          </div>

          {selectedFile && (
            <button
              className="btn-accent"
              style={{ width: '100%', marginTop: 12 }}
              onClick={onProcess}
              disabled={loading}
            >
              {loading ? <><span className="spinner" />Processing…</> : '▶ Process File'}
            </button>
          )}
        </div>
      )}

      {/* History */}
      {history && history.length > 0 && (
        <div className="sidebar-section">
          <h2>Recent</h2>
          <div className="history-list">
            {history.map((h) => (
              <div key={h.id} className="history-item" onClick={() => onHistorySelect(h)}>
                <strong>{h.file_name}</strong>
                {h.bucket} · {h.total_rows.toLocaleString()} rows · {h.column_count} cols
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}
