const BASE = '/api/v1'

export interface ApiErrorBody {
  code: string
  message: string
  details: Record<string, unknown>
}

export interface ApiEnvelope<T> {
  data: T | null
  meta: Record<string, unknown>
  error: ApiErrorBody | null
}

export class ApiError extends Error {
  code: string
  status: number
  details: Record<string, unknown>

  constructor(status: number, error: ApiErrorBody) {
    super(error.message)
    this.name = 'ApiError'
    this.status = status
    this.code = error.code
    this.details = error.details
  }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, options)
  const body = await res.json() as ApiEnvelope<T>

  if (!res.ok || body.error) {
    throw new ApiError(
      res.status,
      body.error ?? {
        code: `HTTP_${res.status}`,
        message: res.statusText,
        details: {},
      },
    )
  }

  return body.data as T
}

export interface NoteSummary {
  file_id: string
  title: string
  description: string | null
  category: string | null
  tags: string[]
  created_at: string | null
  updated_at: string | null
  status: string
  source_project: string | null
  source_path: string | null
  source_context: string | null
  content_type: string
}

export interface NoteDetail extends NoteSummary {
  content: string
  attachments: string[]
}

export type SearchMode = 'fulltext' | 'semantic' | 'hybrid'

export interface RAGSource {
  file_id: string
  title: string
  snippet: string
  source_project: string | null
  source_path: string | null
  content_type: string
  attachments: string[]
}

export type Note = NoteSummary & {
  content?: string
  attachments?: string[]
}

export interface SearchResult {
  note: NoteSummary
  score: number | null
  source: string
  chunk_text: string | null
}

export interface CountItem {
  name: string
  count: number
  label?: string | null
}

export interface Taxonomy {
  tags: string[]
  categories: CountItem[]
  source_projects: CountItem[]
  content_types: CountItem[]
}

export interface DashboardStats {
  notes_count: number
  attachments_count: number
  source_projects: CountItem[]
  content_types: CountItem[]
  index_health: {
    notes_count: number
    vectors_count: number
    coverage: number
  }
}

export interface SourceItem {
  name: string
  label: string
  description: string
  icon: string
}

export interface SourcesResponse {
  sources: SourceItem[]
}

export interface DashboardActivityItem {
  kind: string
  title: string
  description: string
  timestamp: string | null
  note: {
    file_id: string
    title: string
    source_project: string | null
  }
}

export const api = {
  listNotes(params?: {
    category?: string
    tag?: string
    source_project?: string
    limit?: number
    offset?: number
  }) {
    const qs = new URLSearchParams()
    if (params?.category) qs.set('category', params.category)
    if (params?.tag) qs.set('tag', params.tag)
    if (params?.source_project) qs.set('source_project', params.source_project)
    if (params?.limit) qs.set('limit', String(params.limit))
    if (params?.offset) qs.set('offset', String(params.offset))
    const q = qs.toString()
    return request<NoteSummary[]>(`/notes${q ? '?' + q : ''}`)
  },

  getNote(fileId: string) {
    return request<NoteDetail>(`/notes/${encodeURIComponent(fileId)}`)
  },

  createNote(data: {
    title: string
    content?: string
    category?: string
    tags?: string[]
    description?: string | null
    source_project?: string | null
    source_path?: string | null
    source_context?: string | null
    content_type?: string
  }) {
    return request<NoteDetail>('/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  },

  updateNote(fileId: string, data: Partial<NoteDetail>) {
    return request<NoteDetail>(`/notes/${encodeURIComponent(fileId)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  },

  deleteNote(fileId: string) {
    return request<{ ok: boolean }>(`/notes/${encodeURIComponent(fileId)}`, {
      method: 'DELETE',
    })
  },

  search(q: string, mode: SearchMode = 'fulltext', limit?: number) {
    const qs = new URLSearchParams({ q, mode })
    if (limit) qs.set('limit', String(limit))
    return request<SearchResult[]>(`/search?${qs}`)
  },

  uploadAttachment(file: File) {
    const formData = new FormData()
    formData.set('file', file)
    return request<{ path: string }>('/attachments', {
      method: 'POST',
      body: formData,
    })
  },

  getTags() {
    return request<Taxonomy>('/taxonomy').then((taxonomy) => ({ tags: taxonomy.tags }))
  },

  getCategories() {
    return request<Taxonomy>('/taxonomy').then((taxonomy) => ({
      categories: taxonomy.categories.map((item) => item.name),
    }))
  },

  triggerIndex() {
    return request<{ indexed: number; vectors: number }>('/index/rebuild', { method: 'POST' })
  },

  getRelatedNotes(fileId: string, limit?: number) {
    const qs = limit ? `?limit=${limit}` : ''
    return request<SearchResult[]>(`/notes/${encodeURIComponent(fileId)}/related${qs}`)
  },

  getIndexStatus() {
    return request<DashboardStats>('/dashboard').then((stats) => ({
      notes_count: stats.index_health.notes_count,
    }))
  },

  getAttachmentsStats() {
    return request<DashboardStats>('/dashboard').then((stats) => ({
      count: stats.attachments_count,
    }))
  },

  getCategoriesWithCount() {
    return request<Taxonomy>('/taxonomy').then((taxonomy) => ({
      categories: taxonomy.categories,
    }))
  },

  getSourceProjects() {
    return request<DashboardStats>('/dashboard').then((stats) => ({
      projects: stats.source_projects,
    }))
  },

  getSources() {
    return request<SourcesResponse>('/sources').then((data) => data.sources)
  },

  getContentTypeStats() {
    return request<DashboardStats>('/dashboard').then((stats) => ({
      content_types: stats.content_types,
    }))
  },

  getIndexHealth() {
    return request<DashboardStats>('/dashboard').then((stats) => stats.index_health)
  },

  getDashboardActivity(params?: { limit?: number }) {
    const qs = new URLSearchParams()
    if (params?.limit) qs.set('limit', String(params.limit))
    const q = qs.toString()
    return request<DashboardActivityItem[]>(`/dashboard/activity${q ? '?' + q : ''}`)
  },

  chatAsk(query: string, top_k?: number) {
    return request<{
      answer: string
      model: string
      tokens_used: number | null
      sources: RAGSource[]
    }>('/chat/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k: top_k ?? 5 }),
    })
  },
}
