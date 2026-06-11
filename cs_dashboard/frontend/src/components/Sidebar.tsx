// 좌측 네비게이션 사이드바. 대시보드 링크와 인사이트 서브메뉴(접기·펼치기)를 표시한다.
// NavLink로 현재 경로를 감지해 활성 메뉴를 하이라이트한다.
// 메뉴 열림/닫힘(insightsOpen) 로컬 상태만 관리하며 다른 상태나 API 호출은 없다.
import { useState } from 'react'
import { NavLink } from 'react-router-dom'
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
