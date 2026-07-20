import React, { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { PromoBadge, SourceBadge, Delta, Ruleset, fmtMoney, Spinner } from '../components/ui.jsx'

const COLS = [
  { key: 'description', label: 'SKU', num: false },
  { key: 'category', label: 'Категория', num: false },
  { key: 'elasticity', label: 'ε', num: true },
  { key: 'current_price', label: 'Цена', num: true },
  { key: 'recommended_price', label: 'Рекоменд.', num: true },
  { key: 'price_change_pct', label: 'Δ цена', num: true },
  { key: 'recommended_promo', label: 'Промо', num: false },
  { key: 'expected_margin', label: 'Маржа', num: true },
  { key: 'profit_uplift_pct', label: 'Uplift', num: true },
  { key: 'binding_rules', label: 'Ограничения', num: false },
]

export default function Catalog() {
  const [rows, setRows] = useState(null)
  const [cat, setCat] = useState('all')
  const [sort, setSort] = useState({ key: 'profit_uplift_pct', dir: -1 })
  const nav = useNavigate()

  useEffect(() => { api.skus().then(setRows) }, [])
  if (!rows) return <Spinner />

  const cats = ['all', ...Array.from(new Set(rows.map((r) => r.category)))]
  const filtered = cat === 'all' ? rows : rows.filter((r) => r.category === cat)
  const sorted = [...filtered].sort((a, b) => {
    const va = a[sort.key], vb = b[sort.key]
    if (typeof va === 'string') return va.localeCompare(vb) * sort.dir
    return (va - vb) * sort.dir
  })

  const setSortKey = (k) => setSort((s) => ({ key: k, dir: s.key === k ? -s.dir : -1 }))

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Каталог и цены</h1>
          <p className="page-desc">
            Текущие и рекомендованные цены по всем SKU под активной политикой.
            Нажмите на строку — детальный разбор оптимума и история цены.
          </p>
        </div>
      </div>

      <div className="seg" style={{ marginBottom: 16 }}>
        {cats.map((c) => (
          <button key={c} className={cat === c ? 'active' : ''} onClick={() => setCat(c)}>
            {c === 'all' ? 'Все' : c}
          </button>
        ))}
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {COLS.map((c) => (
                <th key={c.key} className={c.num ? 'num' : ''} onClick={() => setSortKey(c.key)}>
                  {c.label}{sort.key === c.key ? (sort.dir < 0 ? ' ▾' : ' ▴') : ''}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((r) => (
              <tr key={r.upc} onClick={() => nav(`/catalog/${r.upc}`)}>
                <td>
                  <div style={{ fontWeight: 600 }}>{r.description}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{r.manufacturer}</div>
                </td>
                <td className="muted">{r.category}</td>
                <td className="num mono">
                  {r.elasticity} <SourceBadge source={r.elasticity_source} />
                </td>
                <td className="num mono">{fmtMoney(r.current_price)}</td>
                <td className="num mono" style={{ fontWeight: 600 }}>{fmtMoney(r.recommended_price)}</td>
                <td className="num"><Delta value={r.price_change_pct} /></td>
                <td><PromoBadge promo={r.recommended_promo} /></td>
                <td className="num mono">{(r.expected_margin * 100).toFixed(1)}%</td>
                <td className="num"><Delta value={r.profit_uplift_pct} /></td>
                <td><Ruleset rules={r.binding_rules} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}
