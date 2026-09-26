import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import type { HostBridge, ScreenProps } from '@/lib/host'

export const screenId = 'service'

type QueryState<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'denied' }
  | { kind: 'error' }

type Where = { type: 'in' | 'equals'; attribute: string; value: string | string[] }
type ListResponse<T> = { list?: T[]; total?: number }
type Item = {
  id?: string
  name?: string
  status?: string
  controlMode?: string
  lastInboundAt?: string
  assignedUserName?: string
  needsManualMatch?: boolean
  conversationId?: string
  conversationName?: string
  riskLevel?: string
  displayName?: string
  channelType?: string
  externalUserId?: string
  linkStatus?: string
  executionMode?: string
  errorMessage?: string
  connectionStatus?: string
  mode?: string
  lastHeartbeatAt?: string
}
type CountKey = 'all' | 'reply' | 'review' | 'identity' | 'takeover' | 'exception'
type SectionKey = 'conversations' | 'drafts' | 'identities' | 'exceptions' | 'channels' | 'agents'
type Snapshot = {
  counts: Record<CountKey, QueryState<number>>
  sections: Record<SectionKey, QueryState<Item[]>>
  outbound: boolean | null
}

const statusNames: Record<string, string> = {
  new: '新询盘', pending: '待回复', drafted: '已有草稿', waitingApproval: '待审核',
  readyToSend: '待发送', sending: '发送中', sent: '已发送', failed: '失败',
  replied: '已回复', closed: '已关闭', aiAssist: 'AI 辅助', human: '人工接管',
  unlinked: '待确认', confirmed: '已确认', generated: '待审核', edited: '已修改',
  approved: '已审核', rejected: '已拒绝', low: '低风险', medium: '中风险',
  high: '高风险', mock: '演示', online: '在线', offline: '离线',
  heartbeatStale: '心跳超时', loginExpired: '登录失效', captcha: '验证码',
  pageChanged: '页面变化', riskControl: '风控', healthy: '正常', degraded: '异常',
  Alibaba: '阿里国际站', MadeInChina: '中国制造网', Website: '独立站',
  Email: '邮件', Other: '其他',
}

const whereIn = (attribute: string, value: string[]): Where => ({ type: 'in', attribute, value })
const whereEquals = (attribute: string, value: string): Where => ({ type: 'equals', attribute, value })

async function count(host: HostBridge, entity: string, where?: Where): Promise<QueryState<number>> {
  if (!host.can(entity, 'read')) return { kind: 'denied' }
  try {
    const response = await host.api.get<ListResponse<Item>>(entity, {
      maxSize: 1,
      where: where ? [where] : [],
    })
    return Number.isInteger(response?.total) && response.total! >= 0
      ? { kind: 'ok', value: response.total! }
      : { kind: 'error' }
  } catch {
    return { kind: 'error' }
  }
}

async function recent(
  host: HostBridge,
  entity: string,
  select: string[],
  where?: Where,
  orderBy = 'createdAt',
): Promise<QueryState<Item[]>> {
  if (!host.can(entity, 'read')) return { kind: 'denied' }
  try {
    const response = await host.api.get<ListResponse<Item>>(entity, {
      maxSize: 6,
      orderBy,
      order: 'desc',
      select: select.join(','),
      where: where ? [where] : [],
    })
    return Array.isArray(response?.list)
      ? { kind: 'ok', value: response.list }
      : { kind: 'error' }
  } catch {
    return { kind: 'error' }
  }
}

export function parseOutboundState(value: unknown): boolean | null {
  if (typeof value !== 'object' || value === null || !('paused' in value)) return null
  return typeof value.paused === 'boolean' ? value.paused : null
}

function failedSnapshot(): Snapshot {
  const error = { kind: 'error' } as const
  return {
    counts: { all: error, reply: error, review: error, identity: error, takeover: error, exception: error },
    sections: { conversations: error, drafts: error, identities: error, exceptions: error, channels: error, agents: error },
    outbound: null,
  }
}

export async function loadServiceSnapshot(host: HostBridge): Promise<Snapshot> {
  const [all, reply, review, identity, takeover, exception, conversations, drafts,
    identities, exceptions, channels, agents, outbound] = await Promise.all([
    count(host, 'ExternalConversation'),
    count(host, 'ExternalConversation', whereIn('status', ['new', 'pending'])),
    count(host, 'AIReplyDraft', whereIn('status', ['generated', 'edited'])),
    count(host, 'ExternalIdentity', whereEquals('linkStatus', 'unlinked')),
    count(host, 'ExternalConversation', whereEquals('controlMode', 'human')),
    count(host, 'OutboundTask', whereIn('status', ['failed', 'sending'])),
    recent(host, 'ExternalConversation', ['id', 'name', 'status', 'controlMode', 'lastMessagePreview',
      'lastInboundAt', 'assignedUserName', 'needsManualMatch'], undefined, 'lastMessageAt'),
    recent(host, 'AIReplyDraft', ['id', 'name', 'status', 'conversationId', 'conversationName',
      'summaryZh', 'riskLevel', 'createdAt'], whereIn('status', ['generated', 'edited'])),
    recent(host, 'ExternalIdentity', ['id', 'name', 'channelType', 'externalUserId', 'displayName',
      'linkStatus', 'lastSeenAt'], whereEquals('linkStatus', 'unlinked')),
    recent(host, 'OutboundTask', ['id', 'name', 'status', 'executionMode', 'errorMessage',
      'conversationId', 'conversationName'], whereIn('status', ['failed', 'sending'])),
    recent(host, 'ExternalChannel', ['id', 'name', 'type', 'connectionStatus']),
    recent(host, 'AutomationAgent', ['id', 'name', 'status', 'mode', 'lastHeartbeatAt', 'lastError']),
    host.can('ExternalConversation', 'read')
      ? host.getOutboundState().then(parseOutboundState).catch(() => null)
      : Promise.resolve(null),
  ])
  return {
    counts: { all, reply, review, identity, takeover, exception },
    sections: {
      conversations: conversations.kind === 'ok'
        ? { kind: 'ok', value: [...conversations.value].sort((a, b) =>
          (b.lastInboundAt || '').localeCompare(a.lastInboundAt || '')) }
        : conversations,
      drafts, identities, exceptions, channels, agents,
    },
    outbound,
  }
}

function statusVariant(value?: string): 'secondary' | 'outline' | 'destructive' {
  if (value && ['failed', 'high', 'riskControl', 'loginExpired'].includes(value)) return 'destructive'
  if (value && ['waitingApproval', 'generated', 'medium', 'captcha', 'pageChanged',
    'heartbeatStale', 'human', 'unlinked', 'sending'].includes(value)) return 'secondary'
  return 'outline'
}

function heartbeatStatus(row: Item): string | undefined {
  if (row.status !== 'online') return row.status
  const heartbeat = parseServerTime(row.lastHeartbeatAt)
  return Number.isFinite(heartbeat) && Date.now() - heartbeat <= 5 * 60_000 ? 'online' : 'heartbeatStale'
}

function parseServerTime(value?: string): number {
  const timestamp = value?.replace(' ', 'T')
  if (!timestamp) return NaN
  return Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(timestamp) ? timestamp : `${timestamp}Z`)
}

function shanghaiTime(value?: string): string {
  const milliseconds = parseServerTime(value)
  if (!Number.isFinite(milliseconds)) return '—'
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(milliseconds))
  const part = (type: string) => parts.find((item) => item.type === type)?.value || '—'
  return `${part('year')}-${part('month')}-${part('day')} ${part('hour')}:${part('minute')} UTC+8`
}

function recordHref(entity: string, id?: string): string | undefined {
  return id ? `#${entity}/view/${encodeURIComponent(id)}` : undefined
}

function text(value?: string): string {
  return value || '—'
}

function RecordLink({ entity, id, name, allowed = true }: {
  entity: string; id?: string; name?: string; allowed?: boolean
}) {
  const href = allowed ? recordHref(entity, id) : undefined
  return href
    ? <a href={href} className="inline-flex min-h-11 items-center font-medium underline-offset-4 hover:underline">{text(name)}</a>
    : <>{allowed ? text(name) : '—'}</>
}

function Section({
  host, title, entity, state, columns, renderCells, onRetry,
}: {
  host: HostBridge
  title: string
  entity: string
  state: QueryState<Item[]>
  columns: string[]
  renderCells: (row: Item) => ReactNode
  onRetry: () => void
}) {
  const t = (value: string) => host.translate(value)
  return (
    <section className="min-w-0 border-t pt-5" aria-label={t(title)}>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-base font-semibold">{t(title)}</h2>
        {state.kind !== 'denied' && (
          <a href={`#${entity}`} className="inline-flex min-h-11 items-center text-sm font-medium underline-offset-4 hover:underline">
            {t('查看全部')}
          </a>
        )}
      </div>
      {state.kind === 'denied' ? (
        <Empty className="min-h-28 py-4">
          <EmptyHeader>
            <EmptyTitle>{t('没有读取权限')}</EmptyTitle>
            <EmptyDescription>{t('请联系管理员确认此模块的访问权限。')}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : state.kind === 'error' ? (
        <Alert variant="destructive">
          <AlertTitle>{t('无法加载记录')}</AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            {t('请检查连接后重试。')}
            <Button variant="outline" size="sm" className="min-h-11" onClick={onRetry}>{t('重试')}</Button>
          </AlertDescription>
        </Alert>
      ) : state.value.length === 0 ? (
        <Empty className="min-h-28 py-4">
          <EmptyHeader>
            <EmptyTitle>{t('暂无记录')}</EmptyTitle>
            <EmptyDescription>{t('收到相关业务数据后将在这里显示。')}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      ) : (
        <div className="max-w-full overflow-x-auto rounded-md border">
          <Table className="min-w-[560px]">
            <TableHeader>
              <TableRow>{columns.map((column) => <TableHead key={column}>{t(column)}</TableHead>)}</TableRow>
            </TableHeader>
            <TableBody>
              {state.value.map((row, index) => <TableRow key={row.id || `${entity}-${index}`}>{renderCells(row)}</TableRow>)}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  )
}

function LoadingScreen({ host }: { host: HostBridge }) {
  return (
    <div className="flex flex-col gap-6" role="status" aria-label={host.translate('正在加载客服数据…')}>
      <Skeleton className="h-11 w-64 max-w-full" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        {Array.from({ length: 6 }, (_, index) => <Skeleton key={index} className="h-16" />)}
      </div>
      <Skeleton className="h-32 w-full" />
      <Skeleton className="h-32 w-full" />
    </div>
  )
}

export default function ServiceScreen({ host }: ScreenProps) {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const generation = useRef(0)
  const t = (value: string) => host.translate(value)
  const badge = (value?: string) => value
    ? <Badge variant={statusVariant(value)}>{statusNames[value] ? t(statusNames[value]) : value}</Badge>
    : <span>—</span>

  const refresh = useCallback(async () => {
    const request = ++generation.current
    setRefreshing(true)
    try {
      const next = await loadServiceSnapshot(host)
      if (request === generation.current) setSnapshot(next)
    } catch {
      if (request === generation.current) setSnapshot(failedSnapshot())
    } finally {
      if (request === generation.current) setRefreshing(false)
    }
  }, [host])

  useEffect(() => {
    void refresh()
    return () => { generation.current += 1 }
  }, [refresh])

  const metricSpecs: { key: CountKey; label: string }[] = [
    { key: 'reply', label: '进行中会话' },
    { key: 'review', label: '待审核草稿' },
    { key: 'identity', label: '身份待确认' },
    { key: 'takeover', label: '人工接管中' },
    { key: 'exception', label: '发送异常' },
    { key: 'all', label: '会话总数' },
  ]
  const section = (key: SectionKey, title: string, entity: string, columns: string[], renderCells: (row: Item) => ReactNode) =>
    snapshot && <Section key={key} host={host} title={title} entity={entity} state={snapshot.sections[key]}
      columns={columns} renderCells={renderCells} onRetry={() => void refresh()} />

  return (
    <div className="fsh-ui-service flex min-w-0 flex-col gap-5" role="region" aria-label={t('AI 客服工作台')}>
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">{t('AI 客服工作台')}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t('统一收件箱、草稿审核、身份确认与发送异常')}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {host.can('ExternalConversation', 'read') && (
            <Button variant="outline" className="min-h-11" asChild>
              <a href="#Home/insights">{t('历史客户与今日建议')}</a>
            </Button>
          )}
          <Button variant="outline" className="min-h-11" disabled={refreshing} onClick={() => void refresh()}>
            {refreshing ? t('正在加载…') : t('刷新')}
          </Button>
        </div>
      </header>
      <p className="sr-only" role="status">{refreshing ? t('正在加载…') : snapshot ? t('数据已更新') : ''}</p>

      {snapshot ? (
        <>
          <Alert variant={snapshot.outbound === null || snapshot.outbound === false ? 'destructive' : 'default'} role="status">
            <AlertTitle>{snapshot.outbound === true ? t('全局停发已开启') :
              snapshot.outbound === false ? t('全局停发未开启') : t('外发开关状态未知')}</AlertTitle>
            <AlertDescription>{snapshot.outbound === true
              ? t('批准只创建发送任务，不会实际发送。')
              : snapshot.outbound === false
                ? t('批准的任务可由执行端领取并实际发送。')
                : t('无法读取状态接口，请勿假定任务不会实际发送。')}</AlertDescription>
          </Alert>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 border-y py-4 sm:grid-cols-3 lg:grid-cols-6" aria-label={t('客服概览')}>
            {metricSpecs.map(({ key, label }) => {
              const state = snapshot.counts[key]
              return (
                <div key={key} className="min-w-0">
                  <dt className="text-sm text-muted-foreground">{t(label)}</dt>
                  <dd className="mt-1 text-xl font-semibold tabular-nums" aria-label={`${t(label)}：${state.kind === 'ok' ? state.value : state.kind === 'denied' ? t('无权限') : t('未知')}`}>
                    {state.kind === 'ok' ? state.value : '—'}
                  </dd>
                </div>
              )
            })}
          </dl>
          <div className="grid min-w-0 gap-x-6 gap-y-6 xl:grid-cols-2">
            {section('conversations', '统一收件箱', 'ExternalConversation', ['会话', '状态', '接管', '身份', '负责人'], (row) => (
              <>
                <TableCell><RecordLink entity="ExternalConversation" id={row.id} name={row.name} /></TableCell>
                <TableCell>{badge(row.status)}</TableCell>
                <TableCell>{badge(row.controlMode)}</TableCell>
                <TableCell>{row.needsManualMatch ? <Badge variant="secondary">{t('身份待确认')}</Badge> : '—'}</TableCell>
                <TableCell>{text(row.assignedUserName) === '—' ? t('未分配') : row.assignedUserName}</TableCell>
              </>
            ))}
            {section('drafts', '需要审核的草稿', 'AIReplyDraft', ['草稿', '会话', '风险', '审核'], (row) => (
              <>
                <TableCell><RecordLink entity="AIReplyDraft" id={row.id} name={row.name} /></TableCell>
                <TableCell><RecordLink entity="ExternalConversation" id={row.conversationId} name={row.conversationName} allowed={host.can('ExternalConversation', 'read')} /></TableCell>
                <TableCell>{badge(row.riskLevel)}</TableCell>
                <TableCell><RecordLink entity="ExternalConversation" id={row.conversationId} name={t('打开会话审核')} allowed={host.can('ExternalConversation', 'read')} /></TableCell>
              </>
            ))}
            {section('identities', '身份待确认', 'ExternalIdentity', ['身份', '渠道', '平台用户', '状态'], (row) => (
              <>
                <TableCell><RecordLink entity="ExternalIdentity" id={row.id} name={row.displayName || row.name} /></TableCell>
                <TableCell>{row.channelType && statusNames[row.channelType] ? t(statusNames[row.channelType]) : text(row.channelType)}</TableCell>
                <TableCell>{row.externalUserId || t('匿名访客')}</TableCell>
                <TableCell>{badge(row.linkStatus)}</TableCell>
              </>
            ))}
            {section('exceptions', '失败或发送中的任务', 'OutboundTask', ['任务', '会话', '状态', '执行模式', '错误信息'], (row) => (
              <>
                <TableCell><RecordLink entity="OutboundTask" id={row.id} name={row.name} /></TableCell>
                <TableCell><RecordLink entity="ExternalConversation" id={row.conversationId} name={row.conversationName} allowed={host.can('ExternalConversation', 'read')} /></TableCell>
                <TableCell>{badge(row.status)}</TableCell>
                <TableCell>{row.executionMode === 'mock' ? badge('mock') : text(row.executionMode)}</TableCell>
                <TableCell className="max-w-52 truncate" title={row.errorMessage || undefined}>{text(row.errorMessage)}</TableCell>
              </>
            ))}
            {host.can('ExternalChannel', 'read') && section('channels', '渠道状态', 'ExternalChannel', ['渠道', '连接状态'], (row) => (
              <>
                <TableCell><RecordLink entity="ExternalChannel" id={row.id} name={row.name} /></TableCell>
                <TableCell>{badge(row.connectionStatus)}</TableCell>
              </>
            ))}
            {host.can('AutomationAgent', 'read') && section('agents', '执行端状态', 'AutomationAgent', ['执行端', '状态', '模式', '最后心跳'], (row) => (
              <>
                <TableCell><RecordLink entity="AutomationAgent" id={row.id} name={row.name} /></TableCell>
                <TableCell>{badge(heartbeatStatus(row))}</TableCell>
                <TableCell>{badge(row.mode)}</TableCell>
                <TableCell>{shanghaiTime(row.lastHeartbeatAt)}</TableCell>
              </>
            ))}
          </div>
        </>
      ) : <LoadingScreen host={host} />}
    </div>
  )
}
