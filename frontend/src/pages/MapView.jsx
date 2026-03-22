import { useEffect, useState } from 'react';
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup } from 'react-leaflet';
import { getBusStopsGeo, getWaterMainsGeo, getBuildingPermitsGeo } from '../api/index.js';

// Region of Waterloo centre coordinates
const MAP_CENTER = [43.465, -80.522];
const MAP_ZOOM = 12;

const SOURCE_COLORS = {
  kitchener: '#2563eb',
  waterloo_city: '#be185d',
};

const MUNI_COLORS = {
  Kitchener: '#d97706',
  Waterloo: '#2563eb',
  Cambridge: '#7c3aed',
  default: '#64748b',
};

const MATERIAL_COLORS = {
  PVC: '#22c55e',
  PVCO: '#16a34a',
  DI: '#3b82f6',
  CI: '#6366f1',
  AC: '#f59e0b',
  HDPE: '#14b8a6',
  default: '#64748b',
};

const PERMIT_TYPE_COLORS = {
  'Residential Building (House)': '#22c55e',
  'Residential Building (Multi)': '#16a34a',
  'Residential Alteration': '#84cc16',
  'Non-Residential Alteration': '#f59e0b',
  'Plumbing': '#3b82f6',
  default: '#8b5cf6',
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
        </div>
      </Popup>
    </CircleMarker>
  );
}

function WaterMainLine({ feature }) {
  const props = feature.properties || {};
  const geo = feature.geometry;
  if (!geo || !geo.coordinates) return null;

  // Convert coordinates to [lat, lng] format
  let positions;
  if (geo.type === 'MultiLineString') {
    positions = geo.coordinates.flat().map(([lng, lat]) => [lat, lng]);
  } else {
    positions = geo.coordinates.map(([lng, lat]) => [lat, lng]);
  }

  const material = props.material || 'default';
  const color = MATERIAL_COLORS[material] || MATERIAL_COLORS.default;
  const sourceColor = SOURCE_COLORS[props.source_id] || '#64748b';

  return (
    <Polyline
      positions={positions}
      pathOptions={{
        color: color,
        weight: 2,
        opacity: 0.7,
      }}
    >
      <Popup>
        <div style={{ fontFamily: 'system-ui, sans-serif', minWidth: 180 }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>
            Water Main {props.watmain_id}
          </div>
          <div>Material: <strong>{material}</strong></div>
          <div>Size: {props.pipe_size}mm</div>
          <div>Pressure Zone: {props.pressure_zone}</div>
          <div>Status: {props.status}</div>
          <div style={{ marginTop: 4, fontSize: '0.8em', color: sourceColor }}>
            {props.source_id === 'kitchener' ? 'Kitchener' : 'Waterloo'}
          </div>
        </div>
      </Popup>
    </Polyline>
  );
}

function PermitMarker({ feature }) {
  const props = feature.properties || {};
  const geo = feature.geometry;
  if (!geo || !geo.coordinates) return null;

  const [lng, lat] = geo.coordinates;
  if (!lat || !lng) return null;

  const permitType = props.permit_type || 'default';
  const color = PERMIT_TYPE_COLORS[permitType] || PERMIT_TYPE_COLORS.default;
  const sourceColor = SOURCE_COLORS[props.source_id] || '#64748b';

  const value = props.construction_value;
  const valueStr = value ? `$${(value / 1000).toFixed(0)}k` : '—';

  return (
    <CircleMarker
      center={[lat, lng]}
      radius={5}
      pathOptions={{
        color: color,
        fillColor: color,
        fillOpacity: 0.6,
        weight: 1,
      }}
    >
      <Popup>
        <div style={{ fontFamily: 'system-ui, sans-serif', minWidth: 200 }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>
            Permit {props.permitno}
          </div>
          <div>{props.permit_type}</div>
          <div>{props.work_type}</div>
          <div style={{ marginTop: 4 }}>
            <strong>Value:</strong> {valueStr}
          </div>
          <div><strong>Status:</strong> {props.permit_status}</div>
          <div style={{ fontSize: '0.85em', color: '#64748b' }}>{props.foldername}</div>
          <div style={{ marginTop: 4, fontSize: '0.8em', color: sourceColor }}>
            {props.source_id === 'kitchener' ? 'Kitchener' : 'Waterloo'}
          </div>
        </div>
      </Popup>
    </CircleMarker>
  );
}

export default function MapView() {
  const [busStops, setBusStops] = useState(null);
  const [waterMains, setWaterMains] = useState(null);
  const [permits, setPermits] = useState(null);
  const [loading, setLoading] = useState({ busStops: true, waterMains: true, permits: true });
  const [error, setError] = useState(null);

  // Layer visibility
  const [showBusStops, setShowBusStops] = useState(true);
  const [showWaterMains, setShowWaterMains] = useState(true);
  const [showPermits, setShowPermits] = useState(true);

  // Filters
  const [sourceFilter, setSourceFilter] = useState('');
  const [permitYear, setPermitYear] = useState(2024);

  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setMapReady(true), 0);
    return () => clearTimeout(t);
  }, []);

  // Fetch bus stops
  useEffect(() => {
    if (!showBusStops) return;
    setLoading(l => ({ ...l, busStops: true }));
    getBusStopsGeo(2000)
      .then(setBusStops)
      .catch(e => setError(e.message))
      .finally(() => setLoading(l => ({ ...l, busStops: false })));
  }, [showBusStops]);

  // Fetch water mains
  useEffect(() => {
    if (!showWaterMains) return;
    setLoading(l => ({ ...l, waterMains: true }));
    getWaterMainsGeo(2000, sourceFilter)
      .then(setWaterMains)
      .catch(e => setError(e.message))
      .finally(() => setLoading(l => ({ ...l, waterMains: false })));
  }, [showWaterMains, sourceFilter]);

  // Fetch permits
  useEffect(() => {
    if (!showPermits) return;
    setLoading(l => ({ ...l, permits: true }));
    getBuildingPermitsGeo(1000, sourceFilter, permitYear)
      .then(setPermits)
      .catch(e => setError(e.message))
      .finally(() => setLoading(l => ({ ...l, permits: false })));
  }, [showPermits, sourceFilter, permitYear]);

  const busStopFeatures = busStops?.features || [];
  const waterMainFeatures = waterMains?.features || [];
  const permitFeatures = permits?.features || [];

  const isLoading = Object.values(loading).some(Boolean);

  return (
    <div className="page" style={{ maxWidth: '100%', padding: '1.5rem' }}>
      <div className="page-header">
        <h2>Map View</h2>
        <p>Geographic visualization of municipal infrastructure from Kitchener and Waterloo.</p>
      </div>

      {/* Stats */}
      <div className="card-grid card-grid-4 mb-lg">
        <div className="stat-card">
          <div className="stat-label">Bus Stops</div>
          <div className="stat-value">{busStopFeatures.length.toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Water Mains</div>
          <div className="stat-value">{waterMainFeatures.length.toLocaleString()}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Building Permits</div>
          <div className="stat-value">{permitFeatures.length.toLocaleString()}</div>
          <div className="stat-sub">{permitYear}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Features</div>
          <div className="stat-value">
            {(busStopFeatures.length + waterMainFeatures.length + permitFeatures.length).toLocaleString()}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="card mb-lg">
        <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>
          {/* Layer toggles */}
          <div>
            <div className="stat-label" style={{ marginBottom: '0.5rem' }}>Layers</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={showBusStops} onChange={e => setShowBusStops(e.target.checked)} />
                <span style={{ fontSize: '0.875rem' }}>Bus Stops</span>
                {loading.busStops && <span className="text-muted" style={{ fontSize: '0.75rem' }}>loading...</span>}
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={showWaterMains} onChange={e => setShowWaterMains(e.target.checked)} />
                <span style={{ fontSize: '0.875rem' }}>Water Mains</span>
                {loading.waterMains && <span className="text-muted" style={{ fontSize: '0.75rem' }}>loading...</span>}
              </label>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
                <input type="checkbox" checked={showPermits} onChange={e => setShowPermits(e.target.checked)} />
                <span style={{ fontSize: '0.875rem' }}>Building Permits</span>
                {loading.permits && <span className="text-muted" style={{ fontSize: '0.75rem' }}>loading...</span>}
              </label>
            </div>
          </div>

          {/* Source filter */}
          <div>
            <div className="stat-label" style={{ marginBottom: '0.3rem' }}>City</div>
            <select className="select" value={sourceFilter} onChange={e => setSourceFilter(e.target.value)}>
              <option value="">All Cities</option>
              <option value="kitchener">Kitchener</option>
              <option value="waterloo_city">Waterloo</option>
            </select>
          </div>

          {/* Permit year */}
          <div>
            <div className="stat-label" style={{ marginBottom: '0.3rem' }}>Permit Year</div>
            <select className="select" value={permitYear} onChange={e => setPermitYear(Number(e.target.value))}>
              {[2026, 2025, 2024, 2023, 2022, 2021, 2020].map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>

          {/* Legend */}
          <div>
            <div className="stat-label" style={{ marginBottom: '0.5rem' }}>Legend</div>
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', fontSize: '0.75rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                <span style={{ fontWeight: 600, marginBottom: '0.2rem' }}>Pipe Material</span>
                {Object.entries(MATERIAL_COLORS).filter(([k]) => k !== 'default').slice(0, 4).map(([mat, color]) => (
                  <span key={mat} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <span style={{ width: 12, height: 3, background: color, display: 'inline-block' }} />
                    {mat}
                  </span>
                ))}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                <span style={{ fontWeight: 600, marginBottom: '0.2rem' }}>Source</span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: SOURCE_COLORS.kitchener }} />
                  Kitchener
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: SOURCE_COLORS.waterloo_city }} />
                  Waterloo
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {error && <div className="error-box mb-lg">{error}</div>}

      {/* Map */}
      <div className="card" style={{ padding: 0 }}>
        <div style={{ height: 600, width: '100%' }}>
          {mapReady && (
            <MapContainer
              key="citymind-map"
              center={MAP_CENTER}
              zoom={MAP_ZOOM}
              style={{ height: '100%', width: '100%' }}
              scrollWheelZoom={true}
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
              />

              {/* Water mains layer (render first so it's behind) */}
              {showWaterMains && waterMainFeatures.map((feature, i) => (
                <WaterMainLine key={feature.properties?.watmain_id || `wm-${i}`} feature={feature} />
              ))}

              {/* Building permits layer */}
              {showPermits && permitFeatures.map((feature, i) => (
                <PermitMarker key={feature.properties?.permitno || `p-${i}`} feature={feature} />
              ))}

              {/* Bus stops layer (render last so it's on top) */}
              {showBusStops && busStopFeatures.map((feature, i) => (
                <StopMarker key={feature.properties?.stop_id || `bs-${i}`} feature={feature} />
              ))}
            </MapContainer>
          )}
        </div>
      </div>

      <div className="alert alert-info" style={{ marginTop: '1rem' }}>
        <strong>Note:</strong> Geometry is fetched live from ArcGIS APIs. Water mains show up to 2000 segments
        per city. Building permits are filtered by year to keep the map responsive.
      </div>
    </div>
  );
}
