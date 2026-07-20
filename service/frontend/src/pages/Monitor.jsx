import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend,
} from 'recharts'
import { api } from '../api.js'
import { PromoBadge, Delta, fmtMoney, Spinner } from '../components/ui.jsx'

export default function Monitor() {
  const [data, setData] = useState(null)
  const [upc, setUpc] = useState(null)
  const [busy, setBusy] = useState(false)
  const [toast, setToast] = useState(null)

  const load = () => api.history(300).then((d) => {
    setData(d)
    setUpc((u) => u || (d.series[0] && d.series[0].upc))
  })
  useEffect(() => { load() }, [])
  if (!data) return <Spinner />

  const skuList = Array.from(
    new Map(data.series.map((s) => [s.upc, s])).values()
  )
  const nameOf = (u) => {
    const ev = data.events.find((e) => e.upc === u)
    return ev ? ev.description : `UPC ${u}`
  }
  const series = data.series.filter((s) => s.upc === upc)

  const applyAll = async () => {
    setBusy(true)
    const r = await api.applyAll()
    setBusy(false)
    setToast(`Применено рекомендаций: ${r.applied}`)
    setTimeout(() => setToast(null), 2600)
    load()
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Монитор цен</h1>
          <p className="page-desc">
            Динамика цен по SKU и журнал изменений. «Применить все» проведёт рекомендованные
            изменения по каталогу и запишет их в аудит.
          </p>
        </div>
        <button className="primary" onClick={applyAll} disabled={busy}>
          {busy ? 'Применяем…' : 'Применить все рекомендации'}
        </button>
      </div>

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, gap: 12, flexWrap: 'wrap' }}>
          <div className="section-title" style={{ margin: 0 }}>Динамика цены</div>
          <select style={{ width: 280 }} value={upc || ''} onChange={(e) => setUpc(Number(e.target.value))}>
            {skuList.map((s) => (
              <option key={s.upc} value={s.upc}>{nameOf(s.upc)}</option>
            ))}
          </select>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={series} margin={{ left: 6, right: 12, top: 8 }}>
            <CartesianGrid stroke="#262e3a" strokeDasharray="3 3" />
            <XAxis dataKey="date" stroke="#8b98a9" fontSize={10} minTickGap={40} />
            <YAxis stroke="#8b98a9" fontSize={11} tickFormatter={(v) => '$' + v} />
            <Tooltip contentStyle={{ background: '#1c232e', border: '1px solid #262e3a', borderRadius: 8 }}
              formatter={(v) => fmtMoney(v)} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line dataKey="base_price" name="базовая цена" stroke="#8b98a9" strokeWidth={1} dot={false} />
            <Line dataKey="price" name="фактическая цена" stroke="#4c8dff" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <div className="section-title">Журнал изменений цен ({data.events.length})</div>
        {!data.events.length ? (
          <div className="muted">
            Пока нет применённых изменений. Примените рекомендацию на странице SKU
            или нажмите «Применить все рекомендации».
          </div>
        ) : (
          <div className="table-wrap" style={{ border: 'none' }}>
            <table>
              <thead>
                <tr>
                  <th>Время</th><th>SKU</th>
                  <th className="num">Было</th><th className="num">Стало</th>
                  <th>Промо</th><th className="num">Uplift</th><th>Причина</th>
                </tr>
              </thead>
              <tbody>
                {data.events.map((e) => (
                  <tr key={e.id}>
                    <td className="muted mono">{new Date(e.ts).toLocaleString('ru-RU')}</td>
                    <td><Link to={`/catalog/${e.upc}`} style={{ color: 'var(--accent)' }}>{e.description}</Link></td>
                    <td className="num mono muted">{fmtMoney(e.old_price)}</td>
                    <td className="num mono" style={{ fontWeight: 600 }}>{fmtMoney(e.new_price)}</td>
                    <td>
                      <PromoBadge promo={e.new_promo} />
                      {e.old_promo !== e.new_promo && <span className="muted" style={{ fontSize: 11 }}> ← {e.old_promo}</span>}
                    </td>
                    <td className="num"><Delta value={e.uplift_pct} /></td>
                    <td className="muted" style={{ fontSize: 12 }}>{e.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {toast && <div className="toast">{toast}</div>}
    </>
  )
}
