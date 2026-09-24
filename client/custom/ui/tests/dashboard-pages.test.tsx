// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { HostBridge } from '../src/lib/host'
import HomeScreen, { loadHome } from '../src/screens/dashboard/home'
import CrmScreen, { loadCrm } from '../src/screens/dashboard/crm'

afterEach(cleanup)

function makeHost(readable: string[] = ['Account', 'Contact', 'Lead', 'Task', 'ExternalConversation', 'AIReplyDraft', 'ExternalIdentity', 'OutboundTask']) {
  const get = vi.fn(async (_route: string, params?: Record<string, unknown>) => params?.maxSize === 1
    ? { total: 0, list: [] } : { total: 0, list: [] })
  const post = vi.fn(async () => ({}))
  const patch = vi.fn(async () => ({}))
  const host = { api: { get, post, patch }, can: (scope: string) => readable.includes(scope),
    navigate: vi.fn(), translate: (label: string) => label, notify: vi.fn(), currentUserId: 'u-1',
    getOutboundState: vi.fn(async () => ({ paused: null, status: 'unknown' as const })),
  } as HostBridge
  return { host, get, post, patch }
}

describe('home and CRM dashboard', () => {
  it('does not read denied scopes and keeps a denied count distinct from zero', async () => {
    const { host, get, post, patch } = makeHost(['Account'])
    const home = await loadHome(host)
    const crm = await loadCrm(host)
    expect(home.counts.accounts).toEqual({ kind: 'ok', value: 0 })
    expect(home.counts.conversations).toEqual({ kind: 'denied' })
    expect(crm.counts.contacts).toEqual({ kind: 'denied' })
    expect(get.mock.calls.every(([route]) => route === 'Account')).toBe(true)
    expect(post).not.toHaveBeenCalled()
    expect(patch).not.toHaveBeenCalled()
  })

  it('shows only authorized workspace links and safe recent records', async () => {
    const { host, get } = makeHost(['Account'])
    get.mockImplementation(async (route, params) => route === 'Account' && params?.maxSize === 6
      ? { list: [{ id: 'a/1', name: '<Acme>', assignedUserName: 'Owner' }], total: 1 }
      : { total: 0, list: [] })
    const { container } = render(<HomeScreen host={host} data={null} screen="home" />)
    await screen.findByRole('link', { name: '<Acme>' })
    expect(screen.getByRole('link', { name: /CRM 工作台/ }).getAttribute('href')).toBe('#Home/crm')
    expect(screen.queryByRole('link', { name: /AI 客服工作台/ })).toBeNull()
    expect(screen.queryByRole('link', { name: '查看老板页' })).toBeNull()
    expect(screen.getByRole('link', { name: '<Acme>' }).getAttribute('href')).toBe('#Account/view/a%2F1')
    expect(container.querySelector('script')).toBeNull()
  })

  it('preserves unknown and errors without rendering them as zero', async () => {
    const { host, get } = makeHost(['Account', 'Task'])
    get.mockImplementation(async (route, params) => {
      if (route === 'Task') throw new Error('unavailable')
      return params?.maxSize === 1 ? { total: undefined } : { list: [] }
    })
    const result = await loadCrm(host)
    expect(result.counts.accounts.kind).toBe('error')
    expect(result.counts.tasks.kind).toBe('error')
    const { container } = render(<CrmScreen host={host} data={null} screen="crm" />)
    await waitFor(() => expect(container.querySelectorAll('[aria-label$="：未知"]').length).toBeGreaterThan(0))
    expect(screen.queryByRole('link', { name: '历史客户与今日建议' })).toBeNull()
    expect(screen.getAllByText('无法加载记录').length).toBeGreaterThan(0)
  })

  it('filters completed tasks from the open task section without changing the assigned total', async () => {
    const { host, get } = makeHost(['Task'])
    get.mockImplementation(async (route, params) => route === 'Task' && params?.maxSize === 6
      ? { list: [{ id: 't-1', name: 'Done', status: 'Completed' }, { id: 't-2', name: 'Follow up', status: 'Not Started' }] }
      : { total: route === 'Task' ? 2 : 0, list: [] })
    const result = await loadCrm(host)
    expect(result.counts.tasks).toEqual({ kind: 'ok', value: 2 })
    expect(result.sections.tasks).toEqual({ kind: 'ok', value: [{ id: 't-2', name: 'Follow up', status: 'Not Started' }] })
  })

  it('refreshes through a read request and never writes', async () => {
    const { host, get, post, patch } = makeHost(['Account'])
    render(<CrmScreen host={host} data={null} screen="crm" />)
    await screen.findByRole('button', { name: '刷新' })
    const before = get.mock.calls.length
    fireEvent.click(screen.getByRole('button', { name: '刷新' }))
    await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(before))
    expect(post).not.toHaveBeenCalled()
    expect(patch).not.toHaveBeenCalled()
  })
})
