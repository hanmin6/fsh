import { useCallback, useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import type { HostBridge, ScreenProps } from '@/lib/host'
import { count, Loading, MetricStrip, recent, RecordLink, RecordSection, StateBadge, TableCell, type QueryState } from './shared'

export const screenId = 'crm'

type Row = {
  id?: string; name?: string; accountId?: string; accountName?: string; assignedUserName?: string;
  status?: string; createdAt?: string; dateEnd?: string; parentType?: string; parentId?: string
}
type Section = 'accounts' | 'contacts' | 'leads' | 'tasks'
type Snapshot = { counts: Record<Section, QueryState<number>>; sections: Record<Section, QueryState<Row[]>> }

export async function loadCrm(host: HostBridge): Promise<Snapshot> {
  const taskWhere = host.currentUserId ? { type: 'equals' as const, attribute: 'assignedUserId', value: host.currentUserId } : undefined
  const [accountsCount, contactsCount, leadsCount, tasksCount, accounts, contacts, leads, tasks] = await Promise.all([
    count(host, 'Account'), count(host, 'Contact'), count(host, 'Lead'),
    taskWhere ? count(host, 'Task', taskWhere) : Promise.resolve({ kind: host.can('Task', 'read') ? 'error' : 'denied' } as const),
    recent<Row>(host, 'Account', ['id', 'name', 'assignedUserName', 'createdAt']),
    recent<Row>(host, 'Contact', ['id', 'name', 'accountId', 'accountName', 'createdAt']),
    recent<Row>(host, 'Lead', ['id', 'name', 'accountName', 'status', 'createdAt']),
    taskWhere ? recent<Row>(host, 'Task', ['id', 'name', 'status', 'dateEnd', 'parentType', 'parentId'], taskWhere)
      : Promise.resolve({ kind: host.can('Task', 'read') ? 'error' : 'denied' } as const),
  ])
  return {
    counts: { accounts: accountsCount, contacts: contactsCount, leads: leadsCount, tasks: tasksCount },
    sections: { accounts, contacts, leads, tasks: tasks.kind === 'ok'
      ? { kind: 'ok', value: tasks.value.filter(row => !['Completed', 'Canceled'].includes(row.status || '')) } : tasks },
  }
}

function displayTime(value?: string) {
  if (!value) return '—'
  const normalized = value.includes('T') ? value : value.replace(' ', 'T') + 'Z'
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return '—'
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(date) + ' UTC+8'
}

export default function CrmScreen({ host }: ScreenProps) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const sequence = useRef(0)
  const t = (label: string) => host.translate(label)
  const refresh = useCallback(async () => {
    const request = ++sequence.current
    setRefreshing(true)
    const next = await loadCrm(host)
    if (request === sequence.current) { setSnapshot(next); setRefreshing(false) }
  }, [host])
  useEffect(() => { void refresh(); return () => { sequence.current += 1 } }, [refresh])
  return <div className="flex min-w-0 flex-col gap-5" role="region" aria-label={t('CRM 工作台')}>
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-2xl font-semibold tracking-tight">{t('CRM 工作台')}</h1><p className="mt-1 text-sm text-muted-foreground">{t('客户、联系人、线索与跟进任务')}</p></div>
      <div className="flex flex-wrap items-center gap-2">
        {host.can('ExternalConversation', 'read') && <Button asChild variant="outline" className="min-h-11"><a href="#Home/insights">{t('历史客户与今日建议')}</a></Button>}
        <Button variant="outline" className="min-h-11" disabled={refreshing} onClick={() => void refresh()}>{refreshing ? t('正在加载…') : t('刷新')}</Button>
      </div>
    </header>
    <p className="sr-only" role="status">{refreshing ? t('正在加载…') : snapshot ? t('数据已更新') : ''}</p>
    {snapshot ? <>
      <MetricStrip host={host} items={[
        { label: '客户公司', state: snapshot.counts.accounts }, { label: '联系人', state: snapshot.counts.contacts },
        { label: '线索', state: snapshot.counts.leads }, { label: '分配给我的任务', state: snapshot.counts.tasks },
      ]} />
      <div className="grid min-w-0 gap-x-6 gap-y-6 xl:grid-cols-2">
        <RecordSection host={host} title="最近客户" entity="Account" state={snapshot.sections.accounts} headers={['客户公司', '负责人', '创建时间']} onRetry={() => void refresh()} renderRow={row => <><TableCell><RecordLink entity="Account" id={row.id} name={row.name} /></TableCell><TableCell>{row.assignedUserName || t('未分配')}</TableCell><TableCell className="whitespace-nowrap">{displayTime(row.createdAt)}</TableCell></>} />
        <RecordSection host={host} title="最近联系人" entity="Contact" state={snapshot.sections.contacts} headers={['联系人', '所属客户', '创建时间']} onRetry={() => void refresh()} renderRow={row => <><TableCell><RecordLink entity="Contact" id={row.id} name={row.name} /></TableCell><TableCell><RecordLink entity="Account" id={row.accountId} name={row.accountName} allowed={host.can('Account', 'read')} /></TableCell><TableCell className="whitespace-nowrap">{displayTime(row.createdAt)}</TableCell></>} />
        <RecordSection host={host} title="最近线索" entity="Lead" state={snapshot.sections.leads} headers={['线索', '所属客户', '状态']} onRetry={() => void refresh()} renderRow={row => <><TableCell><RecordLink entity="Lead" id={row.id} name={row.name} /></TableCell><TableCell>{row.accountName || '—'}</TableCell><TableCell><StateBadge host={host} value={row.status} /></TableCell></>} />
        <RecordSection host={host} title="我的待办" entity="Task" state={snapshot.sections.tasks} headers={['任务', '状态', '截止时间', '来源会话']} onRetry={() => void refresh()} renderRow={row => <><TableCell><RecordLink entity="Task" id={row.id} name={row.name} /></TableCell><TableCell><StateBadge host={host} value={row.status} /></TableCell><TableCell className="whitespace-nowrap">{displayTime(row.dateEnd)}</TableCell><TableCell>{row.parentType === 'ExternalConversation' ? <RecordLink entity="ExternalConversation" id={row.parentId} name={t('来源会话')} allowed={host.can('ExternalConversation', 'read')} /> : '—'}</TableCell></>} />
      </div>
    </> : <Loading host={host} label="正在加载客户数据…" />}
  </div>
}
