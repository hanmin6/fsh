import type { ReactNode } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { HostBridge } from '@/lib/host'

export type QueryState<T> = { kind: 'ok'; value: T } | { kind: 'denied' } | { kind: 'error' }
export type Where = { type: 'in' | 'equals'; attribute: string; value: string | string[] }
type ListResponse<T> = { list?: T[]; total?: number }

export async function count(host: HostBridge, entity: string, where?: Where): Promise<QueryState<number>> {
  if (!host.can(entity, 'read')) return { kind: 'denied' }
  try {
    const response = await host.api.get<ListResponse<unknown>>(entity, { maxSize: 1, where: where ? [where] : [] })
    return Number.isInteger(response?.total) && response.total! >= 0
      ? { kind: 'ok', value: response.total! } : { kind: 'error' }
  } catch { return { kind: 'error' } }
}

export async function recent<T>(host: HostBridge, entity: string, select: string[], where?: Where, orderBy = 'createdAt'): Promise<QueryState<T[]>> {
  if (!host.can(entity, 'read')) return { kind: 'denied' }
  try {
    const response = await host.api.get<ListResponse<T>>(entity, {
      maxSize: 6, orderBy, order: 'desc', select: select.join(','), where: where ? [where] : [],
    })
    return Array.isArray(response?.list) ? { kind: 'ok', value: response.list } : { kind: 'error' }
  } catch { return { kind: 'error' } }
}

export function metricValue(state: QueryState<number>, host: HostBridge): string {
  return state.kind === 'ok' ? String(state.value) : host.translate(state.kind === 'denied' ? '无权限' : '未知')
}

export function MetricStrip({ host, items }: { host: HostBridge; items: { label: string; state: QueryState<number> }[] }) {
  return <dl className="grid grid-cols-2 gap-x-4 gap-y-3 border-y py-4 sm:grid-cols-4" aria-label={host.translate('业务概览')}>
    {items.map(({ label, state }) => <div key={label} className="min-w-0">
      <dt className="text-sm text-muted-foreground">{host.translate(label)}</dt>
      <dd className="mt-1 text-xl font-semibold tabular-nums" aria-label={`${host.translate(label)}：${metricValue(state, host)}`}>
        {state.kind === 'ok' ? state.value : '—'}
      </dd>
    </div>)}
  </dl>
}

export function Loading({ host, label }: { host: HostBridge; label: string }) {
  return <div className="flex flex-col gap-5" role="status" aria-label={host.translate(label)}>
    <Skeleton className="h-11 w-64 max-w-full" />
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-16" />)}</div>
    <Skeleton className="h-32 w-full" />
  </div>
}

export function RecordLink({ entity, id, name, allowed = true }: { entity: string; id?: string; name?: string; allowed?: boolean }) {
  if (!allowed || !id) return <>{allowed ? name || '—' : '—'}</>
  return <a href={`#${entity}/view/${encodeURIComponent(id)}`} className="inline-flex min-h-11 items-center font-medium underline-offset-4 hover:underline">{name || '—'}</a>
}

export function StateBadge({ host, value }: { host: HostBridge; value?: string }) {
  if (!value) return <span>—</span>
  const labels: Record<string, string> = {
    new: '新询盘', pending: '待回复', drafted: '已有草稿', waitingApproval: '待审核',
    readyToSend: '待发送', sending: '发送中', sent: '已发送', failed: '失败',
    replied: '已回复', closed: '已关闭', aiAssist: 'AI 辅助', human: '人工接管',
    unlinked: '待确认', confirmed: '已确认', generated: '待审核', edited: '已修改',
    approved: '已审核', rejected: '已拒绝', low: '低风险', medium: '中风险',
    high: '高风险', mock: '演示', online: '在线', offline: '离线',
  }
  const variant = ['failed', 'high'].includes(value) ? 'destructive'
    : ['pending', 'waitingApproval', 'human', 'unlinked', 'sending'].includes(value) ? 'secondary' : 'outline'
  return <Badge variant={variant}>{host.translate(labels[value] || value)}</Badge>
}

export function RecordSection<T>({ host, title, entity, state, headers, renderRow, onRetry }: {
  host: HostBridge; title: string; entity: string; state: QueryState<T[]>; headers: string[];
  renderRow: (row: T, index: number) => ReactNode; onRetry: () => void;
}) {
  const t = (text: string) => host.translate(text)
  return <section className="min-w-0 border-t pt-5" aria-label={t(title)}>
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-base font-semibold">{t(title)}</h2>
      {state.kind !== 'denied' && <a href={`#${entity}`} className="inline-flex min-h-11 items-center text-sm font-medium underline-offset-4 hover:underline">{t('查看全部')}</a>}
    </div>
    {state.kind === 'denied' ? <Empty className="min-h-28 py-4"><EmptyHeader><EmptyTitle>{t('没有读取权限')}</EmptyTitle><EmptyDescription>{t('请联系管理员确认此模块的访问权限。')}</EmptyDescription></EmptyHeader></Empty>
      : state.kind === 'error' ? <Alert variant="destructive"><AlertTitle>{t('无法加载记录')}</AlertTitle><AlertDescription className="flex flex-wrap items-center gap-2">{t('请检查连接后重试。')}<Button variant="outline" className="min-h-11" onClick={onRetry}>{t('重试')}</Button></AlertDescription></Alert>
        : state.value.length === 0 ? <Empty className="min-h-28 py-4"><EmptyHeader><EmptyTitle>{t('暂无记录')}</EmptyTitle><EmptyDescription>{t('收到相关业务数据后将在这里显示。')}</EmptyDescription></EmptyHeader></Empty>
          : <div className="max-w-full overflow-x-auto rounded-md border"><Table className="min-w-[560px]"><TableHeader><TableRow>{headers.map(h => <TableHead key={h}>{t(h)}</TableHead>)}</TableRow></TableHeader><TableBody>{state.value.map((row, i) => <TableRow key={(row as { id?: string }).id || i}>{renderRow(row, i)}</TableRow>)}</TableBody></Table></div>}
  </section>
}

export { TableCell }
