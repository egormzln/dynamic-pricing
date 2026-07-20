import React, { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ResponsiveContainer, ComposedChart, LineChart, Line, XAxis, YAxis,
  Tooltip, ReferenceLine, ReferenceDot, ReferenceArea, CartesianGrid,
} from 'recharts'
import { api } from '../api.js'
import {
  PromoBadge, SourceBadge, Delta, Ruleset, fmtMoney, Spinner, PROMO_LABELS,
} from '../components/ui.jsx'

export default function SkuDetail() {
  const { upc } = useParams()
  const [data, setData] = useState(null)
  const [promo, setPromo] = useState(null)
  const [toast, setToast] = useState(null)

  const load = () => api.sku(upc).then((d) => {
    setData(d); setPromo((p) => p || d.recommendation.recommended_promo)
  })
  useEffect(() => { load() }, [upc])
  if (!data) return <Spinner />

  const { sku, recommendation: rec, curves, history } = data
  const curve = curves[promo] || curves[rec.recommended_promo] || []
  const feas = curve.filter((d) => d.feasible)
  const feasMin = feas.length ? feas[0].price : null
  const feasMax = feas.length ? feas[feas.length - 1].price : null
  // «оптимум» отмечаем в точке рекомендации (для выбранного = рекомендованного промо)
  const optPoint = promo === rec.recommended_promo
    ? { price: rec.recommended_price, profit: rec.expected_profit }
    : null

  const doApply = async () => {
    await api.apply(sku.upc)
    setToast('Цена применена — событие записано в монитор')
    setTimeout(() => setToast(null), 2600)
    load()
  }

  return (
    <>
      <Link to="/catalog" className="back-link">← Каталог</Link>
      <div className="page-head">
        <div>
          <h1 className="page-title">{sku.description}</h1>
          <p className="page-desc">
            {sku.manufacturer} · {sku.category} · {sku.size} · UPC {sku.upc}
          </p>
        </div>
        <button className="primary" onClick={doApply}>Применить рекомендацию</button>
      </div>

      <div className="two-col">
        {/* левая колонка — рекомендация и параметры */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="section-title">Рекомендация</div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 6 }}>
              <span className="muted mono" style={{ fontSize: 18, textDecoration: 'line-through' }}>
                {fmtMoney(rec.current_price)}
              </span>
              <span className="mono" style={{ fontSize: 30, fontWeight: 700 }}>
                {fmtMoney(rec.recommended_price)}
              </span>
              <Delta value={rec.price_change_pct} />
            </div>
            <div style={{ marginBottom: 12 }}>
              <PromoBadge promo={rec.recommended_promo} />
              {rec.current_promo !== rec.recommended_promo && (
                <span className="muted" style={{ marginLeft: 8, fontSize: 12 }}>
                  было: {PROMO_LABELS[rec.current_promo]}
                </span>
              )}
            </div>
            <div className="stat-line"><span className="k">Ожид. прибыль</span>
              <span className="mono">{fmtMoney(rec.expected_profit)} (<Delta value={rec.profit_uplift_pct} />)</span></div>
            <div className="stat-line"><span className="k">Ожид. выручка</span>
              <span className="mono">{fmtMoney(rec.expected_revenue)} (<Delta value={rec.revenue_uplift_pct} />)</span></div>
            <div className="stat-line"><span className="k">Ожид. спрос</span>
              <span className="mono">{rec.expected_units} ед.</span></div>
            <div className="stat-line"><span className="k">Валовая маржа</span>
              <span className="mono">{(rec.expected_margin * 100).toFixed(1)}%</span></div>
            <div className="stat-line"><span className="k">Активные ограничения</span>
              <span><Ruleset rules={rec.binding_rules} /></span></div>
          </div>

          <div className="card">
            <div className="section-title">Параметры товара</div>
            <div className="stat-line"><span className="k">Эластичность ε</span>
              <span className="mono">{sku.elasticity} <SourceBadge source={sku.elasticity_source} /></span></div>
            <div className="stat-line"><span className="k">Себестоимость</span>
              <span className="mono">{fmtMoney(sku.cost)}</span></div>
            <div className="stat-line"><span className="k">Базовая цена</span>
              <span className="mono">{fmtMoney(sku.base_price)}</span></div>
            <div className="stat-line"><span className="k">Базовый спрос</span>
              <span className="mono">{sku.base_units} ед./нед.</span></div>
            <div className="stat-line"><span className="k">Флагман. магазин</span>
              <span className="mono">#{sku.flagship_store}</span></div>
          </div>
        </div>

        {/* правая колонка — графики */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <div className="section-title" style={{ margin: 0 }}>Кривая прибыли по цене</div>
              <div className="seg">
                {Object.keys(curves).map((p) => (
                  <button key={p} className={promo === p ? 'active' : ''} onClick={() => setPromo(p)}>
                    {PROMO_LABELS[p]}
                  </button>
                ))}
              </div>
            </div>
            <ResponsiveContainer width="100%" height={280}>
              <ComposedChart data={curve} margin={{ left: 6, right: 10, top: 8 }}>
                <CartesianGrid stroke="#262e3a" strokeDasharray="3 3" />
                <XAxis dataKey="price" type="number" domain={['dataMin', 'dataMax']}
                  stroke="#8b98a9" fontSize={11} tickFormatter={(v) => '$' + v.toFixed(2)} />
                <YAxis stroke="#8b98a9" fontSize={11} />
                <Tooltip contentStyle={{ background: '#1c232e', border: '1px solid #262e3a', borderRadius: 8 }}
                  formatter={(v, n) => [n === 'profit' ? fmtMoney(v) : Math.round(v), n === 'profit' ? 'прибыль' : 'спрос']}
                  labelFormatter={(l) => 'Цена ' + fmtMoney(l)} />
                {feasMin != null && (
                  <ReferenceArea x1={feasMin} x2={feasMax} fill="#4c8dff" fillOpacity={0.12} stroke="none"
                    label={{ value: 'допустимо', fill: '#4c8dff', fontSize: 10, position: 'insideTop' }} />
                )}
                <Line dataKey="profit" stroke="#4c8dff" strokeWidth={2} dot={false} isAnimationActive={false} />
                <ReferenceLine x={rec.current_price} stroke="#8b98a9" strokeDasharray="4 4"
                  label={{ value: 'сейчас', fill: '#8b98a9', fontSize: 10, position: 'top' }} />
                {optPoint && (
                  <ReferenceDot x={optPoint.price} y={optPoint.profit} r={5} fill="#3fb950" stroke="#fff" strokeWidth={1.5}
                    label={{ value: 'оптимум', fill: '#3fb950', fontSize: 10, position: 'top' }} />
                )}
              </ComposedChart>
            </ResponsiveContainer>
            <div className="field-hint">
              Закрашенная область — допустимый под правилами диапазон цены для выбранного промо.
            </div>
          </div>

          <div className="card">
            <div className="section-title">История цены (52 недели, магазин #{sku.flagship_store})</div>
            {history.length ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={history} margin={{ left: 6, right: 10, top: 8 }}>
                  <CartesianGrid stroke="#262e3a" strokeDasharray="3 3" />
                  <XAxis dataKey="date" stroke="#8b98a9" fontSize={10} minTickGap={40} />
                  <YAxis stroke="#8b98a9" fontSize={11} tickFormatter={(v) => '$' + v} />
                  <Tooltip contentStyle={{ background: '#1c232e', border: '1px solid #262e3a', borderRadius: 8 }}
                    formatter={(v) => fmtMoney(v)} />
                  <Line dataKey="base_price" stroke="#8b98a9" strokeWidth={1} dot={false} name="базовая" />
                  <Line dataKey="price" stroke="#a371f7" strokeWidth={2} dot={false} name="цена" />
                  <ReferenceLine y={rec.recommended_price} stroke="#3fb950" strokeDasharray="4 4"
                    label={{ value: 'реком.', fill: '#3fb950', fontSize: 10 }} />
                </LineChart>
              </ResponsiveContainer>
            ) : <div className="muted">Нет истории по этому SKU.</div>}
          </div>
        </div>
      </div>
      {toast && <div className="toast">{toast}</div>}
    </>
  )
}
