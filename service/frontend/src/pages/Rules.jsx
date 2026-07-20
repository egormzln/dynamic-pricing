import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { Delta, PROMO_LABELS, fmtMoney, Spinner } from '../components/ui.jsx'

const PROMOS = ['none', 'tpr', 'display', 'feature', 'feature_display']
const OBJECTIVES = [
  { v: 'profit', l: 'Макс. прибыль' },
  { v: 'revenue', l: 'Макс. выручка' },
  { v: 'target_margin', l: 'Целевая маржа' },
]
const ENDINGS = [
  { v: 'none', l: 'Без округл.' },
  { v: '99', l: 'Оканчивать .99' },
  { v: '49', l: '.49 / .99' },
]

function Slider({ label, hint, value, min, max, step, onChange, fmt = (v) => v }) {
  return (
    <div className="field">
      <div className="field-label">
        <span>{label}</span><span className="field-val">{fmt(value)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))} />
      {hint && <span className="field-hint">{hint}</span>}
    </div>
  )
}

export default function Rules() {
  const [policy, setPolicy] = useState(null)
  const [preview, setPreview] = useState(null)
  const [saved, setSaved] = useState(true)
  const [toast, setToast] = useState(null)
  const timer = useRef(null)

  useEffect(() => { api.getPolicy().then((p) => { setPolicy(p); recompute(p, false) }) }, [])

  const recompute = (p, debounce = true) => {
    clearTimeout(timer.current)
    const run = () => api.recommend(p).then((r) => setPreview(r))
    if (debounce) timer.current = setTimeout(run, 220)
    else run()
  }

  const update = (patch) => {
    const next = { ...policy, ...patch }
    setPolicy(next); setSaved(false); recompute(next)
  }
  const updateCap = (promo, val) => {
    update({ promo_capacity: { ...policy.promo_capacity, [promo]: val } })
  }
  const togglePromo = (p) => {
    const has = policy.allowed_promos.includes(p)
    update({ allowed_promos: has ? policy.allowed_promos.filter((x) => x !== p) : [...policy.allowed_promos, p] })
  }

  const save = async () => {
    await api.putPolicy(policy)
    setSaved(true); setToast('Политика сохранена — применена ко всему сервису')
    setTimeout(() => setToast(null), 2600)
  }

  if (!policy) return <Spinner />
  const k = preview?.kpi

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="page-title">Правила ценообразования</h1>
          <p className="page-desc">
            Меняйте политику — рекомендации и KPI пересчитываются на лету.
            Нажмите «Сохранить», чтобы применить политику ко всему сервису.
          </p>
        </div>
        <button className="primary" onClick={save} disabled={saved}>
          {saved ? 'Сохранено' : 'Сохранить политику'}
        </button>
      </div>

      <div className="two-col">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="section-title">Бизнес-цель</div>
            <div className="seg" style={{ width: '100%' }}>
              {OBJECTIVES.map((o) => (
                <button key={o.v} style={{ flex: 1 }}
                  className={policy.objective === o.v ? 'active' : ''}
                  onClick={() => update({ objective: o.v })}>{o.l}</button>
              ))}
            </div>
            {policy.objective === 'target_margin' && (
              <div style={{ marginTop: 14 }}>
                <Slider label="Целевая маржа" value={policy.target_margin_value}
                  min={0.05} max={0.8} step={0.01} onChange={(v) => update({ target_margin_value: v })}
                  fmt={(v) => (v * 100).toFixed(0) + '%'} />
              </div>
            )}
          </div>

          <div className="card">
            <div className="section-title">Границы цены и маржи</div>
            <Slider label="Мин. наценка над cost" value={policy.min_margin} min={0} max={1} step={0.01}
              onChange={(v) => update({ min_margin: v })} fmt={(v) => '+' + (v * 100).toFixed(0) + '%'}
              hint="Цена не ниже cost × (1 + наценка)" />
            <Slider label="Макс. скидка от базовой цены" value={policy.max_discount} min={0} max={0.8} step={0.01}
              onChange={(v) => update({ max_discount: v })} fmt={(v) => '−' + (v * 100).toFixed(0) + '%'} />
            <Slider label="Макс. наценка над базовой ценой" value={policy.max_markup} min={0} max={1} step={0.01}
              onChange={(v) => update({ max_markup: v })} fmt={(v) => '+' + (v * 100).toFixed(0) + '%'} />
            <label className="toggle-row" style={{ marginTop: 4 }}>
              <span className={'toggle' + (policy.respect_bounds ? ' on' : '')}
                onClick={() => update({ respect_bounds: !policy.respect_bounds })}>
                {policy.respect_bounds ? '☑' : '☐'} Ограничивать историческими границами (p05–p95)
              </span>
            </label>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Live KPI */}
          <div className="card">
            <div className="section-title">Влияние политики (пересчёт вживую)</div>
            {!k ? <Spinner text="Пересчёт…" /> : (
              <div className="grid kpi-grid">
                <div className="kpi">
                  <span className="kpi-label">Прибыль</span>
                  <span className="kpi-value">{fmtMoney(k.total_expected_profit)}</span>
                  <span className="kpi-delta"><Delta value={k.profit_uplift_pct} /></span>
                </div>
                <div className="kpi">
                  <span className="kpi-label">Выручка</span>
                  <span className="kpi-value">{fmtMoney(k.total_expected_revenue)}</span>
                  <span className="kpi-delta"><Delta value={k.revenue_uplift_pct} /></span>
                </div>
                <div className="kpi">
                  <span className="kpi-label">Ср. маржа</span>
                  <span className="kpi-value">{(k.avg_margin * 100).toFixed(1)}%</span>
                </div>
                <div className="kpi">
                  <span className="kpi-label">На промо</span>
                  <span className="kpi-value">{(k.share_on_promo * 100).toFixed(0)}%</span>
                  <span className="kpi-sub">{k.n_price_changes} изм. цены</span>
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <div className="section-title">Промо-политика</div>
            <div className="field-hint" style={{ marginBottom: 8 }}>Разрешённые механики промо</div>
            <div className="toggle-row" style={{ marginBottom: 16 }}>
              {PROMOS.map((p) => (
                <span key={p} className={'toggle' + (policy.allowed_promos.includes(p) ? ' on' : '')}
                  onClick={() => togglePromo(p)}>{PROMO_LABELS[p]}</span>
              ))}
            </div>
            <div className="field-hint" style={{ marginBottom: 8 }}>
              Capacity — макс. доля SKU на каждом типе промо (жадное распределение по uplift)
            </div>
            {['tpr', 'display', 'feature', 'feature_display'].map((p) => (
              <Slider key={p} label={PROMO_LABELS[p]} value={policy.promo_capacity[p] ?? 0}
                min={0} max={0.5} step={0.01} onChange={(v) => updateCap(p, v)}
                fmt={(v) => (v * 100).toFixed(0) + '%'} />
            ))}
          </div>

          <div className="card">
            <div className="section-title">Округление и шаг</div>
            <div className="field-hint" style={{ marginBottom: 8 }}>Психологические окончания цены</div>
            <div className="seg" style={{ width: '100%', marginBottom: 16 }}>
              {ENDINGS.map((e) => (
                <button key={e.v} style={{ flex: 1 }}
                  className={policy.price_ending === e.v ? 'active' : ''}
                  onClick={() => update({ price_ending: e.v })}>{e.l}</button>
              ))}
            </div>
            <Slider label="Макс. изменение цены за цикл" value={policy.max_change_per_cycle}
              min={0.02} max={0.6} step={0.01} onChange={(v) => update({ max_change_per_cycle: v })}
              fmt={(v) => '±' + (v * 100).toFixed(0) + '%'}
              hint="Ограничивает резкие скачки относительно текущей цены" />
          </div>
        </div>
      </div>
      {toast && <div className="toast">{toast}</div>}
    </>
  )
}
