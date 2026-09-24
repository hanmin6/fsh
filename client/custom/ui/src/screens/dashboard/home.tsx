import { useCallback, useEffect, useRef, useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import type { HostBridge, ScreenProps } from '@/lib/host'
import { count, Loading, MetricStrip, recent, RecordLink, RecordSection, StateBadge, TableCell, type QueryState } from './shared'

export const screenId = 'home'

type Row = { id?: string; name?: string; status?: string; assignedUserName?: string; accountName?: string }
type Snapshot = {
  counts: Record<'accounts' | 'contacts' | 'leads' | 'tasks' | 'conversations' | 'drafts' | 'identities' | 'exceptions', QueryState<number>>
  accounts: QueryState<Row[]>
  contacts: QueryState<Row[]>
  leads: QueryState<Row[]>
  conversations: QueryState<Row[]>
}

export async function loadHome(host: HostBridge): Promise<Snapshot> {
  const taskWhere = host.currentUserId ? { type: 'equals' as const, attribute: 'assignedUserId', value: host.currentUserId } : undefined
  const [accounts, contacts, leads, tasks, conversations, drafts, identities, exceptions, recentAccounts, recentContacts, recentLeads, recentConversations] = await Promise.all([
    count(host, 'Account'), count(host, 'Contact'), count(host, 'Lead'),
    taskWhere ? count(host, 'Task', taskWhere) : Promise.resolve({ kind: host.can('Task', 'read') ? 'error' : 'denied' } as const),
    count(host, 'ExternalConversation', { type: 'in', attribute: 'status', value: ['new', 'pending', 'drafted', 'waitingApproval'] }),
    count(host, 'AIReplyDraft', { type: 'in', attribute: 'status', value: ['generated', 'edited'] }),
    count(host, 'ExternalIdentity', { type: 'equals', attribute: 'linkStatus', value: 'unlinked' }),
    count(host, 'OutboundTask', { type: 'in', attribute: 'status', value: ['failed', 'sending'] }),
    recent<Row>(host, 'Account', ['id', 'name', 'assignedUserName', 'createdAt']),
    recent<Row>(host, 'Contact', ['id', 'name', 'accountName', 'createdAt']),
    recent<Row>(host, 'Lead', ['id', 'name', 'status', 'createdAt']),
    recent<Row>(host, 'ExternalConversation', ['id', 'name', 'status', 'assignedUserName', 'lastMessageAt'], undefined, 'lastMessageAt'),
  ])
  return { counts: { accounts, contacts, leads, tasks, conversations, drafts, identities, exceptions }, accounts: recentAccounts, contacts: recentContacts, leads: recentLeads, conversations: recentConversations }
}

export default function HomeScreen({ host }: ScreenProps) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const sequence = useRef(0)
  const t = (label: string) => host.translate(label)
  const canCrm = ['Account', 'Contact', 'Lead'].some(scope => host.can(scope, 'read'))
  const canService = host.can('ExternalConversation', 'read')
  const refresh = useCallback(async () => {
    const request = ++sequence.current
    setRefreshing(true)
    const next = await loadHome(host)
    if (request === sequence.current) { setSnapshot(next); setRefreshing(false) }
  }, [host])
  useEffect(() => { void refresh(); return () => { sequence.current += 1 } }, [refresh])

  return <div className="flex min-w-0 flex-col gap-5" role="region" aria-label={t('福三和工作台')}>
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-2xl font-semibold tracking-tight">{t('福三和工作台')}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t('广州福三和食品有限公司')} · {t('从业务入口继续处理客户与会话。')}</p></div>
      <Button variant="outline" className="min-h-11" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? t('正在加载…') : t('刷新')}</Button>
    </header>
    <p className="sr-only" role="status">{refreshing ? t('正在加载…') : snapshot ? t('数据已更新') : ''}</p>
    {!canCrm && !canService ? <Empty><EmptyHeader><EmptyTitle>{t('没有可访问的工作模块')}</EmptyTitle><EmptyDescription>{t('请联系管理员确认您的访问权限。')}</EmptyDescription></EmptyHeader></Empty>
      : <>
        <nav className="grid min-w-0 gap-3 md:grid-cols-2" aria-label={t('选择工作模块')}>
          {canCrm && <a href="#Home/crm" className="flex min-h-24 flex-col justify-center gap-1 rounded-md border p-4 text-foreground outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring">
            <span className="font-semibold">{t('CRM 工作台')}</span><span className="text-sm text-muted-foreground">{t('客户、联系人、线索与跟进任务')}</span><span className="text-sm font-medium">{t('进入 CRM')} →</span>
          </a>}
          {canService && <a href="#Home/service" className="flex min-h-24 flex-col justify-center gap-1 rounded-md border p-4 text-foreground outline-none transition-colors hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring">
            <span className="font-semibold">{t('AI 客服工作台')}</span><span className="text-sm text-muted-foreground">{t('统一收件箱、草稿审核、身份确认与发送异常')}</span><span className="text-sm font-medium">{t('进入客服')} →</span>
          </a>}
        </nav>
        {canService && <Alert><AlertTitle>{t('历史客户与今日建议')}</AlertTitle><AlertDescription className="flex flex-wrap items-center justify-between gap-2">{t('查看导入覆盖率、分析与人工跟进清单')}<Button asChild variant="outline" className="min-h-11"><a href="#Home/insights">{t('查看老板页')}</a></Button></AlertDescription></Alert>}
        {snapshot ? <>
          <MetricStrip host={host} items={canCrm ? [
            { label: '客户公司', state: snapshot.counts.accounts }, { label: '联系人', state: snapshot.counts.contacts },
            { label: '线索', state: snapshot.counts.leads }, { label: '分配给我的任务', state: snapshot.counts.tasks },
          ] : [
            { label: '进行中会话', state: snapshot.counts.conversations }, { label: '待审核草稿', state: snapshot.counts.drafts },
            { label: '身份待确认', state: snapshot.counts.identities }, { label: '发送异常', state: snapshot.counts.exceptions },
          ]} />
          <div className="grid min-w-0 gap-6 xl:grid-cols-2" aria-label={t('最近业务')}>
            {canCrm && host.can('Account', 'read') && <RecordSection host={host} title="最近客户" entity="Account" state={snapshot.accounts} headers={['客户公司', '负责人']} onRetry={() => void refresh()} renderRow={row => <><TableCell><RecordLink entity="Account" id={row.id} name={row.name} /></TableCell><TableCell>{row.assignedUserName || t('未分配')}</TableCell></>} />}
            {canCrm && !host.can('Account', 'read') && host.can('Contact', 'read') && <RecordSection host={host} title="最近联系人" entity="Contact" state={snapshot.contacts} headers={['联系人', '所属客户']} onRetry={() => void refresh()} renderRow={row => <><TableCell><RecordLink entity="Contact" id={row.id} name={row.name} /></TableCell><TableCell>{row.accountName || '—'}</TableCell></>} />}
            {canCrm && !host.can('Account', 'read') && !host.can('Contact', 'read') && host.can('Lead', 'read') && <RecordSection host={host} title="最近线索" entity="Lead" state={snapshot.leads} headers={['线索', '状态']} onRetry={() => void refresh()} renderRow={row => <><TableCell><RecordLink entity="Lead" id={row.id} name={row.name} /></TableCell><TableCell><StateBadge host={host} value={row.status} /></TableCell></>} />}
            {canService && <RecordSection host={host} title="最近会话" entity="ExternalConversation" state={snapshot.conversations} headers={['会话', '状态', '负责人']} onRetry={() => void refresh()} renderRow={row => <><TableCell><RecordLink entity="ExternalConversation" id={row.id} name={row.name} /></TableCell><TableCell><StateBadge host={host} value={row.status} /></TableCell><TableCell>{row.assignedUserName || t('未分配')}</TableCell></>} />}
          </div>
        </> : <Loading host={host} label="正在加载模块入口…" />}
      </>}
  </div>
}
