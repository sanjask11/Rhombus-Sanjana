import { useState } from 'react';

const TYPE_OPTIONS = [
  { value: 'text',       label: 'Text' },
  { value: 'integer',    label: 'Integer' },
  { value: 'decimal',    label: 'Decimal' },
  { value: 'boolean',    label: 'Boolean' },
  { value: 'datetime64', label: 'Date/Time' },
  { value: 'timedelta',  label: 'Time Delta' },
  { value: 'category',   label: 'Category' },
  { value: 'complex',    label: 'Complex Number' },
];

const DISPLAY_TO_VALUE = {
  'Text':           'text',
  'Integer':        'integer',
  'Decimal':        'decimal',
  'Boolean':        'boolean',
  'Date/Time':      'datetime64',
  'Time Delta':     'timedelta',
  'Category':       'category',
  'Complex Number': 'complex',
};

function TypeBadge({ displayType }) {
  const cls = 'type-badge type-' + displayType.replace(/\//g, '\\/').replace(/ /g, '\\ ');
  return <span className={cls}>{displayType}</span>;
}

export default function DataPreview({ result, onReprocess, loading }) {
  const { columns, data, total_rows, file_name, preview_rows } = result;

  const [overrides, setOverrides] = useState({});
  const [pendingChanges, setPendingChanges] = useState(false);

  function handleTypeChange(colName, newType) {
    const col = columns.find((c) => c.name === colName);
    const original = DISPLAY_TO_VALUE[col.display_type] || 'text';
    setOverrides((prev) => {
      const next = { ...prev };
      if (newType === original && !result.appliedOverrides?.[colName]) {
        delete next[colName];
      } else {
        next[colName] = newType;
      }
      return next;
    });
    setPendingChanges(true);
  }

  function handleApply() {
    onReprocess(overrides);
    setPendingChanges(false);
  }

  return (
    <div>
      {/* Header */}
      <div className="preview-header">
        <div>
          <div className="preview-title">{file_name}</div>
          <div className="preview-meta">
            {total_rows.toLocaleString()} rows · {columns.length} columns
            {total_rows > preview_rows && ` · showing first ${preview_rows}`}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {pendingChanges && (
            <button className="btn-accent" onClick={handleApply} disabled={loading}>
              {loading ? <><span className="spinner" />Applying…</> : 'Apply Type Changes'}
            </button>
          )}
          <button className="btn-secondary" onClick={() => onReprocess({})} disabled={loading}>
            Reset
          </button>
        </div>
      </div>

      {/* Column cards with type overrides */}
      <div className="column-cards">
        {columns.map((col) => (
          <div key={col.name} className="column-card">
            <div className="column-card-name" title={col.name}>{col.name}</div>
            <TypeBadge displayType={col.display_type} />
            <div className="column-card-stats">
              {col.null_count > 0 && <span>{col.null_count} nulls · </span>}
              <span>{col.unique_count} unique</span>
            </div>
            <select
              value={overrides[col.name] || DISPLAY_TO_VALUE[col.display_type] || 'text'}
              onChange={(e) => handleTypeChange(col.name, e.target.value)}
            >
              {TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
        ))}
      </div>

      {/* Data table */}
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.name} title={`${col.dtype}`}>{col.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.length === 0 ? (
              <tr><td colSpan={columns.length} style={{ textAlign: 'center', padding: 24, color: 'var(--text-muted)' }}>No data</td></tr>
            ) : (
              data.map((row, i) => (
                <tr key={i}>
                  {columns.map((col) => {
                    const val = row[col.name];
                    return (
                      <td key={col.name} className={val === null || val === undefined ? 'null-cell' : ''}>
                        {val === null || val === undefined ? 'null' : String(val)}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
