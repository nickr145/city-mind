import { useEffect, useState } from 'react';
import { getCatalog, getCatalogQuality } from '../api/index.js';

const DEPT_LABELS = {
  engineering: { label: 'Engineering', className: 'badge-eng' },
  planning:    { label: 'Planning',    className: 'badge-pln' },
  health:      { label: 'Health',      className: 'badge-hlt' },
  transit:     { label: 'Transit',     className: 'badge-trt' },
};

const SENSITIVITY_ORDER = ['public', 'internal', 'confidential', 'restricted'];

function SensitivityBar({ datasets }) {
  const counts = SENSITIVITY_ORDER.map((s) => ({
    label: s,
    count: datasets.filter((d) => d.sensitivity === s).length,
  }));
  const total = datasets.length || 1;

  return (
    <div>
      <div style={{ display: 'flex', height: 8, borderRadius: 999, overflow: 'hidden', gap: 2 }}>
        {counts.map(({ label, count }) =>
          count > 0 ? (
            <div
              key={label}
              style={{
                flex: count / total,
                background: `var(--${label})`,
                borderRadius: 999,
              }}
              title={`${label}: ${count}`}
            />
          ) : null
        )}
      </div>
      <div style={{ display: 'flex', gap: '0.75rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
        {counts.map(({ label, count }) => (
          <span key={label} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: `var(--${label})`, display: 'inline-block' }} />
            {label} ({count})
          </span>
        ))}
      </div>
    </div>
  );
}

function DatasetCard({ dataset, isStale }) {
  const dept = DEPT_LABELS[dataset.department] || { label: dataset.department, className: '' };
  const since = dataset.last_updated
    ? Math.floor((Date.now() - new Date(dataset.last_updated)) / 86400000)
    : null;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      <div className="flex-between">
        <span className={`badge ${dept.className}`}>{dept.label}</span>
        <span className={`badge ${isStale ? 'badge-stale' : 'badge-fresh'}`}>
          {isStale ? '⚠ Stale' : '✓ Fresh'}
        </span>
      </div>

      <div>
        <div style={{ fontWeight: 700, fontSize: '0.9375rem', marginBottom: '0.2rem' }}>
          {dataset.name}
        </div>
        <div className="text-muted text-sm">{dataset.description}</div>
      </div>

      <div style={{ display: 'flex', gap: '1.5rem' }}>
        <div>
          <div className="stat-label" style={{ marginBottom: '0.15rem' }}>Records</div>
          <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>{dataset.record_count ?? '—'}</div>
        </div>
        <div>
          <div className="stat-label" style={{ marginBottom: '0.15rem' }}>Last Updated</div>
          <div style={{ fontWeight: 600, fontSize: '0.875rem', color: isStale ? 'var(--confidential)' : 'var(--text)' }}>
            {dataset.last_updated ?? 'Unknown'}
            {since !== null && <span className="text-muted" style={{ fontWeight: 400, marginLeft: 4 }}>({since}d ago)</span>}
          </div>
        </div>
        <div>
          <div className="stat-label" style={{ marginBottom: '0.15rem' }}>Sensitivity</div>
          <span className={`badge badge-${dataset.sensitivity}`}>{dataset.sensitivity}</span>
        </div>
      </div>

      <div>
        <div className="stat-label" style={{ marginBottom: '0.3rem' }}>Fields</div>
        <div className="tags">
          {dataset.fields?.map((f) => (
            <span key={f} className="tag mono">{f}</span>
          ))}
        </div>
      </div>

      <div>
        <div className="stat-label" style={{ marginBottom: '0.3rem' }}>Tags</div>
        <div className="tags">
          {dataset.tags?.map((t) => (
            <span key={t} className="tag">{t}</span>
          ))}
        </div>
      </div>

      <div style={{ paddingTop: '0.5rem', borderTop: '1px solid var(--border)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        Steward: <strong>{dataset.steward ?? '—'}</strong>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [catalog, setCatalog] = useState(null);
  const [quality, setQuality] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([getCatalog(), getCatalogQuality()])
      .then(([cat, qual]) => {
        setCatalog(cat);
        setQuality(qual);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Loading data quality report…</div>;
  if (error)   return <div className="page"><div className="error-box">Error: {error}</div></div>;

  const datasets = catalog?.datasets ?? [];
  const staleIds = new Set((quality?.stale_datasets ?? []).map((s) => s.dataset_id));
  const totalRecords = datasets.reduce((sum, d) => sum + (d.record_count ?? 0), 0);
  const deptCount = new Set(datasets.map((d) => d.department)).size;
  const staleCount = staleIds.size;

  return (
    <div className="page">
      <div className="page-header">
        <h2>Data Quality Dashboard</h2>
        <p>Health and freshness overview for all integrated department datasets.</p>
      </div>

      {/* Summary stats */}
      <div className="card-grid card-grid-4 mb-lg">
        <div className="stat-card">
          <div className="stat-label">Total Datasets</div>
          <div className="stat-value">{datasets.length}</div>
          <div className="stat-sub">across {deptCount} departments</div>
        </div>
        <div className={`stat-card ${staleCount > 0 ? 'warn' : 'good'}`}>
          <div className="stat-label">Stale Datasets</div>
          <div className="stat-value">{staleCount}</div>
          <div className="stat-sub">not updated in 90+ days</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Records</div>
          <div className="stat-value">{totalRecords.toLocaleString()}</div>
          <div className="stat-sub">across all departments</div>
        </div>
        <div className="stat-card good">
          <div className="stat-label">Departments Integrated</div>
          <div className="stat-value">{deptCount}</div>
          <div className="stat-sub">federated data sources</div>
        </div>
      </div>

      {/* Sensitivity distribution */}
      <div className="card mb-lg">
        <div className="section-title" style={{ marginBottom: '0.75rem' }}>Sensitivity Distribution</div>
        <SensitivityBar datasets={datasets} />
      </div>

      {/* Stale alert */}
      {staleCount > 0 && (
        <div className="alert alert-warn mb-md">
          ⚠ <strong>{staleCount} dataset{staleCount > 1 ? 's' : ''}</strong> not updated in 90+ days. Contact the listed data steward to refresh.
        </div>
      )}

      {/* Dataset cards */}
      <div className="section-title mb-sm">Dataset Health</div>
      <div className="card-grid card-grid-2">
        {datasets.map((ds) => (
          <DatasetCard key={ds.dataset_id} dataset={ds} isStale={staleIds.has(ds.dataset_id)} />
        ))}
      </div>
    </div>
  );
}
