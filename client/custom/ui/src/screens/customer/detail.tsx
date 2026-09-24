import { useEffect, useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { Separator } from '@/components/ui/separator'
import { Skeleton } from '@/components/ui/skeleton'
import type { HostBridge, ScreenProps } from '@/lib/host'

export const screenId = 'customer-detail'

type CustomerData = {
  type: 'Account' | 'Contact' | 'Lead'
  id: string
  attributes: Record<string, unknown>
}
type Conversation = {
  id: string
  name?: string
  status?: string
  channelName?: string
  contactName?: string
  country?: string
  product?: string
  assignedUserName?: string
  externalUserId?: string
  controlMode?: string
  lastMessageAt?: string
  lastOutboundAt?: string
  needsManualMatch?: boolean
}
type Task = { id: string; name?: string; dateEnd?: string }
type Result<T> = { kind: 'loading' } | { kind: 'denied' } | { kind: 'error' } | { kind: 'ok'; items: T[] }
type ListResponse<T> = { list?: T[] }

const loading = { kind: 'loading' } as const
const asText = (value: unknown): string => typeof value === 'string' && value.trim() ? value : ''

async function fetchList<T>(
  host: HostBridge,
  entity: string,
  params: Record<string, unknown>,
): Promise<Result<T>> {
  if (!host.can(entity, 'read')) return { kind: 'denied' }
  try {
    const response = await host.api.get<ListResponse<T>>(entity, params)
    return Array.isArray(response?.list) ? { kind: 'ok', items: response.list } : { kind: 'error' }
  } catch {
    return { kind: 'error' }
  }
}

function RecordLink({ entity, id, children }: { entity: string; id?: string; children: React.ReactNode }) {
  return id
    ? <a className="inline-flex min-h-11 items-center font-medium underline-offset-4 hover:underline" href={`#${entity}/view/${encodeURIComponent(id)}`}>{children}</a>
    : <>{children}</>
}

function Fact({ label, value, fallback }: { label: string; value?: React.ReactNode; fallback: string }) {
  return (
    <div className="grid min-w-0 gap-1 border-b py-2 last:border-0 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-3">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="m-0 min-w-0 break-words">{value || fallback}</dd>
    </div>
  )
}

function SectionState({ result, host, empty }: { result: Result<unknown>; host: HostBridge; empty: string }) {
  const t = host.translate
  if (result.kind === 'loading') return <div aria-label={t('正在读取客户跟进信息…')} className="flex flex-col gap-2"><Skeleton className="h-6 w-3/4" /><Skeleton className="h-6 w-1/2" /></div>
  if (result.kind === 'denied') return <p className="text-muted-foreground">{t('没有读取权限')}</p>
  if (result.kind === 'error') return <Alert variant="destructive"><AlertTitle>{t('读取失败')}</AlertTitle><AlertDescription>{t('请刷新页面重试。')}</AlertDescription></Alert>
  return <p className="text-muted-foreground">{empty}</p>
}

export default function CustomerDetail({ host, data }: ScreenProps<CustomerData>) {
  const t = host.translate
  const [conversations, setConversations] = useState<Result<Conversation>>(loading)
  const [tasks, setTasks] = useState<Result<Task>>(loading)
  const customer = data?.attributes || {}
  const customerId = data?.id
  const entityType = data?.type

  useEffect(() => {
    if (!customerId || !['Account', 'Contact', 'Lead'].includes(entityType)) return
    let active = true
    const field = entityType === 'Account' ? 'accountId' : entityType === 'Contact' ? 'contactId' : 'leadId'
    void fetchList<Conversation>(host, 'ExternalConversation', {
      where: [{ type: 'equals', attribute: field, value: customerId }],
      orderBy: 'lastMessageAt', order: 'desc', maxSize: 20,
    }).then(result => { if (active) setConversations(result) })
    void fetchList<Task>(host, 'Task', {
      where: [
        { type: 'equals', attribute: 'parentId', value: customerId },
        { type: 'equals', attribute: 'parentType', value: entityType },
        { type: 'notIn', attribute: 'status', value: ['Completed', 'Canceled'] },
      ],
      orderBy: 'dateEnd', order: 'asc', maxSize: 5,
    }).then(result => { if (active) setTasks(result) })
    return () => { active = false }
  }, [customerId, entityType, host])

  const list = conversations.kind === 'ok' ? conversations.items : []
  const latest = list[0]
  const relatedFallback = conversations.kind === 'loading' ? t('正在加载…')
    : conversations.kind === 'denied' ? t('没有读取权限')
      : conversations.kind === 'error' ? t('读取失败') : t('未记录')
  const productNames = [...new Set(list.map(item => item.product).filter((value): value is string => !!value))]
  const missing = t('未记录')
  const statusNames: Record<string, string> = {
    New: '新线索', Assigned: '已分配', InProcess: '跟进中',
    Converted: '已转化', Recycled: '待再跟进', Dead: '无效',
    new: '新询盘', pending: '待回复', replied: '已回复', closed: '已关闭',
  }
  const statusLabel = (status?: string) => status ? t(statusNames[status] || status) : missing
  const externalIds = [...new Set(list.map(item => item.externalUserId).filter((value): value is string => !!value))]

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="m-0 text-base font-semibold">{t('客户业务概览')}</h2>
          <p className="mb-0 mt-1 text-sm text-muted-foreground">{t('原生详情与关系记录保留在下方。')}</p>
        </div>
        {host.can('Task', 'create') && customerId && (
          <Button variant="outline" size="sm" asChild>
            <a href={`#Task/create?parentType=${encodeURIComponent(entityType)}&parentId=${encodeURIComponent(customerId)}`}>{t('创建跟进任务')}</a>
          </Button>
        )}
      </div>
      {list.some(item => item.needsManualMatch) && (
        <Alert>
          <AlertTitle>{t('客户匹配待人工确认')}</AlertTitle>
          <AlertDescription>{t('请先核对平台身份与客户关系，再据此跟进。')}</AlertDescription>
        </Alert>
      )}
      <dl className="m-0 grid min-w-0 gap-x-6 lg:grid-cols-2">
        <Fact label={t('客户 / 公司')} value={asText(customer.accountName) || asText(customer.name)} fallback={missing} />
        <Fact label={t('国家 / 地区')} value={asText(customer.billingAddressCountry) || asText(customer.addressCountry) || latest?.country} fallback={relatedFallback} />
        <Fact label={t('主要联系人')} value={latest?.contactName || (entityType === 'Account' ? '' : asText(customer.name))} fallback={relatedFallback} />
        <Fact label={t('邮箱')} value={asText(customer.emailAddress)} fallback={missing} />
        <Fact label={t('客户负责人')} value={asText(customer.assignedUserName)} fallback={t('未分配')} />
        <Fact label={t('接待人（最近会话）')} value={latest?.assignedUserName} fallback={conversations.kind === 'ok' ? t('未分配') : relatedFallback} />
        <Fact label={t('来源渠道')} value={latest?.channelName || asText(customer.source)} fallback={relatedFallback} />
        <Fact label={t('感兴趣产品')} value={productNames.join('、')} fallback={relatedFallback} />
        <Fact label={t('最近联系')} value={latest?.lastMessageAt} fallback={conversations.kind === 'ok' ? t('暂无询盘消息') : relatedFallback} />
        <Fact label={t('最近回复')} value={latest?.lastOutboundAt} fallback={conversations.kind === 'ok' ? t('暂无发出回复记录') : relatedFallback} />
        <Fact label={t('平台身份')} value={externalIds.join('、')} fallback={conversations.kind === 'ok' ? t('未记录平台身份') : relatedFallback} />
        <Fact label={t('WhatsApp')} value={t('未单独记录，请在联系人信息中核实')} fallback={missing} />
        <Fact label={t('客户阶段')} value={statusLabel(asText(customer.status))} fallback={t('请查看关联商机')} />
      </dl>
      <Separator />
      <div className="grid min-w-0 gap-5 lg:grid-cols-2">
        <section aria-labelledby="fsh-recent-conversations" className="min-w-0">
          <h3 id="fsh-recent-conversations" className="mb-2 text-sm font-semibold">{t('最近询盘')}</h3>
          {conversations.kind === 'ok' && conversations.items.length ? (
            <ul className="m-0 list-none p-0">
              {conversations.items.slice(0, 5).map(item => (
                <li key={item.id} className="flex min-w-0 flex-wrap items-center gap-2 border-b py-1 last:border-0">
                  <RecordLink entity="ExternalConversation" id={item.id}>{item.name || t('未命名询盘')}</RecordLink>
                  <Badge variant="outline">{statusLabel(item.status)}</Badge>
                  {item.controlMode === 'human' && <Badge variant="secondary">{t('人工接管')}</Badge>}
                </li>
              ))}
            </ul>
          ) : conversations.kind === 'ok' ? (
            <Empty className="border"><EmptyHeader><EmptyTitle>{t('暂无关联询盘')}</EmptyTitle><EmptyDescription>{t('收到相关业务数据后将在这里显示。')}</EmptyDescription></EmptyHeader></Empty>
          ) : <SectionState result={conversations} host={host} empty={t('暂无关联询盘')} />}
        </section>
        <section aria-labelledby="fsh-next-actions" className="min-w-0">
          <h3 id="fsh-next-actions" className="mb-2 text-sm font-semibold">{t('下一步')}</h3>
          {tasks.kind === 'ok' && tasks.items.length ? (
            <ul className="m-0 list-none p-0">
              {tasks.items.map(task => <li key={task.id} className="flex flex-wrap items-center gap-2 border-b py-1 last:border-0"><RecordLink entity="Task" id={task.id}>{task.name || t('未命名任务')}</RecordLink><span className="text-sm text-muted-foreground">{task.dateEnd || '—'}</span></li>)}
            </ul>
          ) : tasks.kind === 'ok' ? (
            <Empty className="border"><EmptyHeader><EmptyTitle>{t('暂无关联待办')}</EmptyTitle><EmptyDescription>{t('可创建跟进任务记录下一步。')}</EmptyDescription></EmptyHeader></Empty>
          ) : <SectionState result={tasks} host={host} empty={t('暂无关联待办')} />}
        </section>
      </div>
    </div>
  )
}
