import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { getBusStopsGeo } from '../api/index.js';
// leaflet/dist/leaflet.css is imported globally in main.jsx

// Kitchener, ON centre coordinates
const MAP_CENTER = [43.452, -80.492];
const MAP_ZOOM = 12;

const MUNI_COLORS = {
  Kitchener: '#d97706',
  Waterloo:  '#2563eb',
  Cambridge: '#7c3aed',
  default:   '#64748b',
};

function StopMarker({ feature }) {
  const props = feature.properties || {};
  const geo = feature.geometry;
  if (!geo || !geo.coordinates) return null;

  const [lng, lat] = geo.coordinates;
  if (!lat || !lng) return null;

  const muni = props.municipality || props.MUNICIPALITY || 'default';
  const color = MUNI_COLORS[muni] || MUNI_COLORS.default;
  const isIXpress = (props.ixpress || props.IXPRESS) === 'Y';

  return (
    <CircleMarker
      center={[lat, lng]}
      radius={isIXpress ? 6 : 4}
      pathOptions={{
        color: isIXpress ? '#dc2626' : color,
        fillColor: isIXpress ? '#fca5a5' : color,
        fillOpacity: 0.75,
        weight: isIXpress ? 2 : 1,
      }}
    >
      <Popup>
        <div style={{ fontFamily: 'system-ui, sans-serif', minWidth: 160 }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>
            Stop {props.stop_id || props.STOP_ID}
          </div>
          <div>{props.street || props.STREET} @ {props.crossstreet || props.CROSSSTREET}</div>
          <div style={{ color: '#64748b', fontSize: '0.8em' }}>
            {muni} · {isIXpress ? '⚡ iXpress' : 'Local'}
          </div>
          <div style={{ color: (props.status || props.STATUS) === 'Active' ? '#16a34a' : '#dc2626',
            fontSize: '0.8em', marginTop: 2 }}>
            {props.status || props.STATUS || 'Unknown'}
          </div>
        </div>
      </Popup>
    </CircleMarker>
  );
}

export default function MapView() {
  const [geoData, setGeoData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [muniFilter, setMuniFilter] = useState('all');
  const [ixpressOnly, setIxpressOnly] = useState(false);
  // Defer MapContainer render until after React StrictMode double-mount cycle.
  // Without this, Leaflet crashes when StrictMode unmounts then remounts the map
  // on the same DOM element, wiping the entire React tree.
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    // Small timeout ensures the component has fully settled after StrictMode remount
    const t = setTimeout(() => setMapReady(true), 0);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    getBusStopsGeo(1178)
      .then(setGeoData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const features = geoData?.features || [];
  const hasGeometry = features.some(f => f.geometry?.coordinates);

  const filtered = features.filter(f => {
    const p = f.properties || {};
    const muni = p.municipality || p.MUNICIPALITY || '';
    if (muniFilter !== 'all' && muni !== muniFilter) return false;
    if (ixpressOnly && (p.ixpress || p.IXPRESS) !== 'Y') return false;
    return true;
  });

  const munis = [...new Set(features.map(f =>
    f.properties?.municipality || f.properties?.MUNICIPALITY || '').filter(Boolean))].sort();

  const iXpressCount = features.filter(f =>
    (f.properties?.ixpress || f.properties?.IXPRESS) === 'Y').length;

  return (
    <div className="page" style={{ maxWidth: '100%', padding: '1.5rem' }}>
      <div className="page-header">
        <h2>Map View</h2>
        <p>Bus stop locations across the Region of Waterloo from the GRT open data feed.</p>
      </div>

      {/* Stats */}
      <div className="card-grid card-grid-4 mb-lg">
        <div className="stat-card">
          <div className="stat-label">Total Stops</div>
          <div className="stat-value">{features.length.toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">iXpress Stops</div>
          <div className="stat-value" style={{ color: 'var(--restricted)' }}>{iXpressCount}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Municipalities</div>
          <div className="stat-value">{munis.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Showing</div>
          <div className="stat-value">{filtered.length.toLocaleString()}</div>
          <div className="stat-sub">after filters</div>
        </div>
      </div>

      {/* Filters */}
      <div className="card mb-lg">
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
          <div>
            <div className="stat-label" style={{ marginBottom: '0.3rem' }}>Municipality</div>
            <select className="select" value={muniFilter} onChange={e => setMuniFilter(e.target.value)}>
              <option value="all">All</option>
              {munis.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '1.1rem' }}>
            <input
              type="checkbox"
              id="ixpress"
              checked={ixpressOnly}
              onChange={e => setIxpressOnly(e.target.checked)}
            />
            <label htmlFor="ixpress" style={{ fontSize: '0.875rem', cursor: 'pointer' }}>
              iXpress stops only
            </label>
          </div>
          <div style={{ marginTop: '1.1rem' }}>
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              {Object.entries(MUNI_COLORS).filter(([k]) => k !== 'default').map(([muni, color]) => (
                <span key={muni} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem',
                  fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%',
                    background: color, display: 'inline-block' }} />
                  {muni}
                </span>
              ))}
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem',
                fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%',
                  background: '#dc2626', display: 'inline-block' }} />
                iXpress
              </span>
            </div>
          </div>
        </div>
      </div>

      {loading && <div className="loading">Loading bus stop locations…</div>}
      {error && <div className="error-box">{error}</div>}

      {!loading && !hasGeometry && (
        <div className="alert alert-warn mb-lg">
          ArcGIS geometry unavailable — showing tabular fallback. The map requires a live
          connection to the Kitchener ArcGIS API to render stop coordinates.
        </div>
      )}

      {!loading && (
        <div className="card" style={{ padding: 0 }}>
          {hasGeometry ? (
            <div style={{ height: 520, width: '100%' }}>
              {mapReady && (
                <MapContainer
                  key="citymind-map"
                  center={MAP_CENTER}
                  zoom={MAP_ZOOM}
                  style={{ height: '100%', width: '100%' }}
                  scrollWheelZoom={true}
                >
                  <TileLayer
                    attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                    url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                  />
                  {filtered.map((feature, i) => (
                    <StopMarker
                      key={feature.properties?.stop_id || feature.properties?.STOP_ID || i}
                      feature={feature}
                    />
                  ))}
                </MapContainer>
              )}
            </div>
          ) : (
            /* Fallback: tabular view if no geometry */
            <div style={{ padding: '1.25rem' }}>
              <div className="section-title mb-sm">Bus Stops — Tabular View</div>
              <div className="table-wrap" style={{ maxHeight: 400, overflowY: 'auto' }}>
                <table>
                  <thead>
                    <tr>
                      <th>Stop ID</th>
                      <th>Street</th>
                      <th>Cross Street</th>
                      <th>Municipality</th>
                      <th>iXpress</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.slice(0, 200).map((f, i) => {
                      const p = f.properties || {};
                      return (
                        <tr key={i}>
                          <td className="mono">{p.stop_id || p.STOP_ID}</td>
                          <td>{p.street || p.STREET}</td>
                          <td>{p.crossstreet || p.CROSSSTREET}</td>
                          <td>{p.municipality || p.MUNICIPALITY}</td>
                          <td>{(p.ixpress || p.IXPRESS) === 'Y'
                            ? <span className="badge badge-none">Yes</span>
                            : '—'}</td>
                          <td>{p.status || p.STATUS}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="alert alert-info" style={{ marginTop: '1rem' }}>
        <strong>Note:</strong> Water main geometry and permit locations are not shown — these
        datasets do not have coordinate columns in the local replica. Coordinates are fetched
        live from the Kitchener ArcGIS API for bus stops only.
      </div>
    </div>
  );
}
