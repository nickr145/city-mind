import { NavLink } from 'react-router-dom';

const links = [
  {
    section: 'Governance',
    items: [
      { to: '/dashboard', icon: '📊', label: 'Data Quality' },
      { to: '/dictionary', icon: '📖', label: 'Data Dictionary' },
      { to: '/audit', icon: '🔍', label: 'Audit Log' },
    ],
  },
  {
    section: 'Data',
    items: [
      { to: '/explorer', icon: '🗂️', label: 'Dataset Explorer' },
    ],
  },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <h1>CityMind</h1>
        <p>Internal Data Platform</p>
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
