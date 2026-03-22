import { useEffect, useState, useCallback } from 'react';
import { getSyncStatus, getSyncRuns, triggerSync } from '../api/index.js';

const TABLE_LABELS = {
  building_permits: 'Building Permits',
  water_mains: 'Water Mains',
  bus_stops: 'Bus Stops',
};

function StatusBadge({ status }) {
  const colors = {
    completed: 'badge-full',
    failed: 'badge-none',
    running: 'badge-aggregated',
    pending: 'badge-unknown',
  };
  return <span className={`badge ${colors[status] || 'badge-unknown'}`}>{status}</span>;
}

function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function fmtNum(n) {
  return n?.toLocaleString() ?? '—';
}

export default function SyncStatus() {
  const [status, setStatus] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [triggerResult, setTriggerResult] = useState(null);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([getSyncStatus(), getSyncRuns(20)]);
      setStatus(s);
      setRuns(r.runs || []);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleTrigger = async () => {
    setTriggering(true);
    setTriggerResult(null);
    try {
      const result = await triggerSync([]);
      setTriggerResult({ ok: true, message: result.message || 'Sync triggered successfully.' });
      setTimeout(refresh, 3000);
    } catch (e) {
      setTriggerResult({ ok: false, message: e.message });
    } finally {
      setTriggering(false);
    }
  };

  const datasets = status?.datasets || [];
  const totalRecords = status?.total_records ?? 0;

  return (
    <div className="page">
      <div className="page-header">
        <h2>Sync Status</h2>
        <p>Monitor and trigger data synchronisation from ArcGIS open data sources.</p>
      </div>

      {loading && <div className="loading">Loading sync status…</div>}
      {error && <div className="error-box">{error}</div>}

      {!loading && status && (
        <>
          {/* Stat cards */}
          <div className="card-grid card-grid-3 mb-lg">
            <div className="stat-card">
              <div className="stat-label">Total Records</div>
              <div className="stat-value">{fmtNum(totalRecords)}</div>
              <div className="stat-sub">across all local tables</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Datasets Tracked</div>
              <div className="stat-value">{datasets.length}</div>
              <div className="stat-sub">in local replica</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Last Full Sync</div>
              <div className="stat-value" style={{ fontSize: '1rem', marginTop: '0.25rem' }}>
                {status.last_full_sync ? fmtDate(status.last_full_sync) : 'Never'}
              </div>
            </div>
          </div>

          {/* Per-dataset table */}
          <div className="card mb-lg">
            <div className="section-title mb-sm">Dataset Status</div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Dataset</th>
                    <th>Table</th>
                    <th>Records</th>
                    <th>Last Sync</th>
                  </tr>
                </thead>
                <tbody>
                  {datasets.map((ds) => (
                    <tr key={ds.table_name || ds.dataset_id}>
                      <td style={{ fontWeight: 600 }}>
                        {TABLE_LABELS[ds.table_name] || ds.table_name || ds.dataset_id}
                      </td>
                      <td><code className="mono">{ds.table_name}</code></td>
                      <td>{fmtNum(ds.record_count)}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{fmtDate(ds.last_sync)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Trigger sync */}
          <div className="card mb-lg">
            <div className="section-title mb-sm">Trigger Sync</div>
            <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>
              Pull the latest data from ArcGIS. This runs in the background and may take several minutes.
            </p>
            {triggerResult && (
              <div className={`alert ${triggerResult.ok ? 'alert-info' : 'alert-warn'}`}
                style={{ marginBottom: '1rem' }}>
                {triggerResult.message}
              </div>
            )}
            <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
              <button className="btn btn-primary" onClick={handleTrigger} disabled={triggering}>
                {triggering ? 'Triggering…' : '▶ Trigger Full Sync'}
              </button>
              <button className="btn btn-ghost" onClick={refresh}>↺ Refresh</button>
            </div>
          </div>

          {/* Recent sync runs */}
          <div className="card">
            <div className="section-title mb-sm">Recent Sync Runs</div>
            {runs.length === 0 ? (
              <div className="text-muted text-sm">No sync runs recorded yet.</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Dataset</th>
                      <th>Status</th>
                      <th>Records</th>
                      <th>Started</th>
                      <th>Completed</th>
                      <th>Error</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((run) => (
                      <tr key={run.run_id}>
                        <td style={{ fontWeight: 500 }}>
                          {TABLE_LABELS[run.dataset_id] || run.dataset_id}
                        </td>
                        <td><StatusBadge status={run.status} /></td>
                        <td>{run.records_fetched != null ? fmtNum(run.records_fetched) : '—'}</td>
                        <td style={{ color: 'var(--text-muted)' }}>{fmtDate(run.started_at)}</td>
                        <td style={{ color: 'var(--text-muted)' }}>{fmtDate(run.completed_at)}</td>
                        <td style={{ color: 'var(--restricted)', fontSize: '0.75rem' }}>
                          {run.error_message || ''}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
