import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import Sidebar from './components/Sidebar.jsx';
import Dashboard from './pages/Dashboard.jsx';
import Dictionary from './pages/Dictionary.jsx';
import AuditLog from './pages/AuditLog.jsx';
import Explorer from './pages/Explorer.jsx';

export default function App() {
  return (
    <HashRouter>
      <div className="app">
        <Sidebar />
        <main className="content">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/dictionary" element={<Dictionary />} />
            <Route path="/audit" element={<AuditLog />} />
            <Route path="/explorer" element={<Explorer />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}
