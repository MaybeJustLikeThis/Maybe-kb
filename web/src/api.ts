const BASE = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, options)
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`)
  }
  return res.json()
}

export interface Note {
  file_id: string
  title: string
  description: string | null
  content: string
  category: string | null
  tags: string[]
  attachments: string[]
  created_at: string | null
  updated_at: string | null
  status: string
}

export const api = {
  listNotes(params?: { category?: string; tag?: string; limit?: number }) {
    const qs = new URLSearchParams()
    if (params?.category) qs.set('category', params.category)
    if (params?.tag) qs.set('tag', params.tag)
    if (params?.limit) qs.set('limit', String(params.limit))
    const q = qs.toString()
    return request<Note[]>(`/notes${q ? '?' + q : ''}`)
  },

  getNote(fileId: string) {
    return request<Note>(`/notes/${encodeURIComponent(fileId)}`)
  },

  createNote(data: { title: string; content?: string; category?: string; tags?: string[] }) {
    return request<Note>('/notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  },

  updateNote(fileId: string, data: Partial<Note>) {
    return request<Note>(`/notes/${encodeURIComponent(fileId)}`, {
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

  search(q: string, limit?: number) {
    const qs = new URLSearchParams({ q })
    if (limit) qs.set('limit', String(limit))
    return request<Note[]>(`/search?${qs}`)
  },

  getTags() {
    return request<{ tags: string[] }>('/tags')
  },

  getCategories() {
    return request<{ categories: string[] }>('/categories')
  },

  triggerIndex() {
    return request<{ indexed: number }>('/index', { method: 'POST' })
  },

  getRelatedNotes(fileId: string, limit?: number) {
    const qs = limit ? `?limit=${limit}` : ''
    return request<Array<Note & { score: number }>>(`/notes/${encodeURIComponent(fileId)}/related${qs}`)
  },

  getAttachmentsStats() {
    return request<{ count: number }>('/attachments/stats')
  },

  getCategoriesWithCount() {
    return request<{ categories: Array<{ name: string; count: number }> }>('/categories?with_count=1')
  },

  chatAsk(query: string, top_k?: number) {
    return request<{ answer: string; model: string; tokens_used: number }>('/chat/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, top_k: top_k ?? 5 }),
    })
  },
}
