// @vitest-environment jsdom
import { render, screen as dom, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { HostBridge } from '../src/lib/host'
import ServiceScreen, { loadServiceSnapshot, parseOutboundState } from '../src/screens/dashboard/service'

function makeHost(canRead: (scope: string) => boolean = () => true) {
  const get = vi.fn(async (_route: string, _params?: Record<string, unknown>) => ({ total: 0, list: [] }))
  const post = vi.fn(async () => ({}))
  const patch = vi.fn(async () => ({}))
  const getOutboundState = vi.fn(async () => ({ paused: true, status: 'paused' as const }))
  const host = {
    api: { get, post, patch },
    can: (scope) => canRead(scope),
    navigate: vi.fn(),
    translate: (label) => label,
    notify: vi.fn(),
    currentUserId: null,
    getOutboundState,
  } as unknown as HostBridge
  return { host, get, post, patch, getOutboundState }
}

describe('service dashboard read contract', () => {
  it('never requests forbidden scopes or writes anything', async () => {
    const { host, get, post, patch, getOutboundState } = makeHost(() => false)
    const result = await loadServiceSnapshot(host)
    expect(get).not.toHaveBeenCalled()
    expect(post).not.toHaveBeenCalled()
    expect(patch).not.toHaveBeenCalled()
    expect(getOutboundState).not.toHaveBeenCalled()
    expect(result.counts.all.kind).toBe('denied')
    expect(result.sections.agents.kind).toBe('denied')
    expect(result.outbound).toBeNull()
  })

  it('queries only bounded totals and six recent records, preserving zero', async () => {
    const { host, get, post, patch } = makeHost()
    const result = await loadServiceSnapshot(host)
    expect(result.counts.all).toEqual({ kind: 'ok', value: 0 })
    expect(result.outbound).toBe(true)
    expect(get).toHaveBeenCalledTimes(12)
    const calls = get.mock.calls as unknown as [string, { maxSize: number; where: unknown[] }][]
    expect(calls.slice(0, 6).every(([, params]) => params.maxSize === 1)).toBe(true)
    expect(calls.slice(6).every(([, params]) => params.maxSize === 6)).toBe(true)
    expect(calls.find(([route]) => route === 'ExternalIdentity')?.[1].where).toEqual([
      { type: 'equals', attribute: 'linkStatus', value: 'unlinked' },
    ])
    expect(post).not.toHaveBeenCalled()
    expect(patch).not.toHaveBeenCalled()
  })

  it('keeps a failed section and unknown outbound state distinct from zero', async () => {
    const { host, get, getOutboundState } = makeHost()
    get.mockImplementation(async (route) => {
      if (route === 'AIReplyDraft') throw new Error('temporarily unavailable')
      return { total: 0, list: [] }
    })
    getOutboundState.mockResolvedValue({ paused: null, status: 'unknown' })
    const result = await loadServiceSnapshot(host)
    expect(result.counts.review.kind).toBe('error')
    expect(result.sections.drafts.kind).toBe('error')
    expect(result.counts.all).toEqual({ kind: 'ok', value: 0 })
    expect(result.outbound).toBeNull()
  })

  it('accepts only an explicit boolean from the checked outbound bridge', () => {
    expect(parseOutboundState({ paused: true })).toBe(true)
    expect(parseOutboundState({ paused: false })).toBe(false)
    expect(parseOutboundState({ paused: 0 })).toBeNull()
    expect(parseOutboundState({ outboundPaused: false })).toBeNull()
    expect(parseOutboundState(null)).toBeNull()
  })

  it('renders the real shadcn table, badge and alert with safe record text', async () => {
    const { host, get, getOutboundState } = makeHost()
    get.mockImplementation(async (route, params) => {
      if (route === 'ExternalConversation') {
        return params?.maxSize === 1
          ? { total: 1, list: [] }
          : { total: 1, list: [{ id: 'buyer/1', name: '<buyer>', status: 'pending' }] }
      }
      return { total: 0, list: [] }
    })
    getOutboundState.mockResolvedValue({ paused: null, status: 'unknown' })
    const { container } = render(<ServiceScreen host={host} data={null} screen="service" />)
    await dom.findByRole('link', { name: '<buyer>' })
    expect(container.querySelector('[data-slot="table"]')).not.toBeNull()
    expect(container.querySelector('[data-slot="badge"]')).not.toBeNull()
    expect(container.querySelector('[data-slot="alert"]')).not.toBeNull()
    expect(dom.getByRole('link', { name: '<buyer>' }).getAttribute('href')).toBe('#ExternalConversation/view/buyer%2F1')
    await waitFor(() => expect(dom.getByText('外发开关状态未知')).not.toBeNull())
    expect(container.querySelector('script')).toBeNull()
  })

  it('does not expose conversation links when draft access is narrower than conversation access', async () => {
    const { host, get } = makeHost((scope) => scope !== 'ExternalConversation')
    get.mockImplementation(async (route, params) => {
      if (route === 'AIReplyDraft' && params?.maxSize === 6) {
        return { total: 1, list: [{ id: 'draft-1', name: '待审草稿',
          conversationId: 'secret-1', conversationName: 'Private buyer', riskLevel: 'high' }] }
      }
      return { total: 0, list: [] }
    })
    const { container } = render(<ServiceScreen host={host} data={null} screen="service" />)
    await dom.findByRole('link', { name: '待审草稿' })
    expect(container.querySelector('a[href^="#ExternalConversation/view/"]')).toBeNull()
    expect(container.querySelector('a[href="#Home/insights"]')).toBeNull()
    expect(dom.queryByText('Private buyer')).toBeNull()
  })
})
