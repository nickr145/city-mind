const BASE = '';  // proxied via vite dev server

// ── Catalog ──────────────────────────────────────────────────────────────────

export async function getCatalog() {
  const res = await fetch(`${BASE}/catalog`);
  if (!res.ok) throw new Error('Failed to fetch catalog');
  return res.json();
}

// Real open data replica endpoints
export async function getReplicaStats() {
  const res = await fetch(`${BASE}/replica/stats`);
  if (!res.ok) throw new Error('Failed to fetch replica stats');
  return res.json();
}

export async function getReplicaPermits(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${BASE}/replica/permits?${qs}`);
  if (!res.ok) throw new Error('Failed to fetch permits');
  return res.json();
}

export async function getReplicaWaterMains(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${BASE}/replica/water-mains?${qs}`);
  if (!res.ok) throw new Error('Failed to fetch water mains');
  return res.json();
}

export async function getReplicaBusStops(params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`${BASE}/replica/bus-stops?${qs}`);
  if (!res.ok) throw new Error('Failed to fetch bus stops');
  return res.json();
}

export async function getCatalogQuality() {
  const res = await fetch(`${BASE}/catalog/quality`);
  if (!res.ok) throw new Error('Failed to fetch catalog quality');
  return res.json();
}

export async function getCatalogDictionary() {
  const res = await fetch(`${BASE}/catalog/dictionary`);
  if (!res.ok) throw new Error('Failed to fetch data dictionary');
  return res.json();
}

export async function getDataset(datasetId) {
  const res = await fetch(`${BASE}/catalog/${datasetId}`);
  if (!res.ok) throw new Error(`Dataset not found: ${datasetId}`);
  return res.json();
}

export async function searchCatalog({ tags = [], department, query = '' } = {}) {
  const res = await fetch(`${BASE}/catalog/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tags, department, query }),
  });
  if (!res.ok) throw new Error('Catalog search failed');
  return res.json();
}

export async function upsertDataset({ role, dataset }) {
  const res = await fetch(`${BASE}/catalog/datasets`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role, dataset }),
  });
  if (!res.ok) throw new Error('Failed to upsert dataset');
  return res.json();
}

// ── Audit ─────────────────────────────────────────────────────────────────────

export async function getAuditLog(limit = 50) {
  const res = await fetch(`${BASE}/audit?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch audit log');
  return res.json();
}

// ── Query ─────────────────────────────────────────────────────────────────────

export async function queryDepartment({ department, role = 'analyst', filters = {}, limit = 200, as_of = null }) {
  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ department, role, filters, limit, ...(as_of ? { as_of } : {}) }),
  });
  if (!res.ok) throw new Error(`Query failed for ${department}`);
  return res.json();
}

export async function crossQuery({ role = 'analyst', limit = 200 } = {}) {
  const res = await fetch(`${BASE}/query/cross`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role, limit }),
  });
  if (!res.ok) throw new Error('Cross-departmental query failed');
  return res.json();
}

// ── Geo ───────────────────────────────────────────────────────────────────────

export async function getBusStopsGeo(limit = 500) {
  const res = await fetch(`${BASE}/geo/bus-stops?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch bus stop geometry');
  return res.json();
}

export async function getWaterMainsGeo(limit = 2000, source = '') {
  const params = new URLSearchParams({ limit });
  if (source) params.append('source', source);
  const res = await fetch(`${BASE}/geo/water-mains?${params}`);
  if (!res.ok) throw new Error('Failed to fetch water main geometry');
  return res.json();
}

export async function getBuildingPermitsGeo(limit = 1000, source = '', year = null) {
  const params = new URLSearchParams({ limit });
  if (source) params.append('source', source);
  if (year) params.append('year', year);
  const res = await fetch(`${BASE}/geo/building-permits?${params}`);
  if (!res.ok) throw new Error('Failed to fetch building permit geometry');
  return res.json();
}

// ── AI Chat ───────────────────────────────────────────────────────────────────

export async function chatWithAgent(message) {
  const res = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || 'Chat request failed');
  }
  return res.json(); // { reply: string }
}

// ── Sync ──────────────────────────────────────────────────────────────────────

export async function getSyncStatus() {
  const res = await fetch(`${BASE}/sync/status`);
  if (!res.ok) throw new Error('Failed to fetch sync status');
  return res.json();
}

export async function getSyncRuns(limit = 20) {
  const res = await fetch(`${BASE}/sync/runs?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch sync runs');
  return res.json();
}

export async function triggerSync(datasets = []) {
  const res = await fetch(`${BASE}/sync/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ datasets }),
  });
  if (!res.ok) throw new Error('Failed to trigger sync');
  return res.json();
}
