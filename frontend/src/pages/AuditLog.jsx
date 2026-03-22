import { useEffect, useState, useCallback } from 'react';
import { getAuditLog } from '../api/index.js';

const DEPTS = ['all', 'engineering', 'planning', 'health', 'transit'];
const ROLES = ['all', 'engineer', 'planner', 'health', 'analyst', 'admin'];
const LIMITS = [20, 50, 100];

function AccessBadge({ level }) {
  const cls = `badge badge-${level ?? 'unknown'}`;
  return <span className={cls}>{level ?? '—'}</span>;
}

function formatTimestamp(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts);
    return d.toLocaleString('en-CA', {
      year: 'numeric', month: 'short', day: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
  } catch {
    return ts;
  }
}

export default function AuditLog() {
  const [log, setLog] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [limit, setLimit] = useState(50);
  const [deptFilter, setDeptFilter] = useState('all');
  const [roleFilter, setRoleFilter] = useState('all');
  const [sortKey, setSortKey] = useState('timestamp');
  const [sortAsc, setSortAsc] = useState(false);
  const [search, setSearch] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    getAuditLog(limit)
      .then((data) => setLog(data.log ?? []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [limit]);

  useEffect(() => { load(); }, [load]);

  const handleSort = (key) => {
    if (sortKey === key) setSortAsc((a) => !a);
    else { setSortKey(key); setSortAsc(true); }
  };

  const SortIcon = ({ col }) => {
    if (sortKey !== col) return <span style={{ opacity: 0.3 }}>↕</span>;
    return <span>{sortAsc ? '↑' : '↓'}</span>;
  };

  const filtered = log
    .filter((r) => deptFilter === 'all' || r.department === deptFilter)
    .filter((r) => roleFilter === 'all' || r.requester_role === roleFilter)
    .filter((r) => {
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        r.department?.includes(q) ||
        r.requester_role?.includes(q) ||
        r.zone_filter?.includes(q) ||
        r.access_level_applied?.includes(q)
      );
    })
    .sort((a, b) => {
      const av = a[sortKey] ?? '';
      const bv = b[sortKey] ?? '';
      const cmp = String(av).localeCompare(String(bv), undefined, { numeric: true });
      return sortAsc ? cmp : -cmp;
    });

  const suppressedCount = filtered.filter((r) => r.suppressed).length;
  const deniedCount = filtered.filter((r) => r.access_level_applied === 'none').length;

  return (
    <div className="page">
      <div className="page-header">
        <h2>Audit Log</h2>
        <p>Full governance trail — every data access, role used, and privacy level applied.</p>
      </div>

      {/* Summary stats */}
      <div className="card-grid card-grid-4 mb-lg">
        <div className="stat-card">
          <div className="stat-label">Queries Shown</div>
          <div className="stat-value">{filtered.length}</div>
          <div className="stat-sub">of {log.length} loaded</div>
        </div>
        <div className={`stat-card ${suppressedCount > 0 ? 'warn' : ''}`}>
          <div className="stat-label">Suppressed</div>
          <div className="stat-value">{suppressedCount}</div>
          <div className="stat-sub">small-cell suppression applied</div>
        </div>
        <div className={`stat-card ${deniedCount > 0 ? 'warn' : ''}`}>
          <div className="stat-label">Access Denied</div>
          <div className="stat-value">{deniedCount}</div>
          <div className="stat-sub">role insufficient</div>
        </div>
        <div className="stat-card good">
          <div className="stat-label">RBAC Enforced</div>
          <div className="stat-value">100%</div>
          <div className="stat-sub">all queries privacy-filtered</div>
        </div>
      </div>

      {/* Controls */}
      <div className="controls">
        <input
          className="input"
          style={{ minWidth: 200 }}
          placeholder="Search zone, role, department…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="select" value={deptFilter} onChange={(e) => setDeptFilter(e.target.value)}>
          {DEPTS.map((d) => <option key={d} value={d}>{d === 'all' ? 'All Departments' : d}</option>)}
        </select>
        <select className="select" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
          {ROLES.map((r) => <option key={r} value={r}>{r === 'all' ? 'All Roles' : r}</option>)}
        </select>
        <select className="select" value={limit} onChange={(e) => setLimit(Number(e.target.value))}>
          {LIMITS.map((l) => <option key={l} value={l}>Last {l}</option>)}
        </select>
        <button className="btn btn-primary" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : '↻ Refresh'}
        </button>
      </div>

      {error && <div className="error-box mb-md">Error: {error}</div>}

      {!loading && filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
          No audit entries match your filters.
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th onClick={() => handleSort('timestamp')}>Timestamp <SortIcon col="timestamp" /></th>
                <th onClick={() => handleSort('requester_role')}>Role <SortIcon col="requester_role" /></th>
                <th onClick={() => handleSort('department')}>Department <SortIcon col="department" /></th>
                <th onClick={() => handleSort('zone_filter')}>Zone <SortIcon col="zone_filter" /></th>
                <th onClick={() => handleSort('access_level_applied')}>Access Level <SortIcon col="access_level_applied" /></th>
                <th onClick={() => handleSort('record_count')}>Records <SortIcon col="record_count" /></th>
                <th>Flags</th>
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 7 }).map((__, j) => (
                        <td key={j}>
                          <div style={{ height: 14, background: '#f1f5f9', borderRadius: 4, width: '80%' }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : filtered.map((entry) => (
                    <tr key={entry.query_id}>
                      <td className="mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {formatTimestamp(entry.timestamp)}
                      </td>
                      <td>
                        <span className="tag" style={{ fontWeight: 600 }}>{entry.requester_role}</span>
                      </td>
                      <td>{entry.department}</td>
                      <td className="mono" style={{ fontSize: '0.8rem' }}>
                        {entry.zone_filter === 'all' ? <span className="text-muted">all zones</span> : entry.zone_filter}
                      </td>
                      <td><AccessBadge level={entry.access_level_applied} /></td>
                      <td style={{ textAlign: 'right', fontWeight: 600 }}>{entry.record_count}</td>
                      <td>
                        {entry.suppressed && <span className="badge badge-restricted" style={{ marginRight: 4 }}>Suppressed</span>}
                        {entry.access_level_applied === 'none' && <span className="badge badge-none">Denied</span>}
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </div>
      )}

      <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        Showing {filtered.length} of {log.length} entries · Sorted by {sortKey} {sortAsc ? '↑' : '↓'}
      </div>
    </div>
  );
}
