import { useEffect, useState } from 'react';
import { queryDepartment } from '../api/index.js';

// Plain-language labels for column names
const FIELD_LABELS = {
  permit_no:          'Permit Number',
  permit_type:        'Permit Type',
  permit_status:      'Status',
  work_type:          'Work Type',
  sub_work_type:      'Sub-type',
  application_date:   'Application Date',
  issue_date:         'Issue Date',
  issue_year:         'Year',
  construction_value: 'Est. Value ($)',
  permit_description: 'Description',
  folder_name:        'File Name',
  stop_id:            'Stop ID',
  street:             'Street',
  crossstreet:        'Cross Street',
  municipality:       'City',
  ixpress:            'iXpress Route',
  status:             'Status',
};

const DEPT_INFO = {
  planning: {
    label: 'Building Permits',
    icon: '🏗️',
    description: 'Search active and historical building permits across Kitchener.',
    badge: 'badge-pln',
    filters: [
      { key: 'permit_type', label: 'Permit Type', options: [
        '', 'Residential Building (House)', 'Residential Accessory (1 or 2 units)',
        'Residential Alteration', 'Residential Building (Multi)', 'Non-Residential Alteration',
        'Plumbing', 'Permanent Sign Permits',
      ]},
      { key: 'permit_status', label: 'Status', options: ['', 'Issued', 'Closed', 'Cancelled'] },
      { key: 'issue_year', label: 'Year', options: ['', ...Array.from({ length: 10 }, (_, i) => String(2025 - i))] },
    ],
  },
  transit: {
    label: 'Bus Stops',
    icon: '🚌',
    description: 'Find bus stop locations across Kitchener, Waterloo, and Cambridge.',
    badge: 'badge-trt',
    filters: [
      { key: 'municipality', label: 'City', options: ['', 'Kitchener', 'Waterloo', 'Cambridge'] },
      { key: 'ixpress', label: 'iXpress Only', options: ['', 'Y'] },
    ],
  },
};

// Fields to show publicly (exclude PII — already stripped server-side, but also limit columns shown)
const VISIBLE_FIELDS = {
  planning: ['permit_no', 'permit_type', 'permit_status', 'work_type', 'issue_year', 'construction_value', 'permit_description'],
  transit:  ['stop_id', 'street', 'crossstreet', 'municipality', 'ixpress', 'status'],
};

function fmtValue(key, val) {
  if (val === null || val === undefined || val === '') return '—';
  if (key === 'construction_value' && typeof val === 'number') {
    return `$${val.toLocaleString()}`;
  }
  if (key === 'ixpress') return val === 'Y' ? 'Yes' : 'No';
  return String(val);
}

function DataTable({ dept, rows }) {
  const [page, setPage] = useState(0);
  const pageSize = 20;
  const visibleFields = VISIBLE_FIELDS[dept] || [];
  const cols = visibleFields.filter(f => rows.some(r => f in r));
  const paged = rows.slice(page * pageSize, (page + 1) * pageSize);
  const pages = Math.ceil(rows.length / pageSize);

  return (
    <div>
      <div className="table-wrap" style={{ maxHeight: 400, overflowY: 'auto' }}>
        <table>
          <thead>
            <tr>
              {cols.map(f => <th key={f} style={{ position: 'sticky', top: 0 }}>{FIELD_LABELS[f] || f}</th>)}
            </tr>
          </thead>
          <tbody>
            {paged.map((row, i) => (
              <tr key={i}>
                {cols.map(f => (
                  <td key={f}>{fmtValue(f, row[f])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem',
          fontSize: '0.8rem', color: 'var(--text-muted)' }}>
          <button className="btn btn-ghost" style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem' }}
            onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>←</button>
          <span>Page {page + 1} of {pages} ({rows.length.toLocaleString()} records)</span>
          <button className="btn btn-ghost" style={{ padding: '0.2rem 0.6rem', fontSize: '0.75rem' }}
            onClick={() => setPage(p => Math.min(pages - 1, p + 1))} disabled={page >= pages - 1}>→</button>
        </div>
      )}
    </div>
  );
}

function DeptPanel({ deptKey }) {
  const info = DEPT_INFO[deptKey];
  const [filters, setFilters] = useState({});
  const [rows, setRows] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const setFilter = (key, val) => setFilters(prev => ({ ...prev, [key]: val }));

  const search = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await queryDepartment({
        department: deptKey,
        role: 'analyst',
        filters,
        limit: 500,
      });
      if (result.access_level === 'none' || result.access_level === 'suppressed') {
        setError(result.note || 'No data available.');
        setRows(null);
      } else {
        setRows(result.rows || []);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card mb-lg">
      <div className="flex-between mb-sm">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ fontSize: '1.75rem' }}>{info.icon}</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1rem' }}>{info.label}</div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{info.description}</div>
          </div>
        </div>
        <span className={`badge ${info.badge}`}>{deptKey}</span>
      </div>

      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '0.75rem' }}>
        {info.filters.map(({ key, label, options }) => (
          <div key={key}>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem', fontWeight: 600 }}>
              {label}
            </div>
            <select className="select" value={filters[key] || ''}
              onChange={e => setFilter(key, e.target.value)}>
              {options.map(o => <option key={o} value={o}>{o || 'Any'}</option>)}
            </select>
          </div>
        ))}
        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button className="btn btn-primary" onClick={search} disabled={loading}>
            {loading ? 'Searching…' : 'Search →'}
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}

      {rows !== null && !loading && (
        rows.length === 0
          ? <div className="text-muted text-sm">No records match your search.</div>
          : <DataTable dept={deptKey} rows={rows} />
      )}

      {rows !== null && !loading && rows.length > 0 && (
        <div style={{ marginTop: '0.75rem' }}>
          <a
            href={`/download/${deptKey}?role=analyst&fmt=csv`}
            className="btn btn-ghost"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.75rem' }}
            download
          >
            ↓ Download CSV
          </a>
        </div>
      )}
    </div>
  );
}

export default function CitizenPortal() {
  return (
    <div className="page">
      <div className="page-header">
        <h2>Citizen Data Portal</h2>
        <p>
          Explore public open data from the City of Kitchener. All data shown here is publicly
          available — no login required. Personal information is not displayed.
        </p>
      </div>

      <div className="alert alert-info mb-lg" style={{ marginBottom: '1.5rem' }}>
        <strong>Public access view.</strong> This portal shows only public-sensitivity datasets.
        Sensitive fields (owner names, contacts, legal descriptions) are automatically hidden.
        Internal staff can access more data via the <a href="/#/explorer" style={{ color: 'inherit' }}>Dataset Explorer</a>.
      </div>

      {Object.keys(DEPT_INFO).map(dept => (
        <DeptPanel key={dept} deptKey={dept} />
      ))}
    </div>
  );
}
