import { useEffect, useState } from 'react';
import { getCatalogDictionary } from '../api/index.js';

const DEPT_META = {
  engineering: { label: 'Engineering', badge: 'badge-eng' },
  planning:    { label: 'Planning',    badge: 'badge-pln' },
  health:      { label: 'Health',      badge: 'badge-hlt' },
  transit:     { label: 'Transit',     badge: 'badge-trt' },
};

const PRIVACY_DESCRIPTIONS = {
  public:       'Freely available to all roles and the public.',
  aggregated:   'Only returned as group-level statistics; individual records suppressed.',
  internal:     'Visible to internal staff with appropriate role; not for public release.',
  restricted:   'Highly sensitive — admin or health role only. Never returned raw.',
};

function PrivacyNote({ level }) {
  const desc = PRIVACY_DESCRIPTIONS[level] || level;
  return (
    <span title={desc}>
      <span className={`badge badge-${level}`}>{level}</span>
    </span>
  );
}

export default function Dictionary() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('shared');

  useEffect(() => {
    getCatalogDictionary()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading">Loading data dictionary…</div>;
  if (error)   return <div className="page"><div className="error-box">Error: {error}</div></div>;

  const sharedFields = data?.shared_fields ?? {};
  const departments = data?.departments ?? {};
  const deptKeys = Object.keys(departments);

  const tabs = [
    { key: 'shared', label: 'Shared Fields' },
    ...deptKeys.map((k) => ({
      key: k,
      label: (DEPT_META[k]?.label ?? k),
      badge: DEPT_META[k]?.badge,
    })),
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h2>Data Dictionary</h2>
        <p>Cross-departmental field definitions, types, and privacy classifications.</p>
      </div>

      <div className="alert alert-info mb-md">
        This dictionary is the authoritative reference for all fields across integrated datasets.
        Privacy classifications determine what each role can access via the RBAC layer.
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
        {tabs.map(({ key, label, badge }) => (
          <button
            key={key}
            className={`btn ${activeTab === key ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => setActiveTab(key)}
            style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
          >
            {badge && activeTab !== key && <span className={`badge ${badge}`} style={{ fontSize: '0.6rem' }}>{label.slice(0,3)}</span>}
            {label}
          </button>
        ))}
      </div>

      {/* Shared fields */}
      {activeTab === 'shared' && (
        <div>
          <div className="section-title mb-sm">Shared Fields (all departments)</div>
          <p className="text-muted text-sm mb-md">
            These fields appear across multiple department datasets and share a common meaning.
            They serve as integration keys when joining data across silos.
          </p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Field Name</th>
                  <th>Type</th>
                  <th>Description</th>
                  <th>Privacy Level</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(sharedFields).map(([name, meta]) => (
                  <tr key={name}>
                    <td><span className="mono" style={{ fontWeight: 600 }}>{name}</span></td>
                    <td><span className="tag mono">{meta.type}</span></td>
                    <td className="text-muted">{meta.description}</td>
                    <td><PrivacyNote level={meta.privacy} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card" style={{ marginTop: '1.5rem' }}>
            <div className="section-title mb-sm">Privacy Level Reference</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.75rem' }}>
              {Object.entries(PRIVACY_DESCRIPTIONS).map(([level, desc]) => (
                <div key={level} style={{ display: 'flex', gap: '0.75rem', alignItems: 'flex-start' }}>
                  <span className={`badge badge-${level}`} style={{ marginTop: '0.1rem', flexShrink: 0 }}>{level}</span>
                  <span className="text-sm text-muted">{desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Department-specific fields */}
      {deptKeys.includes(activeTab) && (() => {
        const dept = departments[activeTab];
        const meta = DEPT_META[activeTab] || { label: activeTab, badge: '' };
        return (
          <div>
            <div className="flex-between mb-md">
              <div>
                <div className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span className={`badge ${meta.badge}`}>{meta.label}</span>
                  Schema
                </div>
                <p className="text-muted text-sm" style={{ marginTop: '0.25rem' }}>
                  Sensitivity: <span className={`badge badge-${dept.sensitivity}`}>{dept.sensitivity}</span>
                </p>
              </div>
            </div>

            <div className="table-wrap mb-lg">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Field Name</th>
                    <th>Integration Key?</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {dept.fields?.map((field, i) => {
                    const isShared = field in sharedFields;
                    const isIntegrationKey = field === 'zone_id';
                    return (
                      <tr key={field}>
                        <td className="text-muted">{i + 1}</td>
                        <td><span className="mono" style={{ fontWeight: 600 }}>{field}</span></td>
                        <td>
                          {isIntegrationKey
                            ? <span className="badge badge-internal">✓ Join Key</span>
                            : <span className="text-muted">—</span>}
                        </td>
                        <td className="text-muted text-sm">
                          {isShared
                            ? <span style={{ color: 'var(--accent)' }}>Defined in shared fields ↑</span>
                            : `${meta.label}-specific field`}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="card">
              <div className="section-title mb-sm">Integration Notes</div>
              <div className="text-sm text-muted" style={{ lineHeight: 1.7 }}>
                <p style={{ marginBottom: '0.5rem' }}>
                  <strong>Join key:</strong> <span className="mono">zone_id</span> — use this to join{' '}
                  {meta.label} data with any other department dataset.
                </p>
                <p style={{ marginBottom: '0.5rem' }}>
                  <strong>Sensitivity:</strong> This dataset is classified as{' '}
                  <span className={`badge badge-${dept.sensitivity}`}>{dept.sensitivity}</span>.
                  {dept.sensitivity === 'confidential' &&
                    ' Only health and admin roles can access the raw fields.'}
                  {dept.sensitivity === 'internal' &&
                    ' Analyst and above roles can access; public role is blocked.'}
                  {dept.sensitivity === 'public' &&
                    ' All roles including analyst can access this data.'}
                </p>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
}
