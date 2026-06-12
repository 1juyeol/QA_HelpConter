// 학부모 반복 인입 인사이트 페이지. 30일 내 동일 학부모가 2회 이상 CS 인입한 목록을 테이블로 표시한다.
// 대분류 선택 → 해당 대분류 전체 소분류 조회 / 소분류 선택 → 해당 소분류 메모만 조회.
// 새로고침 버튼은 POST /api/insights/refresh → 재조회 순서로 동작한다.
// 이 컴포넌트 내부에서만 상태를 관리하며 다른 페이지와 상태를 공유하지 않는다 (정책 8).
import { Fragment, useEffect, useState } from 'react'
import { api, adminParentUrl, type InsightParent } from '../../api/client'

// 표시할 카테고리 계층. 여기 정의된 대분류·소분류만 필터 버튼에 노출된다.
const FILTER_TREE = [
  { main: '네트워크·앱 오류',   subs: ['와이파이 오류', '학습 끊김·멈춤', '앱 오류'] },
  { main: '기기·하드웨어 오류', subs: ['충전 불량', '터치·화면 불량', '전원·부팅 오류', '기기 파손', '기기 교체 요청'] },
  { main: '미납·결제',          subs: ['미납 관리', '결제·환불 처리'] },
  { main: '해지·유지 상담',     subs: ['해지 확정', '해지금·위약금 문의'] },
  { main: '교재·물류·배송',     subs: ['기기 장기미회수', '누락·오배송'] },
]

// 대분류 전체 허용
const ALLOWED_MAIN = new Set(['네트워크·앱 오류', '기기·하드웨어 오류', '미납·결제'])
// 소분류 단위 허용
const ALLOWED_SPECIFIC = new Set([
  '해지·유지 상담 > 해지 확정',
  '해지·유지 상담 > 해지금·위약금 문의',
  '교재·물류·배송 > 기기 장기미회수',
  '교재·물류·배송 > 누락·오배송',
])

type ActiveFilter = { main: string | null; sub: string | null }

function isQualified(r: InsightParent) {
  return r.memos.some(m => {
    const main = m.category.split(' > ')[0]
    return ALLOWED_MAIN.has(main) || ALLOWED_SPECIFIC.has(m.category)
  })
}

function memoMatches(category: string, f: ActiveFilter): boolean {
  if (!f.main) return true
  if (f.sub) return category === `${f.main} > ${f.sub}`
  if (ALLOWED_MAIN.has(f.main)) return category.startsWith(`${f.main} > `)
  return ALLOWED_SPECIFIC.has(category) && category.startsWith(`${f.main} > `)
}

export default function RepeatParents() {
  const [data, setData] = useState<InsightParent[]>([])
  const [updatedAt, setUpdatedAt] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [filter, setFilter] = useState<ActiveFilter>({ main: null, sub: null })
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const res = await api.fetchRepeatParents()
      setData((res.data || []).filter(isQualified))
      setUpdatedAt(res.updated_at ? `최근 30일 기준 · 업데이트: ${res.updated_at.slice(0, 16)}` : '')
      setFilter({ main: null, sub: null })
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

  function selectMain(main: string) {
    setFilter(prev => prev.main === main && !prev.sub ? { main: null, sub: null } : { main, sub: null })
    setExpanded(new Set())
  }

  function selectSub(main: string, sub: string) {
    setFilter(prev => prev.sub === sub ? { main, sub: null } : { main, sub })
    setExpanded(new Set())
  }

  function toggleExpand(i: number) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(i) ? next.delete(i) : next.add(i)
      return next
    })
  }

  function getDisplayCount(r: InsightParent) {
    if (filter.main) return r.memos.filter(m => memoMatches(m.category, filter)).length
    return r.memos.filter(m => {
      const main = m.category.split(' > ')[0]
      return ALLOWED_MAIN.has(main) || ALLOWED_SPECIFIC.has(m.category)
    }).length
  }

  const rows = [...(filter.main
    ? data.filter(r => r.memos.some(m => memoMatches(m.category, filter)))
    : data
  )].sort((a, b) => getDisplayCount(b) - getDisplayCount(a))

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
          <div style={{ marginBottom: 16 }}>
            {/* 대분류 버튼 행 */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
              {FILTER_TREE.map(({ main }) => (
                <button
                  key={main}
                  className={`cat-filter-btn${filter.main === main ? ' active' : ''}`}
                  onClick={() => selectMain(main)}
                >
                  {main}
                </button>
              ))}
            </div>
            {/* 선택된 대분류의 소분류 버튼 행 */}
            {filter.main && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, paddingLeft: 4 }}>
                {FILTER_TREE.find(t => t.main === filter.main)?.subs.map(sub => (
                  <button
                    key={sub}
                    className={`cat-filter-btn${filter.sub === sub ? ' active' : ''}`}
                    style={{ fontSize: 11, padding: '3px 10px', borderRadius: 6 }}
                    onClick={() => selectSub(filter.main!, sub)}
                  >
                    {sub}
                  </button>
                ))}
              </div>
            )}
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
                  <th style={{ width: 130 }}>최초 접수</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => {
                  const isTop = i < 3
                  const isOpen = expanded.has(i)
                  const qualifyingMemos = r.memos.filter(m => {
                    const main = m.category.split(' > ')[0]
                    return ALLOWED_MAIN.has(main) || ALLOWED_SPECIFIC.has(m.category)
                  })
                  const visibleMemos = filter.main
                    ? r.memos.filter(m => memoMatches(m.category, filter))
                    : qualifyingMemos
                  const latestMemo = visibleMemos[0]?.memo ?? ''
                  const preview = latestMemo.replace(/\n/g, ' ').slice(0, 80)
                  const displayCount = visibleMemos.length

                  return (
                    <Fragment key={i}>
                      <tr>
                        <td><span className={`rank-badge${isTop ? ' top' : ''}`}>{i + 1}</span></td>
                        <td style={{ fontSize: 13, fontWeight: 600 }}>
                          {r.parent_id
                            ? <a href={adminParentUrl(r.parent_id)} target="_blank" rel="noreferrer" style={{ color: '#1a56db', textDecoration: 'none' }}>{r.parent_id}</a>
                            : <span style={{ color: '#64748b' }}>—</span>}
                        </td>
                        <td><span className="count-badge">{displayCount}건</span></td>
                        <td style={{ color: '#374151', fontSize: 13 }}>
                          {preview}{latestMemo.length > 80 ? '…' : ''}
                          {visibleMemos.length > 0 && (
                            <>
                              <br />
                              <button className="memo-toggle" onClick={() => toggleExpand(i)}>
                                {isOpen ? '▼ 접기' : `▶ 전체 이력 보기 (${visibleMemos.length}건)`}
                              </button>
                            </>
                          )}
                        </td>
                        <td style={{ whiteSpace: 'nowrap', color: '#64748b', fontSize: 12 }}>
                          {visibleMemos[0]?.date ? visibleMemos[0].date.slice(0, 16) : '—'}
                        </td>
                        <td style={{ whiteSpace: 'nowrap', color: '#64748b', fontSize: 12 }}>
                          {visibleMemos[visibleMemos.length - 1]?.date ? visibleMemos[visibleMemos.length - 1].date.slice(0, 16) : '—'}
                        </td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <td colSpan={6} style={{ padding: 0 }}>
                            <div className="memo-expand-inner">
                              {visibleMemos.map((m, mi) => (
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
