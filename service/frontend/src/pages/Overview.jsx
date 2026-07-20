import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell,
} from 'recharts'
import { api } from '../api.js'
import { PromoBadge, Delta, fmtMoney, fmtPct, Spinner } from '../components/ui.jsx'

function Kpi({ label, value, delta, sub, deltaInvert }) {
  return (
    <div className="card kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value">{value}</span>
      {delta !== undefined && <span className="kpi-delta"><Delta value={delta} invert={deltaInvert} /></span>}
      {sub && <span className="kpi-sub">{sub}</span>}
    </div>
  )
}

export default function Overview() {
  const [rows, setRows] = useState(null)
  const [kpi, setKpi] = useState(null)
  const [policy, setPolicy] = useState(null)
  const nav = useNavigate()

  useEffect(() => {
    api.recommend(null).catch(() => null)
    Promise.all([api.skus(), api.kpi(), api.getPolicy()]).then(([r, k, p]) => {
      setRows(r); setKpi(k); setPolicy(p)
    })
  }, [])

  if (!rows || !kpi) return <Spinner />

  const objLabel = { profit: 'макс. прибыль', revenue: 'макс. выручка', target_margin: 'целевая маржа' }[policy?.objective]
  const top = rows.filter((r) => r.profit_uplift_pct > 0).slice(0, 8)

  // разбивка uplift по категориям
  const byCat = {}
  rows.forEach((r) => {
    byCat[r.category] = byCat[r.category] || { category: r.category, base: 0, opt: 0 }
    byCat[r.category].base += r.baseline_profit
    byCat[r.category].opt += r.expected_profit
  })
  const catData = Object.values(byCat).map((c) => ({
    name: c.category, uplift: c.base ? ((c.opt - c.base) / Math.abs(c.base)) * 100 : 0,
  }))

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Обзор</h1>
          <p className="page-desc">
            Сводка рекомендаций оптимизатора по каталогу под активной политикой
            (цель: <b>{objLabel}</b>). Модель спроса построена поверх оценённой эластичности и promo-lift.
          </p>
        </div>
        <button className="primary" onClick={() => nav('/catalog')}>Открыть каталог →</button>
      </div>

      <div className="grid kpi-grid" style={{ marginBottom: 24 }}>
        <Kpi label="Ожид. прибыль" value={fmtMoney(kpi.total_expected_profit)}
          delta={kpi.profit_uplift_pct} sub={`база ${fmtMoney(kpi.total_baseline_profit)}`} />
        <Kpi label="Ожид. выручка" value={fmtMoney(kpi.total_expected_revenue)}
          delta={kpi.revenue_uplift_pct} sub={`база ${fmtMoney(kpi.total_baseline_revenue)}`} />
        <Kpi label="Средняя маржа" value={(kpi.avg_margin * 100).toFixed(1) + '%'}
          sub="валовая по каталогу" />
        <Kpi label="Изменений цены" value={kpi.n_price_changes}
          sub={`из ${kpi.n_skus} SKU`} />
        <Kpi label="Доля на промо" value={(kpi.share_on_promo * 100).toFixed(0) + '%'}
          sub="в рамках capacity" />
      </div>

      <div className="two-col">
        <div className="card">
          <div className="section-title">Uplift прибыли по категориям</div>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={catData} layout="vertical" margin={{ left: 10, right: 20 }}>
              <XAxis type="number" stroke="#8b98a9" fontSize={11} unit="%" />
              <YAxis type="category" dataKey="name" stroke="#8b98a9" fontSize={11} width={120} />
              <Tooltip contentStyle={{ background: '#1c232e', border: '1px solid #262e3a', borderRadius: 8 }}
                formatter={(v) => [fmtPct(v), 'uplift']} />
              <Bar dataKey="uplift" radius={[0, 4, 4, 0]}>
                {catData.map((d, i) => (
                  <Cell key={i} fill={d.uplift >= 0 ? '#3fb950' : '#f85149'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <div className="section-title">Топ рекомендаций по uplift прибыли</div>
          <div className="table-wrap" style={{ border: 'none' }}>
            <table>
              <thead>
                <tr>
                  <th>SKU</th><th>Промо</th>
                  <th className="num">Цена</th><th className="num">→ Реком.</th><th className="num">Uplift</th>
                </tr>
              </thead>
              <tbody>
                {top.map((r) => (
                  <tr key={r.upc} onClick={() => nav(`/catalog/${r.upc}`)}>
                    <td>{r.description}</td>
                    <td><PromoBadge promo={r.recommended_promo} /></td>
                    <td className="num mono">{fmtMoney(r.current_price)}</td>
                    <td className="num mono">{fmtMoney(r.recommended_price)}</td>
                    <td className="num"><Delta value={r.profit_uplift_pct} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  )
}
