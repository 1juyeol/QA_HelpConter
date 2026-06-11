import { Fragment, useEffect, useState } from 'react'
import { api, type InsightParent } from '../../api/client'

const CATEGORY_ORDER = ['네트워크·앱 오류', '기기·하드웨어 오류', '미납·결제', '해지·유지 상담', '체험 관련', '교재·물류·배송', '계정·서비스', '기타']

// 학부모 반복 인입 목록. 독립적으로 fetch하며 다른 페이지와 상태를 공유하지 않는다.
export default function RepeatParents() {
  const [data, setData] = useState<InsightParent[]>([])
  const [updatedAt, setUpdatedAt] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [activeCats, setActiveCats] = useState<Set<string>>(new Set())
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const res = await api.fetchRepeatParents()
      setData(res.data || [])
      setUpdatedAt(res.updated_at ? `최근 30일 기준 · 업데이트: ${res.updated_at.slice(0, 16)}` : '')
      setActiveCats(new Set())
    } finally {
      setLoading(false)
    }
  }

  async function handleRefresh() {
    setRefreshing(true)
    try {
      await api.refreshInsights()
      await load()
    } finally {
      setRefreshing(false)
    }
  }

  function toggleCat(cat: string) {
    setActiveCats(prev => {
      if (cat === '전체') return new Set()
      const next = new Set(prev)
      next.has(cat) ? next.delete(cat) : next.add(cat)
      return next
    })
  }

  function toggleExpand(i: number) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  const allCats = [...new Set(data.flatMap(r => r.categories || []))].sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a), bi = CATEGORY_ORDER.indexOf(b)
    if (ai === -1 && bi === -1) return a.localeCompare(b)
    if (ai === -1) return 1; if (bi === -1) return -1
    return ai - bi
  })

  const rows = activeCats.size === 0
    ? data
    : data.filter(r => (r.categories || []).some(c => activeCats.has(c)))

  return (
    <div className="container">
      <div className="section-card">
        <h2>학부모 반복 인입</h2>
        <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 16 }}>
          동일 학부모가 여러 차례 CS 인입한 건 — 미해결 이슈나 반복 불만 고객을 파악할 수 있습니다.
        </p>
        <div className="insight-toolbar">
          <span style={{ fontSize: 12, color: '#94a3b8' }}>{updatedAt}</span>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            style={{ padding: '8px 16px', background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, cursor: refreshing ? 'default' : 'pointer', fontSize: 13, fontWeight: 500, color: '#374151' }}
          >
            {refreshing ? '업데이트 중...' : '↻ 새로고침'}
          </button>
        </div>

        {!loading && data.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
            {['전체', ...allCats].map(cat => (
              <button
                key={cat}
                className={`cat-filter-btn${cat === '전체' ? (activeCats.size === 0 ? ' active' : '') : (activeCats.has(cat) ? ' active' : '')}`}
                onClick={() => toggleCat(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        )}

        <div className="insight-table-wrap">
          {loading ? (
            <div className="loading">불러오는 중...</div>
          ) : !data.length ? (
            <div className="empty">해당 기간에 반복 인입 없음</div>
          ) : !rows.length ? (
            <div className="empty">해당 분류의 반복 인입 없음</div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th style={{ width: 120 }}>학부모 번호</th>
                  <th style={{ width: 80 }}>인입 횟수</th>
                  <th>최근 메모</th>
                  <th style={{ width: 130 }}>최근 접수</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const isTop = i < 3
                  const isOpen = expanded.has(i)
                  const latestMemo = r.memos?.[0]?.memo ?? ''
                  const preview = latestMemo.replace(/\n/g, ' ').slice(0, 80)

                  return (
                    <Fragment key={i}>
                      <tr>
                        <td><span className={`rank-badge${isTop ? ' top' : ''}`}>{i + 1}</span></td>
                        <td style={{ fontSize: 13, color: '#374151', fontWeight: 600 }}>{r.parent_id}</td>
                        <td><span className="count-badge">{r.cs_count}건</span></td>
                        <td style={{ color: '#374151', fontSize: 13 }}>
                          {preview}{latestMemo.length > 80 ? '…' : ''}
                          {r.memos?.length > 0 && (
                            <>
                              <br />
                              <button className="memo-toggle" onClick={() => toggleExpand(i)}>
                                {isOpen ? '▼ 접기' : `▶ 전체 이력 보기 (${r.memos.length}건)`}
                              </button>
                            </>
                          )}
                        </td>
                        <td style={{ whiteSpace: 'nowrap', color: '#64748b', fontSize: 12 }}>{r.latest_date ? r.latest_date.slice(0, 16) : '—'}</td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <td colSpan={5} style={{ padding: 0 }}>
                            <div className="memo-expand-inner">
                              {r.memos.map((m, mi) => (
                                <div key={mi} className="memo-item">
                                  <div className="memo-item-date">{m.date ? m.date.slice(0, 16) : '—'} · {m.category || ''}</div>
                                  <div>{m.memo ? m.memo.split('\n').map((line, li) => <span key={li}>{li > 0 && <br />}{line}</span>) : ''}</div>
                                </div>
                              ))}
                            </div>
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
