import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { searchCatalog } from '../api/index.js';

const links = [
  {
    section: 'Governance',
    items: [
      { to: '/dashboard',  icon: '📊', label: 'Data Quality' },
      { to: '/dictionary', icon: '📖', label: 'Data Dictionary' },
      { to: '/audit',      icon: '🔍', label: 'Audit Log' },
    ],
  },
  {
    section: 'Data',
    items: [
      { to: '/explorer',      icon: '🗂️',  label: 'Dataset Explorer' },
      { to: '/cross-analysis', icon: '🔗', label: 'Cross Analysis' },
      { to: '/citizen',       icon: '🏙️',  label: 'Citizen Portal' },
      { to: '/map',           icon: '🗺️',  label: 'Map View' },
    ],
  },
  {
    section: 'Admin',
    items: [
      { to: '/sync-status', icon: '🔄', label: 'Sync Status' },
    ],
  },
];

const DEPT_BADGE = {
  planning:    'badge-pln',
  engineering: 'badge-eng',
  transit:     'badge-trt',
};

export default function Sidebar() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const navigate = useNavigate();

  const handleSearch = async (e) => {
    const val = e.target.value;
    setQuery(val);
    if (!val.trim()) {
      setResults([]);
      return;
    }
    setSearching(true);
    try {
      const data = await searchCatalog({ query: val });
      setResults(data.results || []);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleResultClick = (dept) => {
    setQuery('');
    setResults([]);
    navigate(`/explorer?dept=${dept}`);
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1>CityMind</h1>
        <p>Internal Data Platform</p>
      </div>

      {/* Catalog search */}
      <div style={{ padding: '0.6rem 1rem', borderBottom: '1px solid #1e293b', position: 'relative' }}>
        <input
          className="input"
          style={{
            width: '100%',
            background: '#1e293b',
            border: '1px solid #334155',
            color: '#e2e8f0',
            fontSize: '0.8rem',
            padding: '0.4rem 0.65rem',
          }}
          placeholder="Search datasets…"
          value={query}
          onChange={handleSearch}
        />
        {results.length > 0 && (
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            background: '#1e293b',
            border: '1px solid #334155',
            borderTop: 'none',
            zIndex: 100,
            maxHeight: 240,
            overflowY: 'auto',
          }}>
            {results.map((r) => (
              <button
                key={r.dataset_id}
                onClick={() => handleResultClick(r.department)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  width: '100%',
                  background: 'none',
                  border: 'none',
                  padding: '0.55rem 1rem',
                  cursor: 'pointer',
                  textAlign: 'left',
                  color: '#cbd5e1',
                  fontSize: '0.8rem',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#0f172a'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'none'}
              >
                <span className={`badge ${DEPT_BADGE[r.department] || ''}`}
                  style={{ fontSize: '0.6rem' }}>
                  {r.department}
                </span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {r.name}
                </span>
              </button>
            ))}
          </div>
        )}
        {searching && (
          <div style={{ padding: '0.4rem 1rem', color: '#64748b', fontSize: '0.75rem' }}>
            Searching…
          </div>
        )}
      </div>

      <nav className="sidebar-nav">
        {links.map(({ section, items }) => (
          <div key={section}>
            <div className="sidebar-section">{section}</div>
            {items.map(({ to, icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  'sidebar-link' + (isActive ? ' active' : '')
                }
              >
                <span className="icon">{icon}</span>
                {label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        Region of Waterloo · CityMind v1.0
      </div>
    </aside>
  );
}
