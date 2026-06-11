// 모든 백엔드 API 호출과 TypeScript 타입을 한 곳에 모은다. 컴포넌트는 직접 fetch를 쓰지 않고 이 모듈만 참조한다.

// ── 타입 정의 ────────────────────────────────────────────────────

export interface BucketRow   { bucket: string; count: number }
export interface DailyRow    { date: string; count: number }
export interface WeeklyRow   { week_start: string; count: number }
export interface MonthlyRow  { month: string; count: number }

export interface CategoryRow {
  new_category_main: string
  new_category_sub: string
  count: number
}

export interface Issue {
  id: number
  created_date: string
  new_category_main: string | null
  new_category_sub: string | null
  call_memo: string
  student_id: string
  parent_id: string | null
}

export interface IssueList { total: number; items: Issue[] }

export interface InsightWings {
  ticket_id: string
  cs_count: number
  memos: { memo: string; date: string }[]
  first_date: string
  latest_date: string
}

export interface InsightParent {
  parent_id: string
  cs_count: number
  categories: string[]
  memos: { memo: string; date: string; category: string }[]
  latest_date: string
}

export interface CollectionLatest {
  collected_at: string
  target_date: string
  count: number
  status: string
}

// ── 기본 fetcher ─────────────────────────────────────────────────

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<T>
}

async function post<T>(url: string): Promise<T> {
  const r = await fetch(url, { method: 'POST' })
  if (!r.ok) throw new Error(await r.text())
  return r.json() as Promise<T>
}

// ── API 함수 ─────────────────────────────────────────────────────

export const api = {
  fetchHourly(startDate: string, endDate: string) {
    return get<BucketRow[]>(`/api/stats/hourly_range?start_date=${startDate}&end_date=${endDate}`)
  },

  fetchDaily(targetDate: string, period = 'week') {
    return get<DailyRow[]>(`/api/stats/daily?target_date=${targetDate}&period=${period}`)
  },

  fetchWeekly(targetDate: string) {
    return get<WeeklyRow[]>(`/api/stats/weekly?target_date=${targetDate}`)
  },

  fetchMonthly(targetDate: string) {
    return get<MonthlyRow[]>(`/api/stats/monthly?target_date=${targetDate}`)
  },

  fetchCategory(params: {
    startDate?: string
    endDate?: string
    targetDate?: string
    period?: string
    bucket?: string
  }) {
    const p = new URLSearchParams()
    if (params.startDate) p.set('start_date', params.startDate)
    if (params.endDate)   p.set('end_date',   params.endDate)
    if (params.targetDate) p.set('target_date', params.targetDate)
    if (params.period)    p.set('period',      params.period)
    if (params.bucket)    p.set('bucket',      params.bucket)
    return get<CategoryRow[]>(`/api/stats/category?${p}`)
  },

  fetchIssues(params: {
    startDate?: string
    endDate?: string
    targetDate?: string
    period?: string
    bucket?: string
    categoryMain?: string
    categorySub?: string
    unclassified?: boolean
    limit?: number
    offset?: number
  }) {
    const p = new URLSearchParams()
    if (params.startDate)    p.set('start_date',     params.startDate)
    if (params.endDate)      p.set('end_date',       params.endDate)
    if (params.targetDate)   p.set('target_date',    params.targetDate)
    if (params.period)       p.set('period',         params.period)
    if (params.bucket)       p.set('bucket',         params.bucket)
    if (params.categoryMain) p.set('category_main',  params.categoryMain)
    if (params.categorySub)  p.set('category_sub',   params.categorySub)
    if (params.unclassified) p.set('unclassified',   '1')
    if (params.limit  != null) p.set('limit',  String(params.limit))
    if (params.offset != null) p.set('offset', String(params.offset))
    return get<IssueList>(`/api/issues?${p}`)
  },

  fetchWingsTickets() {
    return get<{ data: InsightWings[]; updated_at: string | null }>('/api/insights/wings_tickets')
  },

  fetchRepeatParents() {
    return get<{ data: InsightParent[]; updated_at: string | null }>('/api/insights/repeat_parents')
  },

  refreshInsights() {
    return post<{ status: string }>('/api/insights/refresh')
  },

  fetchLatestCollection() {
    return get<CollectionLatest>('/api/collection/latest')
  },
}
