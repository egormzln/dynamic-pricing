import React from 'react'
import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import Overview from './pages/Overview.jsx'
import Catalog from './pages/Catalog.jsx'
import SkuDetail from './pages/SkuDetail.jsx'
import Rules from './pages/Rules.jsx'
import Monitor from './pages/Monitor.jsx'

const NAV = [
  { to: '/overview', ico: '◈', label: 'Обзор' },
  { to: '/catalog', ico: '▤', label: 'Каталог и цены' },
  { to: '/rules', ico: '⚙', label: 'Правила' },
  { to: '/monitor', ico: '📈', label: 'Монитор цен' },
]

export default function App() {
  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">₽</div>
          <div>
            <div className="brand-title">PriceEngine</div>
            <div className="brand-sub">Динамическое ценообразование</div>
          </div>
        </div>
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>
            <span className="nav-ico">{n.ico}</span>
            {n.label}
          </NavLink>
        ))}
        <div style={{ flex: 1 }} />
        <div className="brand-sub" style={{ padding: '0 8px' }}>
          dunnhumby · Breakfast at the Frat
        </div>
      </aside>

      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/catalog" element={<Catalog />} />
          <Route path="/catalog/:upc" element={<SkuDetail />} />
          <Route path="/rules" element={<Rules />} />
          <Route path="/monitor" element={<Monitor />} />
        </Routes>
      </main>
    </div>
  )
}
