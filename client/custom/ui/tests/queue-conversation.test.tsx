// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { HostBridge } from '../src/lib/host'
import QueueScreen from '../src/screens/queue'
import ConversationScreen from '../src/screens/conversation'
import { canApproveDraft, canEditDraft, outboundDescription } from '../src/screens/conversation/policy'
afterEach(cleanup)

function makeHost(can: (scope: string, action?: string) => boolean = () => true) {
  const get = vi.fn(async (_route: string, _params?: Record<string, unknown>): Promise<any> => ({ list: [], total: 0 }))
  const post = vi.fn(async () => ({}))
  const patch = vi.fn(async () => ({}))
  const getOutboundState = vi.fn(async () => ({ paused: null, status: 'unknown' as const }))
  const navigate = vi.fn()
  const host = { api: { get, post, patch }, can, navigate, translate: (label: string) => label,
    notify: vi.fn(), currentUserId: null, getOutboundState } as HostBridge
  return { host, get, post, patch, navigate, getOutboundState }
}
const conversation = { id: 'conv/1', name: '询盘一', status: 'pending', controlMode: 'aiAssist', identityId: null,
  contactName: '<buyer>', lastInboundAt: '2026-09-24 08:00:00' }
const draft = { id: 'draft/1', status: 'generated', riskLevel: 'high', draftText: 'Original reply', summaryZh: '价格和交期',
  missingInformation: ['MOQ'], citedKnowledge: ['doc/1'], suggestedLanguage: 'en' }
function mockConversationGet(get: ReturnType<typeof vi.fn>, currentDraft: any = draft) {
  get.mockImplementation(async (route: string) => {
    if (route === 'ExternalConversation/conv%2F1') return conversation
    if (route === 'ExternalConversation') return { list: [conversation], total: 1 }
    if (route === 'ExternalMessage') return { list: [{ id: 'msg/1', direction: 'inbound', senderName: 'Buyer',
      body: '<original>\nMOQ?', translatedBody: '中文译文', attachmentMetadata: [{ name: 'file.pdf' }], deliveryStatus: 'received' }], total: 1 }
    if (route === 'AIReplyDraft') return { list: currentDraft ? [currentDraft] : [] }
    if (route === 'OutboundTask') return { list: [] }
    if (route.endsWith('handoff-tasks')) return { tasks: [] }
    return { list: [] }
  })
}

describe('queue workbench', () => {
  it('keeps forbidden lists request-free', async () => {
    const { host, get } = makeHost(() => false)
    render(<QueueScreen host={host} data={{ entity: 'OutboundTask', statusOptions: [] }} screen="queue" />)
    expect(screen.getByText('没有读取权限')).not.toBeNull()
    await waitFor(() => expect(get).not.toHaveBeenCalled())
  })

  it('renders a real table and row keyboard action without hijacking links', async () => {
    const { host, get, navigate } = makeHost()
    get.mockImplementation(async (route) => route === 'KnowledgeDocument'
      ? { list: [{ id: 'doc/1', name: '<unsafe>', approvalStatus: 'approved' }], total: 1 }
      : { list: [] })
    const { container } = render(<QueueScreen host={host} data={{ entity: 'KnowledgeDocument', statusOptions: ['approved'] }} screen="queue" />)
    const row = await screen.findByRole('row', { name: /打开记录/ })
    expect(container.querySelector('[data-slot="table"]')).not.toBeNull()
    expect(container.querySelector('[data-slot="badge"]')).not.toBeNull()
    expect(screen.getByRole('link', { name: '<unsafe>' }).getAttribute('href')).toBe('#KnowledgeDocument/view/doc%2F1')
    fireEvent.click(screen.getByRole('link', { name: '<unsafe>' }))
    expect(navigate).not.toHaveBeenCalled()
    fireEvent.keyDown(row, { key: 'Enter' })
    expect(navigate).toHaveBeenCalledWith('#KnowledgeDocument/view/doc%2F1')
    expect(container.querySelector('script')).toBeNull()
  })

  it('sends bounded filtered queries and changes page only when more rows exist', async () => {
    const { host, get } = makeHost()
    get.mockImplementation(async (route) => route === 'OutboundTask'
      ? { list: Array.from({ length: 50 }, (_, i) => ({ id: `task-${i}`, status: 'pending' })), total: 60 }
      : { list: [] })
    render(<QueueScreen host={host} data={{ entity: 'OutboundTask', statusOptions: ['pending'] }} screen="queue" />)
    await screen.findByText('1–50 / 60')
    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    await screen.findByText('51–100 / 60')
    expect(get.mock.calls.filter(([route]) => route === 'OutboundTask').every(([, params]) => params.maxSize === 50)).toBe(true)
    expect(get.mock.calls.some(([route, params]) => route === 'OutboundTask' && params.offset === 50)).toBe(true)
  })

  it('searches visible conversation identifiers and provides a record link', async () => {
    const { host, get } = makeHost()
    get.mockImplementation(async (route) => route === 'ExternalConversation'
      ? { list: [{ id: 'conv/1', name: '询盘 SEC-CONV-1' }], total: 1 }
      : { list: [] })
    render(<QueueScreen host={host} data={{ entity: 'ExternalConversation', statusOptions: [] }} screen="queue" />)
    expect((await screen.findByRole('link', { name: '打开会话' })).getAttribute('href')).toBe('#ExternalConversation/view/conv%2F1')
    fireEvent.change(screen.getByLabelText('搜索'), { target: { value: 'SEC-CONV' } })
    fireEvent.click(screen.getByRole('button', { name: '查询' }))
    await waitFor(() => expect(get.mock.calls.some(([route, params]) => route === 'ExternalConversation' &&
      params?.where?.some((item: Record<string, any>) => item.type === 'or' && item.value.some((part: Record<string, string>) =>
        part.attribute === 'name' && part.type === 'contains' && part.value === 'SEC-CONV')))).toBe(true))
  })

  it('keeps model supplied list text verbatim and links review records', async () => {
    const { host, get } = makeHost()
    get.mockImplementation(async (route) => route === 'AIReplyDraft'
      ? { list: [{ id: 'draft/1', name: 'Draft', missingInformation: ['sent', 'new'] }], total: 1 }
      : { list: [] })
    render(<QueueScreen host={host} data={{ entity: 'AIReplyDraft', statusOptions: [] }} screen="queue" />)
    expect((await screen.findByRole('link', { name: '打开记录' })).getAttribute('href')).toBe('#AIReplyDraft/view/draft%2F1')
    expect(screen.getByText('sent、new')).not.toBeNull()
  })
})

describe('conversation approval and state contract', () => {
  it('returns focus to the action that opened a controlled dialog', async () => {
    const { host, get } = makeHost()
    mockConversationGet(get)
    render(<ConversationScreen host={host} data={{ conversationId: 'conv/1' }} screen="conversation" />)
    const trigger = await screen.findByRole('button', { name: '人工草稿' })
    screen.getByRole('button', { name: '刷新' }).focus()
    fireEvent.click(trigger)
    expect(await screen.findByRole('dialog', { name: '人工草稿' })).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '关闭' }))
    await waitFor(() => expect(document.activeElement).toBe(trigger))
  })

  it('connects compact navigation tabs to their conversation panels', async () => {
    const { host, get } = makeHost()
    mockConversationGet(get)
    render(<ConversationScreen host={host} data={{ conversationId: 'conv/1' }} screen="conversation" />)
    const messages = await screen.findByRole('tab', { name: '消息' })
    expect(messages.getAttribute('aria-controls')).toBe('conversation-panel-messages')
    expect(screen.getByRole('tabpanel', { name: '消息' }).id).toBe('conversation-panel-messages')
    expect(screen.getByRole('tabpanel', { name: '会话' }).id).toBe('conversation-panel-customers')
    expect(screen.getByRole('tabpanel', { name: '资料与审核' }).id).toBe('conversation-panel-review')
  })

  it('makes sent drafts immutable and preserves unknown outbound state', () => {
    expect(canEditDraft(true, { id: 'd', status: 'sent' })).toBe(false)
    expect(canApproveDraft(true, true, { id: 'd', status: 'sent' })).toBe(false)
    expect(canApproveDraft(false, true, { id: 'd', status: 'generated' })).toBe(false)
    expect(outboundDescription(null)).toContain('请勿假定')
  })

  it('shows original text, translation, attachment, evidence, and a true confirmation gate', async () => {
    const { host, get, post } = makeHost()
    mockConversationGet(get)
    const { container } = render(<ConversationScreen host={host} data={{ conversationId: 'conv/1' }} screen="conversation" />)
    await screen.findByText(/<original>/)
    expect(screen.getByText('已接收')).not.toBeNull()
    expect(screen.getByText('中文译文')).not.toBeNull()
    expect(screen.getByText('file.pdf')).not.toBeNull()
    expect(screen.getByRole('link', { name: '查看引用资料' }).getAttribute('href')).toBe('#KnowledgeDocument/view/doc%2F1')
    expect(container.querySelector('[data-slot="alert"]')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '批准并创建发送任务' }))
    const dialog = await screen.findByRole('alertdialog')
    expect(within(dialog).getByText(/商业承诺/)).not.toBeNull()
    expect(post).not.toHaveBeenCalled()
    const confirm = within(dialog).getByRole('button', { name: '确认批准并创建任务' })
    expect((confirm as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(within(dialog).getByRole('checkbox', { name: '我已完成人工审核' }))
    expect((confirm as HTMLButtonElement).disabled).toBe(false)
    fireEvent.click(confirm)
    await waitFor(() => expect(post).toHaveBeenCalledWith('Fusanhe/draft/draft%2F1/approve', { draftText: 'Original reply' }))
  })

  it('saving patches only the draft; forbidden capabilities hide actions', async () => {
    const { host, get, post, patch } = makeHost((scope, action) =>
      !(scope === 'AIReplyDraft' && action === 'create') && !(scope === 'OutboundTask' && action === 'create'))
    mockConversationGet(get)
    render(<ConversationScreen host={host} data={{ conversationId: 'conv/1' }} screen="conversation" />)
    const save = await screen.findByRole('button', { name: '保存修改' })
    fireEvent.change(screen.getByLabelText(/英文回复草稿/), { target: { value: 'Edited reply' } })
    fireEvent.click(save)
    await waitFor(() => expect(patch).toHaveBeenCalledWith('AIReplyDraft/draft%2F1', { draftText: 'Edited reply', status: 'edited' }))
    expect(post).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: '生成 AI 草稿' })).toBeNull()
    expect((screen.getByRole('button', { name: '批准并创建发送任务' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('rejecting patches only rejection status, and pending writes cannot duplicate', async () => {
    const { host, get, post, patch } = makeHost()
    mockConversationGet(get)
    let finish!: () => void
    patch.mockImplementation(() => new Promise<void>((resolve) => { finish = resolve }))
    render(<ConversationScreen host={host} data={{ conversationId: 'conv/1' }} screen="conversation" />)
    const reject = await screen.findByRole('button', { name: '拒绝草稿' })
    fireEvent.click(reject)
    fireEvent.click(reject)
    expect(patch).toHaveBeenCalledTimes(1)
    expect(patch).toHaveBeenCalledWith('AIReplyDraft/draft%2F1', { status: 'rejected' })
    expect(post).not.toHaveBeenCalled()
    finish()
    await waitFor(() => expect((reject as HTMLButtonElement).disabled).toBe(false))
  })

  it('withholds editing, rejection and approval when draft edit permission is missing', async () => {
    const { host, get, post, patch } = makeHost((scope, action) => !(scope === 'AIReplyDraft' && action === 'edit'))
    mockConversationGet(get)
    render(<ConversationScreen host={host} data={{ conversationId: 'conv/1' }} screen="conversation" />)
    const save = await screen.findByRole('button', { name: '保存修改' })
    expect((save as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: '拒绝草稿' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: '批准并创建发送任务' }) as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByLabelText(/英文回复草稿/) as HTMLTextAreaElement).readOnly).toBe(true)
    expect(post).not.toHaveBeenCalled()
    expect(patch).not.toHaveBeenCalled()
  })
})
