// @vitest-environment jsdom
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { HostBridge } from '../src/lib/host'
import CustomerDetail from '../src/screens/customer/detail'
import ContextDetail from '../src/screens/customer/context'

function makeHost(can: (scope: string, action?: string) => boolean = () => true) {
  const get = vi.fn(async (_route: string, _params?: Record<string, unknown>) => ({ list: [] }))
  const post = vi.fn(async () => ({}))
  const patch = vi.fn(async () => ({}))
  const getOutboundState = vi.fn(async () => ({ paused: null, status: 'unknown' as const }))
  const host = {
    api: { get, post, patch },
    can,
    navigate: vi.fn(),
    translate: (label: string) => label,
    notify: vi.fn(),
    currentUserId: null,
    getOutboundState,
  } as HostBridge
  return { host, get, post, patch, getOutboundState }
}

describe('customer and native context screens', () => {
  it('does not request a forbidden related entity or expose its links', async () => {
    const { host, get, post, patch } = makeHost(scope => scope !== 'ExternalConversation')
    get.mockImplementation(async route => route === 'Task'
      ? { list: [{ id: 'task/1', name: 'Follow up' }] }
      : { list: [{ id: 'secret', name: 'Private buyer' }] })
    const { container } = render(<CustomerDetail host={host} data={{
      type: 'Account', id: 'account/1', attributes: { name: 'Example buyer' },
    }} screen="customer-detail" />)
    await screen.findByRole('link', { name: 'Follow up' })
    expect(get).toHaveBeenCalledTimes(1)
    expect(get.mock.calls[0][0]).toBe('Task')
    expect(container.querySelector('a[href^="#ExternalConversation/"]')).toBeNull()
    expect(screen.queryByText('Private buyer')).toBeNull()
    expect(post).not.toHaveBeenCalled()
    expect(patch).not.toHaveBeenCalled()
  })

  it('uses bounded queries, renders real badges, and escapes customer text', async () => {
    const { host, get } = makeHost()
    get.mockImplementation(async route => route === 'ExternalConversation'
      ? { list: [{ id: 'conv/1', name: '<buyer>', status: 'pending', needsManualMatch: true }] }
      : { list: [] })
    const { container } = render(<CustomerDetail host={host} data={{
      type: 'Contact', id: 'contact/1', attributes: { name: '<contact>' },
    }} screen="customer-detail" />)
    await screen.findByRole('link', { name: '<buyer>' })
    const calls = get.mock.calls as unknown as [string, { maxSize: number; where: { attribute: string; value: string }[] }][]
    expect(calls.find(([route]) => route === 'ExternalConversation')?.[1].where[0]).toEqual({
      type: 'equals', attribute: 'contactId', value: 'contact/1',
    })
    expect(calls.every(([, params]) => params.maxSize <= 20)).toBe(true)
    expect(container.querySelector('[data-slot="badge"]')).not.toBeNull()
    expect(container.querySelector('script')).toBeNull()
    expect(screen.getAllByText('<contact>').length).toBeGreaterThan(0)
    expect(screen.getByText('客户匹配待人工确认')).not.toBeNull()
  })

  it('does not claim sending is paused when the status request fails', async () => {
    const { host, getOutboundState } = makeHost(() => false)
    getOutboundState.mockRejectedValue(new Error('offline'))
    render(<ContextDetail host={host} data={{ type: 'AIReplyDraft', conversationId: 'secret', riskLevel: 'high' }} screen="context-detail" />)
    await waitFor(() => expect(screen.getByText('外发开关状态未知（无法读取状态接口），请勿假定任务不会实际发送。')).not.toBeNull())
    expect(screen.queryByRole('link', { name: '打开会话审核' })).toBeNull()
    expect(screen.getByText('包含价格、MOQ、交期、认证、付款、折扣或承诺信息，需要人工确认。')).not.toBeNull()
  })
})
