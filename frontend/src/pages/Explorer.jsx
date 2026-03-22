import { useEffect, useState } from 'react';
import { getCatalog, queryDepartment, getReplicaPermits, getReplicaWaterMains, getReplicaBusStops, getReplicaStats } from '../api/index.js';

const ROLES = ['analyst', 'engineer', 'planner', 'health', 'admin'];
const CITIES = [
  { value: '', label: 'All Cities' },
  { value: 'kitchener', label: 'Kitchener' },
  { value: 'waterloo_city', label: 'Waterloo' },
];

const DEPT_META = {
  engineering: { label: 'Engineering', badge: 'badge-eng' },
  planning:    { label: 'Planning',    badge: 'badge-pln' },
  transit:     { label: 'Transit',     badge: 'badge-trt' },
};

const SOURCE_LABELS = {
  kitchener: 'Kitchener',
  waterloo_city: 'Waterloo',
};

// Filter options derived from real data
const FILTER_OPTIONS = {
  planning: {
    permit_type: [
      '', 'Residential Building (House)', 'Residential Accessory (1 or 2 units)',
      'Residential Alteration', 'Residential Building (Multi)', 'Non-Residential Alteration',
      'Plumbing', 'Permanent Sign Permits', 'Residential Garage/Carport (1 or 2 units)',
    ],
    permit_status: ['', 'Issued', 'Closed', 'Cancelled', 'Occupancy Permitted', 'Ready to Final', 'Violation'],
    work_type: [
      '', 'New Construction', 'Alterations/Improvements', 'Interior Finish',
      'Addition to Building', 'Site Services', 'Exterior Alteration',
      'Installation of Pre-Fabricated Building', 'Interior Alteration',
    ],
    issue_year: ['', ...Array.from({ length: 30 }, (_, i) => String(2025 - i))],
  },
  engineering: {
    pressure_zone: [
      '', 'KIT 2E', 'KIT 2EA', 'KIT 2W', 'KIT 4', 'KIT 4A', 'KIT 5', 'KIT 6',
      'BRIDGEPORT', 'BRESLAU', 'BRESLAU NORTH', 'BRESLAU SOUTH', 'MANNHEIM', 'CAM 1', 'CAM 2W',
    ],
    material: ['', 'PVC', 'PVCO', 'PVCB', 'PVCF', 'DI', 'CI', 'AC', 'HDPE', 'HDPE IN CI', 'CPP', 'COP', 'ST'],
    status: ['', 'ACTIVE', 'ABANDONED', 'INACTIVE'],
  },
  transit: {
    municipality: ['', 'Kitchener', 'Waterloo', 'Cambridge'],
    status: ['', 'Active', 'Inactive'],
    ixpress: ['', 'Y', 'N'],
  },
};

const FILTER_LABELS = {
  permit_type: 'Permit Type', permit_status: 'Status', work_type: 'Work Type',
  issue_year: 'Issue Year', pressure_zone: 'Pressure Zone', material: 'Material',
  status: 'Status', municipality: 'Municipality', ixpress: 'iXpress Only',
};

function ResultTable({ rows }) {
  const [page, setPage] = useState(0);
  const pageSize = 50;
  if (!rows || rows.length === 0) return <div className="text-muted text-sm" style={{ padding: '0.75rem 0' }}>No records returned.</div>;

  const headers = Object.keys(rows[0]);
  const total = rows.length;
  const paged = rows.slice(page * pageSize, (page + 1) * pageSize);
  const pages = Math.ceil(total / pageSize);

  return (
    <div>
      <div style={{ marginTop: '0.75rem', maxHeight: '400px', overflowY: 'auto', overflowX: 'auto', border: '1px solid var(--border)', borderRadius: '4px' }}>
        <table style={{ minWidth: 'max-content', fontSize: '0.75rem', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              {headers.map((h) => (
                <th key={h} style={{ position: 'sticky', top: 0, background: '#f8fafc', padding: '0.5rem 0.75rem', textAlign: 'left', borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap', fontWeight: 600, fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map((row, i) => (
              <tr key={i} style={{ borderBottom: '1px solid #f1f5f9' }}>
                {headers.map((h) => (
                  <td key={h} title={String(row[h] ?? '')} style={{ padding: '0.4rem 0.75rem', whiteSpace: 'nowrap' }}>
                    {row[h] !== null && row[h] !== undefined
                      ? String(row[h])
                      : <span className="text-muted">—</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          <button className="btn btn-ghost" style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem' }} onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>←</button>
          <span>Page {page + 1} of {pages} ({total} records)</span>
          <button className="btn btn-ghost" style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem' }} onClick={() => setPage(p => Math.min(pages - 1, p + 1))} disabled={page >= pages - 1}>→</button>
        </div>
      )}
    </div>
  );
}

function ResultCard({ dataset, result, loading, error, role, filters, cityFilter }) {
  const meta = DEPT_META[dataset.department] || { label: dataset.department, badge: '' };
  const access = result?.access_level;

  // Get sources from the actual data rows
  const sources = result?.rows?.length > 0
    ? [...new Set(result.rows.map(r => r.source_id).filter(Boolean))]
    : [];
  const sourceLabel = sources.length === 1
    ? SOURCE_LABELS[sources[0]] || sources[0]
    : sources.length > 1
      ? 'Multiple Cities'
      : cityFilter ? SOURCE_LABELS[cityFilter] : 'All Cities';

  const filterStr = Object.entries(filters || {}).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join('&');
  const downloadUrl = `/download/${dataset.department}?role=${role}${filterStr ? '&' + filterStr : ''}`;

  return (
    <div className="card">
      <div className="flex-between mb-sm">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className={`badge ${meta.badge}`}>{meta.label}</span>
          <span style={{ fontWeight: 700 }}>{dataset.name}</span>
        </div>
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          {sources.length > 0 && sources.map(s => (
            <span key={s} className={`badge ${s === 'kitchener' ? 'badge-kitchener' : 'badge-waterloo'}`} style={{ fontSize: '0.65rem', padding: '0.15rem 0.4rem' }}>
              {SOURCE_LABELS[s] || s}
            </span>
          ))}
          {access && <span className={`badge badge-${access}`}>{access}</span>}
        </div>
      </div>

      {loading && <div className="text-muted text-sm">Querying…</div>}
      {error && <div className="error-box" style={{ fontSize: '0.8rem' }}>{error}</div>}

      {result && !loading && (
        <>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
            {result.rows?.length ?? 0} records returned · access: <strong>{access}</strong>
            {result.note && <span> · {result.note}</span>}
          </div>

          {access !== 'none' && access !== 'suppressed'
            ? <ResultTable rows={result.rows} />
            : <div className="alert alert-warn" style={{ marginTop: '0.5rem' }}>{result.note ?? `Access ${access}`}</div>}

          {access !== 'none' && (
            <div style={{ marginTop: '0.75rem', display: 'flex', gap: '0.5rem' }}>
              <a href={`${downloadUrl}&fmt=csv`} className="btn btn-ghost" style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }} download>↓ CSV</a>
              <a href={`${downloadUrl}&fmt=json`} className="btn btn-ghost" style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }} download>↓ JSON</a>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function Explorer() {
  const [catalog, setCatalog] = useState(null);
  const [role, setRole] = useState('analyst');
  const [deptFilter, setDeptFilter] = useState('all');
  const [cityFilter, setCityFilter] = useState('');
  const [filters, setFilters] = useState({});
  const [limit, setLimit] = useState(200);
  const [results, setResults] = useState({});
  const [loadingMap, setLoadingMap] = useState({});
  const [errorMap, setErrorMap] = useState({});
  const [queried, setQueried] = useState(false);
  const [replicaStats, setReplicaStats] = useState(null);

  useEffect(() => { getCatalog().then(setCatalog).catch(console.error); }, []);
  useEffect(() => { getReplicaStats().then(setReplicaStats).catch(console.error); }, []);

  const datasets = (catalog?.datasets ?? []).filter(d => d.department in DEPT_META);
  const visible = deptFilter === 'all' ? datasets : datasets.filter(d => d.department === deptFilter);

  const depts = ['all', ...new Set(datasets.map(d => d.department))];

  const activeFilterOptions = FILTER_OPTIONS[deptFilter] || {};

  const setFilter = (key, val) => setFilters(prev => ({ ...prev, [key]: val }));

  const runQuery = async () => {
    setQueried(true);
    const newLoading = {};
    visible.forEach(d => { newLoading[d.dataset_id] = true; });
    setLoadingMap(newLoading);
    setResults({});
    setErrorMap({});

    await Promise.all(visible.map(async (ds) => {
      try {
        // Add source_id (city filter) to the filters
        const queryFilters = { ...filters };
        if (cityFilter) {
          queryFilters.source_id = cityFilter;
        }
        const result = await queryDepartment({ department: ds.department, role, filters: queryFilters, limit });
        setResults(prev => ({ ...prev, [ds.dataset_id]: result }));
      } catch (e) {
        setErrorMap(prev => ({ ...prev, [ds.dataset_id]: e.message }));
      } finally {
        setLoadingMap(prev => ({ ...prev, [ds.dataset_id]: false }));
      }
    }));
  };

  return (
    <div className="page">
      <div className="page-header">
        <h2>Dataset Explorer</h2>
        <p>Query real open data across all integrated departments with RBAC privacy enforcement.</p>
      </div>

      <div className="card mb-lg">
        <div className="section-title mb-sm">Query Parameters</div>

        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <div>
            <div className="stat-label" style={{ marginBottom: '0.3rem' }}>Your Role</div>
            <select className="select" value={role} onChange={e => setRole(e.target.value)}>
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <div className="stat-label" style={{ marginBottom: '0.3rem' }}>Department</div>
            <select className="select" value={deptFilter} onChange={e => { setDeptFilter(e.target.value); setFilters({}); }}>
              {depts.map(d => <option key={d} value={d}>{d === 'all' ? 'All Departments' : d}</option>)}
            </select>
          </div>
          <div>
            <div className="stat-label" style={{ marginBottom: '0.3rem' }}>City</div>
            <select className="select" value={cityFilter} onChange={e => setCityFilter(e.target.value)}>
              {CITIES.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
          </div>
          <div>
            <div className="stat-label" style={{ marginBottom: '0.3rem' }}>Row Limit</div>
            <select className="select" value={limit} onChange={e => setLimit(Number(e.target.value))}>
              {[50, 100, 200, 500, 1000, 2000, 5000].map(l => <option key={l} value={l}>{l} rows</option>)}
            </select>
          </div>
        </div>

        {/* Dynamic filters based on selected department */}
        {deptFilter !== 'all' && Object.keys(activeFilterOptions).length > 0 && (
          <div>
            <div className="stat-label" style={{ marginBottom: '0.5rem' }}>Filters <span className="text-muted" style={{ fontWeight: 400, textTransform: 'none', fontSize: '0.75rem' }}>(optional)</span></div>
            <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
              {Object.entries(activeFilterOptions).map(([key, options]) => (
                <div key={key}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem', fontWeight: 600 }}>
                    {FILTER_LABELS[key] || key}
                  </div>
                  <select
                    className="select"
                    style={{ minWidth: 160 }}
                    value={filters[key] || ''}
                    onChange={e => setFilter(key, e.target.value)}
                  >
                    {options.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
                  </select>
                </div>
              ))}
            </div>
          </div>
        )}

        <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button className="btn btn-primary" onClick={runQuery}>Run Query →</button>
          {queried && <span className="text-muted text-sm">Showing {visible.length} dataset{visible.length !== 1 ? 's' : ''}</span>}
        </div>

        {role === 'health' && (deptFilter === 'all' || deptFilter === 'engineering') && (
          <div className="alert alert-info" style={{ marginTop: '0.75rem', marginBottom: 0 }}>
            Health role gets aggregated-only access to Engineering data by RBAC design.
          </div>
        )}
      </div>

      {queried && (
        <div>
          <div className="section-title mb-sm">
            Results — role: <strong>{role}</strong>
            {cityFilter && <span style={{ marginLeft: '0.5rem' }}> · City: <strong>{SOURCE_LABELS[cityFilter]}</strong></span>}
            {Object.entries(filters).filter(([,v]) => v).map(([k, v]) => (
              <span key={k} style={{ marginLeft: '0.5rem' }}> · {FILTER_LABELS[k] || k}: <strong>{v}</strong></span>
            ))}
          </div>
          <div className="card-grid card-grid-2">
            {visible.map(ds => (
              <ResultCard
                key={ds.dataset_id}
                dataset={ds}
                result={results[ds.dataset_id]}
                loading={loadingMap[ds.dataset_id]}
                error={errorMap[ds.dataset_id]}
                role={role}
                filters={filters}
                cityFilter={cityFilter}
              />
            ))}
          </div>
        </div>
      )}

      {!queried && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>🗂️</div>
          <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>
            {replicaStats?.tables
              ? `${replicaStats.tables.building_permits?.toLocaleString() || 0} permits · ${replicaStats.tables.water_mains?.toLocaleString() || 0} water mains · ${replicaStats.tables.bus_stops?.toLocaleString() || 0} bus stops`
              : 'Loading stats...'}
          </div>
          <div className="text-sm" style={{ marginBottom: '0.5rem' }}>Real open data from City of Kitchener and City of Waterloo. Select parameters and run a query.</div>
          {replicaStats?.by_source && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: '1.5rem', marginTop: '0.75rem', fontSize: '0.75rem' }}>
              <span><strong>Kitchener:</strong> {(replicaStats.by_source.building_permits?.kitchener || 0).toLocaleString()} permits, {(replicaStats.by_source.water_mains?.kitchener || 0).toLocaleString()} mains</span>
              <span><strong>Waterloo:</strong> {(replicaStats.by_source.building_permits?.waterloo_city || 0).toLocaleString()} permits, {(replicaStats.by_source.water_mains?.waterloo_city || 0).toLocaleString()} mains</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
