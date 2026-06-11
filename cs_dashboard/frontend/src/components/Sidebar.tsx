import { useState } from 'react'
import { NavLink } from 'react-router-dom'

// 사이드바 네비게이션. App.tsx 레이아웃에서 렌더링되며 라우팅만 담당한다.
export default function Sidebar() {
  const [insightsOpen, setInsightsOpen] = useState(true)

  return (
    <nav className="sidebar">
      <NavLink
        to="/"
        end
        className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
      >
        <span className="nav-icon">📊</span> 대시보드
      </NavLink>

      <div
        className={`nav-group-label${insightsOpen ? ' open' : ''}`}
        onClick={() => setInsightsOpen(o => !o)}
      >
        <span className="nav-icon">💡</span> 인사이트
        <span className="nav-arrow">&#9658;</span>
      </div>

      <div className={`nav-sub${insightsOpen ? ' open' : ''}`}>
        <NavLink
          to="/insights/wings"
          className={({ isActive }) => `nav-sub-item${isActive ? ' active' : ''}`}
        >
          반복 Wings 티켓
        </NavLink>
        <NavLink
          to="/insights/parents"
          className={({ isActive }) => `nav-sub-item${isActive ? ' active' : ''}`}
        >
          학부모 반복 인입
        </NavLink>
      </div>
    </nav>
  )
}
