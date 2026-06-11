import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/dashboard/Dashboard'
import WingsTickets from './pages/insights/WingsTickets'
import RepeatParents from './pages/insights/RepeatParents'
import { api } from './api/client'

// 레이아웃(헤더 + 사이드바)과 라우팅만 담당한다. 기능 로직은 각 페이지에 위치한다.

function headerDate() {
  const d = new Date()
  const days = ['일', '월', '화', '수', '목', '금', '토']
  return `${d.getFullYear()}년 ${d.getMonth() + 1}월 ${d.getDate()}일 (${days[d.getDay()]})`
}

export default function App() {
  const [lastCollected, setLastCollected] = useState('마지막 수집: —')

  useEffect(() => {
    const load = () => {
      api.fetchLatestCollection()
        .then(r => {
          if (r?.collected_at) {
            setLastCollected(`마지막 수집: ${r.collected_at.slice(0, 16).replace('T', ' ')}`)
          }
        })
        .catch(() => {})
    }
    load()
    const t = setInterval(load, 60_000)
    return () => clearInterval(t)
  }, [])

  return (
    <BrowserRouter>
      <header>
        <div className="header-left">
          <h1 style={{ cursor: 'pointer' }} onClick={() => location.reload()}>
            공감센터 CS 대시보드
          </h1>
          <p>{headerDate()}</p>
        </div>
        <span id="last-collected">{lastCollected}</span>
      </header>
      <div className="layout">
        <Sidebar />
        <div className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/insights/wings" element={<WingsTickets />} />
            <Route path="/insights/parents" element={<RepeatParents />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  )
}
