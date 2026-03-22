import { useState } from 'react';
import { crossQuery } from '../api/index.js';

const ROLES = ['analyst', 'engineer', 'planner', 'health', 'admin'];

const DEPT_META = {
  planning:    { label: 'Building Permits', icon: '🏗️', badge: 'badge-pln' },
  engineering: { label: 'Water Mains',      icon: '🔧', badge: 'badge-eng' },
  transit:     { label: 'Bus Stops',        icon: '🚌', badge: 'badge-trt' },
};

const ACCESS_COLORS = {
  full:        { badge: 'badge-full',        label: 'Full access' },
  read:        { badge: 'badge-read',        label: 'Read (PII stripped)' },
  aggregated:  { badge: 'badge-aggregated',  label: 'Aggregated only' },
  anonymized:  { badge: 'badge-anonymized',  label: 'Anonymized' },
  suppressed:  { badge: 'badge-suppressed',  label: 'Suppressed (<5 records)' },
  none:        { badge: 'badge-none',        label: 'No access' },
};

function AccessBadge({ level }) {
  const meta = ACCESS_COLORS[level] || { badge: 'badge-unknown', label: level };
  return <span className={`badge ${meta.badge}`}>{level}</span>;
}

function DeptCard({ dept, data }) {
  const meta = DEPT_META[dept];
  const access = data?.access_level;
  const count = data?.record_count ?? 0;
  const acMeta = ACCESS_COLORS[access] || {};

  return (
    <div className="card">
      <div className="flex-between mb-sm">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <span style={{ fontSize: '1.5rem' }}>{meta.icon}</span>
          <div>
            <div style={{ fontWeight: 700 }}>{meta.label}</div>
            <span className={`badge ${meta.badge}`} style={{ fontSize: '0.65rem' }}>{dept}</span>
          </div>
        </div>
        {access && <AccessBadge level={access} />}
      </div>

      <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1rem' }}>
        <div>
          <div className="stat-label">Records Returned</div>
          <div className="stat-value" style={{ fontSize: '1.5rem' }}>{count.toLocaleString()}</div>
        </div>
        {access && (
          <div>
            <div className="stat-label">Access Mode</div>
            <div style={{ fontSize: '0.875rem', marginTop: '0.25rem', color: 'var(--text-muted)' }}>
              {acMeta.label || access}
            </div>
          </div>
        )}
      </div>

      {/* Department-specific summaries */}
      {access === 'aggregated' && data.aggregated_groups?.length > 0 && (
        <div>
          <div className="stat-label" style={{ marginBottom: '0.5rem' }}>Aggregated Groups</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  {Object.keys(data.aggregated_groups[0]).map(k => <th key={k}>{k}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.aggregated_groups.slice(0, 10).map((row, i) => (
                  <tr key={i}>
                    {Object.values(row).map((v, j) => (
                      <td key={j}>{v ?? '—'}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {dept === 'planning' && data.top_permit_types?.length > 0 && (
        <div>
          <div className="stat-label" style={{ marginBottom: '0.5rem' }}>Top Permit Types</div>
          {data.top_permit_types.map(({ type, count: c }) => (
            <div key={type} style={{ marginBottom: '0.35rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between',
                fontSize: '0.8rem', marginBottom: '0.1rem' }}>
                <span style={{ color: 'var(--text)' }}>{type}</span>
                <span style={{ color: 'var(--text-muted)' }}>{c.toLocaleString()}</span>
              </div>
              <div style={{ background: 'var(--border)', borderRadius: 4, height: 6 }}>
                <div style={{
                  background: 'var(--pln)',
                  height: 6,
                  borderRadius: 4,
                  width: `${Math.min(100, (c / data.record_count) * 100)}%`,
                }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {dept === 'engineering' && data.pressure_zones != null && (
        <div className="stat-label" style={{ marginTop: '0.5rem' }}>
          {data.pressure_zones} unique pressure zones
        </div>
      )}

      {dept === 'transit' && data.by_municipality && (
        <div>
          <div className="stat-label" style={{ marginBottom: '0.5rem' }}>By Municipality</div>
          {Object.entries(data.by_municipality).map(([m, c]) => (
            <div key={m} style={{ display: 'flex', justifyContent: 'space-between',
              fontSize: '0.8rem', padding: '0.2rem 0', borderBottom: '1px solid var(--border)' }}>
              <span>{m}</span>
              <span style={{ color: 'var(--text-muted)' }}>{c} stops</span>
            </div>
          ))}
        </div>
      )}

      {(access === 'none' || access === 'suppressed') && (
        <div className="alert alert-warn" style={{ margin: 0 }}>
          {access === 'none'
            ? 'Your role does not have access to this department.'
            : 'Results suppressed: too few records returned for this role.'}
        </div>
      )}
    </div>
  );
}

export default function CrossAnalysis() {
  const [role, setRole] = useState('analyst');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const runCross = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await crossQuery({ role, limit: 500 });
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const depts = result?.departments || {};
  const totalRecords = Object.values(depts).reduce((sum, d) => sum + (d.record_count || 0), 0);

  return (
    <div className="page">
      <div className="page-header">
        <h2>Cross-Departmental Analysis</h2>
        <p>
          Query all departments simultaneously with RBAC enforced independently per dataset.
          See how your access level changes across departments based on your role.
        </p>
      </div>

      <div className="card mb-lg">
        <div className="section-title mb-sm">Query Parameters</div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div>
            <div className="stat-label" style={{ marginBottom: '0.3rem' }}>Your Role</div>
            <select className="select" value={role} onChange={e => setRole(e.target.value)}>
              {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <button className="btn btn-primary" onClick={runCross} disabled={loading}>
            {loading ? 'Querying all depts…' : 'Run Cross-Dept Query →'}
          </button>
        </div>

        <div className="alert alert-info" style={{ marginTop: '1rem', marginBottom: 0 }}>
          RBAC is enforced <strong>independently per department</strong> — a planner gets full
          planning access but only aggregated engineering data in the same query.
        </div>
      </div>

      {error && <div className="error-box mb-md">{error}</div>}

      {result && (
        <>
          {/* Summary row */}
          <div className="card-grid card-grid-3 mb-lg">
            <div className="stat-card">
              <div className="stat-label">Total Records Returned</div>
              <div className="stat-value">{totalRecords.toLocaleString()}</div>
              <div className="stat-sub">role: {role}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Departments Queried</div>
              <div className="stat-value">{Object.keys(depts).length}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Access Levels</div>
              <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
                {Object.values(depts).map((d, i) => (
                  <AccessBadge key={i} level={d.access_level} />
                ))}
              </div>
            </div>
          </div>

          {/* Per-dept cards */}
          <div className="section-title mb-sm">Results by Department</div>
          <div className="card-grid card-grid-3 mb-lg">
            {Object.entries(depts).map(([dept, data]) => (
              <DeptCard key={dept} dept={dept} data={data} />
            ))}
          </div>

          {/* Insight panel */}
          <div className="card">
            <div className="section-title mb-sm">Cross-Dept Insights</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div className="alert alert-info" style={{ margin: 0 }}>
                <strong>Infrastructure planning:</strong> To correlate permits with water main locations,
                you need <em>full</em> or <em>read</em> access to both planning and engineering.
                {depts.planning?.access_level === 'full' && depts.engineering?.access_level === 'full'
                  ? ' Your current role has this access.'
                  : ` Your current role (${role}) does not have full read access to both.`}
              </div>
              <div className="alert alert-info" style={{ margin: 0 }}>
                <strong>Transit & development:</strong> Bus stop density vs. permit activity can show
                where new development is outpacing transit coverage. Both datasets are accessible
                at {depts.planning?.access_level} / {depts.transit?.access_level} level for this role.
              </div>
              {result.note && (
                <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{result.note}</div>
              )}
            </div>
          </div>
        </>
      )}

      {!result && !loading && (
        <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>🔗</div>
          <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>
            See all departments in one unified view
          </div>
          <div className="text-sm">Select a role and run the query to see cross-departmental access.</div>
        </div>
      )}
    </div>
  );
}
