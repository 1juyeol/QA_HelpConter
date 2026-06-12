// 서비스 품질 지수(SQI)와 고객 언어 온도 인사이트 페이지.
// SQI: 전체 CS 대비 리스크 카테고리(네트워크·앱 오류, 기기·하드웨어 오류, 미납 관리 등) 건수 비율.
// 언어 온도: 부정 감정 키워드 포함 메모 비율 — 기술 지표와 별개로 고객 불만 강도를 측정한다.
// SQI = ALLOWED 카테고리 건수 ÷ 전체 CS 건수 × 100
// 언어 온도 = 부정 키워드 포함 메모 건수 ÷ 전체 CS 건수 × 100
// 기준선은 최근 4주 중 첫 2주 평균으로 자동 설정하며, 초과 주는 빨간색으로 강조한다.
// 데이터 소스: /api/stats/weekly, /api/stats/category_weekly, /api/stats/sentiment_weekly
// ALLOWED 기준: RepeatParents.tsx의 ALLOWED_MAIN·ALLOWED_SPECIFIC와 동일하게 유지해야 한다.
import { useEffect, useRef, useState } from 'react'
import Chart from 'chart.js/auto'
import { api, type WeeklyCategoryRow, type SentimentWeeklyRow } from '../../api/client'
import { FILTER_TREE, isAllowed } from '../../api/categories'

const NEGATIVE_KEYWORDS = [
  '환불', '해지', '짜증', '불만', '화가', '실망',
  '황당', '어이없', '도저히', '고소', '소비자원', '몇 번이나',
  '도대체', '말도 안', '최악', '사기', '억울', '피해',
  '항의', '제발', '못 참', '엉터리',
  '변호사', '공정위', '납득', '무책임', '거짓말', '보상', '다시는', '강력',
]

type WeekData = { label: string; sqi: number }
type SentimentData = { label: string; rate: number }

function makeLineChartConfig(
  data: number[],
  labels: string[],
  baseline: number,
  lineColor: string,
  datasetLabel: string,
) {
  return {
    type: 'line' as const,
    data: {
      labels,
      datasets: [
        {
          label: datasetLabel,
          data,
          borderColor: lineColor,
          backgroundColor: 'transparent',
          pointBackgroundColor: data.map(v => v > baseline ? '#ef4444' : lineColor),
          pointRadius: 5,
          tension: 0.3,
          segment: {
            borderColor: (ctx: any) => (data[ctx.p1DataIndex] ?? 0) > baseline ? '#ef4444' : lineColor,
          },
        },
        {
          label: `기준선 (${baseline.toFixed(1)}%)`,
          data: labels.map(() => parseFloat(baseline.toFixed(1))),
          borderColor: '#94a3b8',
          borderDash: [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          backgroundColor: 'transparent',
        },
      ],
    },
    options: {
      plugins: {
        legend: { position: 'bottom' as const, labels: { boxWidth: 12, font: { size: 11 } } },
        tooltip: { callbacks: { label: (ctx: any) => `${ctx.dataset.label}: ${ctx.parsed.y}%` } },
      },
      scales: {
        y: { min: 0, ticks: { callback: (v: any) => `${v}%`, font: { size: 11 } } },
        x: { ticks: { font: { size: 11 } } },
      },
    },
  }
}

function KpiCard({ label, value, baseline }: { label: string; value: number; baseline: number }) {
  const isHigh = value > baseline
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ background: '#f8fafc', borderRadius: 12, padding: '20px 28px', border: '1px solid #e2e8f0', display: 'inline-block', minWidth: 160 }}>
        <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 6 }}>{label}</div>
        <div style={{ fontSize: 32, fontWeight: 700, color: isHigh ? '#ef4444' : '#0f172a' }}>
          {value}%
        </div>
        <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
          기준 {baseline.toFixed(1)}% 대비{' '}
          <span style={{ color: isHigh ? '#ef4444' : '#10b981', fontWeight: 600 }}>
            {isHigh
              ? `▲ ${(value - baseline).toFixed(1)}%p`
              : `▼ ${(baseline - value).toFixed(1)}%p`}
          </span>
        </div>
      </div>
    </div>
  )
}

export default function InsightsSummary() {
  const [loading, setLoading] = useState(true)
  const [weeks, setWeeks] = useState<WeekData[]>([])
  const [sentimentWeeks, setSentimentWeeks] = useState<SentimentData[]>([])

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const chartRef = useRef<Chart | null>(null)
  const sentimentCanvasRef = useRef<HTMLCanvasElement>(null)
  const sentimentChartRef = useRef<Chart | null>(null)

  useEffect(() => { load() }, [])

  async function load() {
    setLoading(true)
    try {
      const today = new Date().toISOString().slice(0, 10)
      const [weeklyData, categoryData, sentimentData] = await Promise.all([
        api.fetchWeekly(today),
        api.fetchCategoryWeekly(today),
        api.fetchSentimentWeekly(today),
      ])

      const totalMap: Record<string, number> = {}
      weeklyData.forEach(r => { totalMap[r.week_start] = r.count })

      const allowedMap: Record<string, number> = {}
      categoryData.forEach((r: WeeklyCategoryRow) => {
        if (!isAllowed(r.main, r.sub)) return
        allowedMap[r.week_start] = (allowedMap[r.week_start] ?? 0) + r.count
      })

      const sorted = Object.keys(totalMap).sort()
      setWeeks(sorted.map(w => ({
        label: w.slice(5).replace('-', '/'),
        sqi: totalMap[w] > 0 ? Math.round((allowedMap[w] ?? 0) / totalMap[w] * 1000) / 10 : 0,
      })))

      setSentimentWeeks(sentimentData.map((r: SentimentWeeklyRow) => ({
        label: r.week_start.slice(5).replace('-', '/'),
        rate: r.total > 0 ? Math.round(r.neg_count / r.total * 1000) / 10 : 0,
      })))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (loading || !weeks.length || !canvasRef.current) return
    chartRef.current?.destroy()
    const baseline = weeks.slice(0, 2).reduce((s, w) => s + w.sqi, 0) / Math.min(2, weeks.length)
    chartRef.current = new Chart(
      canvasRef.current,
      makeLineChartConfig(weeks.map(w => w.sqi), weeks.map(w => w.label), baseline, '#3b82f6', 'SQI'),
    )
  }, [loading, weeks])

  useEffect(() => {
    if (loading || !sentimentWeeks.length || !sentimentCanvasRef.current) return
    sentimentChartRef.current?.destroy()
    const baseline = sentimentWeeks.slice(0, 2).reduce((s, w) => s + w.rate, 0) / Math.min(2, sentimentWeeks.length)
    sentimentChartRef.current = new Chart(
      sentimentCanvasRef.current,
      makeLineChartConfig(sentimentWeeks.map(w => w.rate), sentimentWeeks.map(w => w.label), baseline, '#f59e0b', '언어 온도'),
    )
  }, [loading, sentimentWeeks])

  useEffect(() => () => {
    chartRef.current?.destroy()
    sentimentChartRef.current?.destroy()
  }, [])

  const latest = weeks[weeks.length - 1]
  const sqiBaseline = weeks.length > 0
    ? weeks.slice(0, 2).reduce((s, w) => s + w.sqi, 0) / Math.min(2, weeks.length)
    : null

  const latestSentiment = sentimentWeeks[sentimentWeeks.length - 1]
  const sentimentBaseline = sentimentWeeks.length > 0
    ? sentimentWeeks.slice(0, 2).reduce((s, w) => s + w.rate, 0) / Math.min(2, sentimentWeeks.length)
    : null

  return (
    <div className="container">
      {/* SQI 카드 */}
      <div className="section-card">
        <h2>서비스 품질 지수 <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 400 }}>최근 1달</span></h2>
        <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 12 }}>
          기기·앱 오류, 해지, 미납 등 회사 비용이 발생하는 CS가 전체에서 차지하는 비율이에요.
        </p>
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden', marginBottom: 20, fontSize: 12 }}>
          <div style={{ background: '#f8fafc', padding: '7px 14px', borderBottom: '1px solid #e2e8f0', color: '#94a3b8', fontWeight: 600, fontSize: 11, letterSpacing: '0.04em' }}>
            집계 기준
          </div>
          {FILTER_TREE.map(({ main, subs }, i, arr) => (
            <div key={main} style={{
              display: 'grid', gridTemplateColumns: '152px 1fr',
              padding: '9px 14px', alignItems: 'flex-start', gap: 8,
              borderBottom: i < arr.length - 1 ? '1px solid #f1f5f9' : undefined,
            }}>
              <span style={{ color: '#374151', fontWeight: 600, paddingTop: 3 }}>{main}</span>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {subs.map(sub => (
                  <span key={sub} style={{
                    background: '#f1f5f9', color: '#475569',
                    borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 500,
                  }}>{sub}</span>
                ))}
              </div>
            </div>
          ))}
        </div>

        {loading ? (
          <div className="loading">불러오는 중...</div>
        ) : !weeks.length ? (
          <div className="empty">데이터 없음</div>
        ) : (
          <>
            {latest && sqiBaseline != null && (
              <KpiCard label="이번 주 SQI" value={latest.sqi} baseline={sqiBaseline} />
            )}
            <canvas ref={canvasRef} />
          </>
        )}
      </div>

      {/* 고객 언어 온도 카드 */}
      <div className="section-card" style={{ marginTop: 16 }}>
        <h2>고객 언어 온도 <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 400 }}>최근 1달</span></h2>
        <p style={{ fontSize: 13, color: '#94a3b8', marginBottom: 12 }}>
          부정 감정 키워드가 포함된 메모 비율이에요. SQI와 함께 보면 기술 문제 없이 고객 불만이 쌓이는 시점을 포착할 수 있어요.
        </p>
        <div style={{ border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden', marginBottom: 20, fontSize: 12 }}>
          <div style={{ background: '#f8fafc', padding: '7px 14px', borderBottom: '1px solid #e2e8f0', color: '#94a3b8', fontWeight: 600, fontSize: 11, letterSpacing: '0.04em' }}>
            감지 키워드
          </div>
          <div style={{ padding: '10px 14px', display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {NEGATIVE_KEYWORDS.map(kw => (
              <span key={kw} style={{
                background: '#f1f5f9', color: '#475569',
                borderRadius: 4, padding: '2px 8px', fontSize: 11, fontWeight: 500,
              }}>{kw}</span>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="loading">불러오는 중...</div>
        ) : !sentimentWeeks.length ? (
          <div className="empty">데이터 없음</div>
        ) : (
          <>
            {latestSentiment && sentimentBaseline != null && (
              <KpiCard label="이번 주 언어 온도" value={latestSentiment.rate} baseline={sentimentBaseline} />
            )}
            <canvas ref={sentimentCanvasRef} />
          </>
        )}
      </div>
    </div>
  )
}
