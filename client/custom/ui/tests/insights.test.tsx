// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { HostBridge } from '../src/lib/host'
import InsightsScreen from '../src/screens/insights/insights'
import english from '../../../../custom/Espo/Custom/Resources/i18n/en_US/Fusanhe.json'

afterEach(cleanup)

const overview = {
  date: '2026-09-24', outboundPaused: null, scope: 'own',
  coverage: { platformVisible: null, imported: 0, failedSync: null, pendingIdentity: 1,
    analysisCompleted: 0, analysisFailed: 0, analysisStale: 0, lastSyncAt: '2026-09-23 15:42:00',
    reason: '待采集端提供完整分页及消息对账；平台可见总数和未入库失败数未知。仅统计带同步来源的 Alibaba 会话。' },
  suggestionTotal: 1,
  suggestions: [{ id: 'conv/1', name: '<buyer>', priority: 1, reason: '身份尚未确认', action: '核对平台身份与客户关联后再跟进', owner: 'Owner' }],
  list: [{ id: 'conv/1', name: '<buyer>', externalId: 'ext-1', needsManualMatch: true, owner: 'Owner', analysisStatus: 'stale', customer: { type: 'Account', id: 'a-1' } }],
  total: 30,
}

function makeHost(read = true) {
  const get = vi.fn(async (route: string) => route.startsWith('Fusanhe/insights/')
    ? { id: 'conv/1', name: '<buyer>', analysisStatus: 'stale', analysisNotice: '匿名信号分析，业务事实请核对原文。',
      analysis: { summaryZh: '<script>alert(1)</script>', missingFacts: ['真实采购量'] }, model: 'test-model',
      evidence: [{ id: 'msg/1', sentAt: '2026-09-24 02:00:00', direction: 'inbound' }] }
    : overview)
  const post = vi.fn(async () => ({}))
  const patch = vi.fn(async () => ({}))
  const host = { api: { get, post, patch }, can: (scope: string) => read && ['ExternalConversation', 'Account', 'ExternalMessage'].includes(scope),
    navigate: vi.fn(), translate: (key: string) => key, notify: vi.fn(), currentUserId: 'u-1',
    getOutboundState: vi.fn(async () => ({ paused: null, status: 'unknown' as const })),
  } as HostBridge
  return { host, get, post, patch }
}

describe('boss insights workbench', () => {
  it('keeps unknown coverage distinct from zero and makes no request without ACL', async () => {
    const denied = makeHost(false)
    const view = render(<InsightsScreen host={denied.host} data={null} screen="insights" />)
    await screen.findByText('没有读取权限')
    expect(denied.get).not.toHaveBeenCalled()
    view.unmount()

    const allowed = makeHost()
    render(<InsightsScreen host={allowed.host} data={null} screen="insights" />)
    await screen.findByText('平台可见会话')
    expect(screen.getByLabelText('平台可见会话：待核对')).not.toBeNull()
    expect(screen.getByLabelText('已导入会话：0')).not.toBeNull()
    expect(screen.getByText('外发状态未知。本页不会发送消息；请先核查发送开关。')).not.toBeNull()
    expect(screen.getByText(/2026-09-23 23:42 UTC\+8/)).not.toBeNull()
  })

  it('preserves search, paging and source evidence links without writes', async () => {
    const { host, get, post, patch } = makeHost()
    const { container } = render(<InsightsScreen host={host} data={null} screen="insights" />)
    await screen.findByRole('button', { name: '查看分析：<buyer>' })
    fireEvent.change(screen.getByLabelText('搜索'), { target: { value: 'buyer' } })
    fireEvent.click(screen.getByRole('button', { name: '查询 / 刷新' }))
    await waitFor(() => expect(get.mock.calls.some(([route, params]) => route === 'Fusanhe/insights' && params?.q === 'buyer' && params?.offset === 0)).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() => expect(get.mock.calls.some(([route, params]) => route === 'Fusanhe/insights' && params?.q === 'buyer' && params?.offset === 25)).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: '查看分析：<buyer>' }))
    await screen.findByText('来源已有变化，下方为旧分析，请等待重新分析。')
    expect(screen.getByRole('link', { name: /客户消息/ }).getAttribute('href')).toBe('#ExternalMessage/view/msg%2F1')
    expect(screen.getByRole('link', { name: '打开 CRM 客户' }).getAttribute('href')).toBe('#Account/view/a-1')
    expect(container.querySelector('script')).toBeNull()
    expect(screen.getByText('<script>alert(1)</script>')).not.toBeNull()
    expect(post).not.toHaveBeenCalled()
    expect(patch).not.toHaveBeenCalled()
  })

  it('replaces old metrics with a local retry on failure', async () => {
    const { host, get } = makeHost()
    get.mockRejectedValueOnce(new Error('unavailable'))
    render(<InsightsScreen host={host} data={null} screen="insights" />)
    await screen.findByRole('alert')
    expect(screen.queryByText('平台可见会话')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '重试' }))
    await screen.findByText('平台可见会话')
  })

  it('uses host language for UI labels while preserving customer data verbatim', async () => {
    const { host } = makeHost()
    host.translate = key => english.labels[key as keyof typeof english.labels] || key
    render(<InsightsScreen host={host} data={null} screen="insights" />)
    await screen.findByRole('button', { name: `${english.labels['查看分析']}：<buyer>` })
    expect(screen.getByRole('heading', { name: english.labels['历史客户与今日建议'] })).not.toBeNull()
    expect(screen.getByLabelText(`${english.labels['平台可见会话']}：${english.labels['待核对']}`)).not.toBeNull()
    expect(screen.getAllByRole('link', { name: '<buyer>' }).length).toBeGreaterThan(0)
    expect(screen.getByText(english.labels['身份尚未确认'])).not.toBeNull()
    expect(screen.getByText(english.labels['核对平台身份与客户关联后再跟进'])).not.toBeNull()
    expect(screen.getByText((content, element) => element?.tagName === 'P' && content.startsWith(english.labels['待采集端提供完整分页及消息对账；平台可见总数和未入库失败数未知。仅统计带同步来源的 Alibaba 会话。']))).not.toBeNull()
  })

  it('keeps server-authored text verbatim even when it matches a UI dictionary key', async () => {
    const { host, get } = makeHost()
    host.translate = key => english.labels[key as keyof typeof english.labels] || key
    get.mockImplementation(async route => route.startsWith('Fusanhe/insights/')
      ? { id: 'conv/1', name: '<buyer>', analysisStatus: 'stale', analysisNotice: '待确认',
        analysis: { summaryZh: '待确认' }, evidence: [] }
      : { ...overview, coverage: { ...overview.coverage, reason: '待确认' },
        suggestions: [{ ...overview.suggestions[0], reason: '待确认', action: '未分配' }] })
    render(<InsightsScreen host={host} data={null} screen="insights" />)
    await screen.findByRole('button', { name: `${english.labels['查看分析']}：<buyer>` })
    expect(screen.getAllByText('待确认').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText((content, element) => element?.tagName === 'P' && content.startsWith('待确认 '))).not.toBeNull()
    expect(screen.getByText('未分配')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: `${english.labels['查看分析']}：<buyer>` }))
    await screen.findByText(english.labels['来源已有变化，下方为旧分析，请等待重新分析。'])
    expect(screen.getAllByText('待确认').length).toBeGreaterThanOrEqual(3)
  })

  it('keeps keyboard analysis controls identifiable and hides inaccessible related records', async () => {
    const { host } = makeHost()
    host.can = scope => scope === 'ExternalConversation'
    const { container } = render(<InsightsScreen host={host} data={null} screen="insights" />)
    const button = await screen.findByRole('button', { name: '查看分析：<buyer>' })
    expect(button.getAttribute('aria-controls')).toBe('fsh-insights-analysis')
    expect(button.getAttribute('aria-expanded')).toBe('false')
    expect(button.getAttribute('type')).toBe('button')
    expect(container.querySelector('#fsh-insights-analysis')).not.toBeNull()
    expect(screen.queryByText('打开 CRM 客户')).toBeNull()
    button.focus()
    expect(document.activeElement).toBe(button)
    fireEvent.click(button)
    await screen.findByText('来源已有变化，下方为旧分析，请等待重新分析。')
    expect(button.getAttribute('aria-expanded')).toBe('true')
    expect(document.activeElement).toBe(screen.getByRole('heading', { name: '客户分析' }))
    expect(screen.getByText('无可读取的证据')).not.toBeNull()
    expect(container.querySelector('a[href^="#ExternalMessage/view/"]')).toBeNull()
  })

  it('confines wide tables to local horizontal scrolling at narrow widths', async () => {
    const { host } = makeHost()
    const { container } = render(<InsightsScreen host={host} data={null} screen="insights" />)
    await screen.findByRole('button', { name: '查看分析：<buyer>' })
    const tables = Array.from(container.querySelectorAll('table'))
    expect(tables).toHaveLength(2)
    expect(tables.every(table => table.parentElement?.classList.contains('overflow-x-auto'))).toBe(true)
    expect(tables.every(table => table.className.includes('min-w-['))).toBe(true)
    expect(screen.getByRole('textbox', { name: '搜索' }).getAttribute('maxlength')).toBe('100')
  })
})
