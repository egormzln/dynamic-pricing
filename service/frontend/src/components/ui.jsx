import React from 'react'

export const PROMO_LABELS = {
  none: 'Без промо',
  tpr: 'Скидка',
  display: 'Выкладка',
  feature: 'Каталог',
  feature_display: 'Каталог+выкладка',
}

export const RULE_LABELS = {
  min_margin: 'мин. маржа',
  max_discount: 'макс. скидка',
  max_markup: 'макс. наценка',
  max_change: 'лимит шага',
  hist_bounds: 'ист. границы',
  no_change: 'без изменений',
}

export const fmtMoney = (v) => '$' + Number(v).toFixed(2)
export const fmtPct = (v) => (v > 0 ? '+' : '') + Number(v).toFixed(1) + '%'
export const fmtInt = (v) => Math.round(v).toLocaleString('ru-RU')

export function PromoBadge({ promo }) {
  return <span className={`badge badge-${promo}`}>{PROMO_LABELS[promo] || promo}</span>
}

export function SourceBadge({ source }) {
  const label = { per_sku: 'по SKU', category: 'по категории', global: 'глобальная' }[source] || source
  const title = {
    per_sku: 'Эластичность оценена индивидуально по этому SKU (модель CausalForest DML)',
    category: 'Эластичность оценена по категории (within-SKU OLS) — приближение',
    global: 'Глобальный фолбэк эластичности — грубое приближение',
  }[source]
  return <span className={`badge badge-src-${source}`} title={title}>{label}</span>
}

export function Delta({ value, suffix = '%', invert = false }) {
  const pos = invert ? value < 0 : value > 0
  const cls = value === 0 ? 'muted' : pos ? 'pos' : 'neg'
  const sign = value > 0 ? '+' : ''
  return <span className={cls}>{sign}{Number(value).toFixed(1)}{suffix}</span>
}

export function Ruleset({ rules }) {
  if (!rules || !rules.length) return <span className="muted">—</span>
  return rules.map((r) => <span key={r} className="chip">{RULE_LABELS[r] || r}</span>)
}

export function Spinner({ text = 'Загрузка…' }) {
  return <div className="spinner">{text}</div>
}
