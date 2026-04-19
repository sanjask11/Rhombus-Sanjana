import { useEffect, useState } from 'react';
import { getHistory, processFile } from './api/api';
import S3Browser from './components/S3Browser';
import DataPreview from './components/DataPreview';

export default function App() {
  const [bucket, setBucket] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);

  useEffect(() => {
    getHistory()
      .then(({ data }) => setHistory(data.history))
      .catch(() => {});
  }, []);

  async function handleProcess(typeOverrides = {}) {
    if (!bucket || !selectedFile) return;
    setLoading(true);
    setError('');
    try {
      const { data } = await processFile(bucket, selectedFile.key, typeOverrides);
      setResult(data);
      // Refresh history
      getHistory().then(({ data: h }) => setHistory(h.history)).catch(() => {});
    } catch (err) {
      setError(err.response?.data?.error || 'Processing failed. Please try again.');
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  function handleHistorySelect(h) {
    setBucket(h.bucket);
    setSelectedFile({ key: h.file_key, name: h.file_name });
    handleProcess({});
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">
          <span className="logo-icon">◆</span>
          <span>Rhombus AI</span>
        </div>
        <h1>Data Type Inference Engine</h1>
      </header>

      <main className="app-main">
        <aside className="sidebar">
          <S3Browser
            bucket={bucket}
            setBucket={setBucket}
            onFileSelect={(f) => { setSelectedFile(f); setResult(null); setError(''); }}
            selectedFile={selectedFile}
            onProcess={() => handleProcess({})}
            loading={loading}
            history={history}
            onHistorySelect={handleHistorySelect}
          />
        </aside>

        <section className="content">
          {error && <div className="error-banner">{error}</div>}

          {result ? (
            <DataPreview
              result={result}
              onReprocess={handleProcess}
              loading={loading}
            />
          ) : (
            <div className="placeholder">
              <div className="placeholder-icon">◆</div>
              <p>Connect to S3 and select a file to begin</p>
              <p style={{ fontSize: 13 }}>Supports CSV, XLSX, and XLS files</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
