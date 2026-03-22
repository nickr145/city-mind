const BASE = '';  // proxied via vite dev server

export async function getCatalog() {
  const res = await fetch(`${BASE}/catalog`);
  if (!res.ok) throw new Error('Failed to fetch catalog');
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

export async function searchCatalog({ tags = [], department } = {}) {
  const res = await fetch(`${BASE}/catalog/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tags, department }),
  });
  if (!res.ok) throw new Error('Catalog search failed');
  return res.json();
}

export async function getAuditLog(limit = 50) {
  const res = await fetch(`${BASE}/audit?limit=${limit}`);
  if (!res.ok) throw new Error('Failed to fetch audit log');
  return res.json();
}

export async function queryDepartment({ department, role = 'analyst', filters = {}, limit = 200 }) {
  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ department, role, filters, limit }),
  });
  if (!res.ok) throw new Error(`Query failed for ${department}`);
  return res.json();
}
