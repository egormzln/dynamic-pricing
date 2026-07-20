const BASE = '/api'

async function req(path, opts) {
  const res = await fetch(BASE + path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

export const api = {
  meta: () => req('/meta'),
  skus: () => req('/skus'),
  sku: (upc) => req(`/skus/${upc}`),
  getPolicy: () => req('/policy'),
  putPolicy: (p) => req('/policy', { method: 'PUT', body: JSON.stringify(p) }),
  recommend: (p) => req('/recommend', { method: 'POST', body: JSON.stringify(p) }),
  kpi: () => req('/kpi'),
  apply: (upc) => req('/apply', { method: 'POST', body: JSON.stringify({ upc }) }),
  applyAll: () => req('/apply_all', { method: 'POST', body: '{}' }),
  history: (limit = 200) => req(`/history?limit=${limit}`),
}
