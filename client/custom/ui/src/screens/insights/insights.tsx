import { useEffect, useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { HostBridge, ScreenProps } from '@/lib/host'

export const screenId = 'insights'

type AnalysisStatus = 'pending' | 'completed' | 'failed' | 'stale' | string
type Customer = { type: 'Account' | 'Contact' | 'Lead'; id: string } | null
type Row = { id: string; name?: string; externalId?: string; owner?: string; lastMessageAt?: string; needsManualMatch?: boolean; customer?: Customer; analysisStatus?: AnalysisStatus; analysisError?: string }
type Suggestion = Row & { priority?: number; reason?: string; action?: string }
type Coverage = { platformVisible?: number | null; imported?: number | null; failedSync?: number | null; pendingIdentity?: number | null; analysisCompleted?: number | null; analysisFailed?: number | null; analysisStale?: number | null; lastSyncAt?: string | null; lastAnalysisAt?: string | null; reconciled?: boolean; reason?: string }
type Overview = { date?: string; timezone?: string; outboundPaused?: boolean | null; scope?: 'own' | 'all'; coverage?: Coverage; suggestions?: Suggestion[]; suggestionTotal?: number; list?: Row[]; total?: number; offset?: number; limit?: number }
type Analysis = Record<string, unknown>
type Detail = Row & { analysis?: Analysis | null; analysisNotice?: string; model?: string; promptVersion?: string; analysisAt?: string; evidence?: { id: string; sentAt?: string; direction?: string }[] }
type LoadState<T> = { kind: 'loading' } | { kind: 'ok'; value: T } | { kind: 'error' } | { kind: 'denied' }
type Filter = { q: string; status: string }

const PAGE_SIZE = 25
const fields = [
  ['中文摘要', 'summaryZh'], ['需求', 'demand'], ['产品', 'products'], ['历史进展', 'historyProgress'],
  ['最新状态', 'latestStatus'], ['购买话题信号（待确认）', 'buyingSignals'], ['风险', 'risks'],
  ['缺失信息', 'missingFacts'], ['下一步', 'nextAction'],
] as const

function dateTime(value: string | null | undefined, host: HostBridge): string {
  if (!value) return '—'
  const timestamp = value.replace(' ', 'T')
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(timestamp) ? timestamp : `${timestamp}Z`)
  if (Number.isNaN(date.getTime())) return host.translate('时间待确认')
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23' }).formatToParts(date)
  const part = (type: string) => parts.find(item => item.type === type)?.value || '—'
  return `${part('year')}-${part('month')}-${part('day')} ${part('hour')}:${part('minute')} UTC+8`
}

function recordHref(type: string, id?: string) { return id ? `#${type}/view/${encodeURIComponent(id)}` : undefined }

function RecordLink({ type, id, children }: { type: string; id?: string; children: React.ReactNode }) {
  const href = recordHref(type, id)
  return href ? <a href={href} className="inline-flex min-h-11 items-center font-medium underline-offset-4 hover:underline">{children}</a> : <>{children}</>
}

function analysisLabel(host: HostBridge, status?: string): string {
  const labels: Record<string, string> = { pending: '未分析', completed: '已完成', failed: '分析失败', stale: '待重新分析' }
  return host.translate(labels[status || ''] || status || '未分析')
}

function Metric({ host, label, value }: { host: HostBridge; label: string; value: number | null | undefined }) {
  const t = (key: string) => host.translate(key)
  const text = typeof value === 'number' && Number.isFinite(value) ? String(value) : t('待核对')
  return <div className="min-w-0"><dt className="text-sm text-muted-foreground">{t(label)}</dt><dd className="mt-1 text-xl font-semibold tabular-nums" aria-label={`${t(label)}：${text}`}>{text}</dd></div>
}

function OverviewLoading({ host }: { host: HostBridge }) {
  return <div className="flex flex-col gap-5" role="status" aria-label={host.translate('正在读取同步与分析状态…')}>
    <Skeleton className="h-16 w-full" /><div className="grid grid-cols-2 gap-3 md:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-16" />)}</div><Skeleton className="h-32 w-full" />
  </div>
}

function Value({ value, host }: { value: unknown; host: HostBridge }) {
  let content = ''
  if (Array.isArray(value)) content = value.filter(item => typeof item === 'string' || typeof item === 'number').join('；')
  else if (typeof value === 'string' || typeof value === 'number') content = String(value)
  return <>{content || host.translate('待确认')}</>
}

export default function InsightsScreen({ host }: ScreenProps) {
  const t = (key: string) => host.translate(key)
  const [draftQ, setDraftQ] = useState('')
  const [draftStatus, setDraftStatus] = useState('')
  const [filter, setFilter] = useState<Filter>({ q: '', status: '' })
  const [offset, setOffset] = useState(0)
  const [refreshKey, setRefreshKey] = useState(0)
  const [overview, setOverview] = useState<LoadState<Overview>>({ kind: 'loading' })
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detailRetry, setDetailRetry] = useState(0)
  const [detail, setDetail] = useState<LoadState<Detail> | null>(null)
  const allowed = host.can('ExternalConversation', 'read')

  useEffect(() => {
    if (!allowed) { setOverview({ kind: 'denied' }); return }
    let active = true
    setOverview({ kind: 'loading' })
    host.api.get<Overview>('Fusanhe/insights', { q: filter.q, status: filter.status, offset, limit: PAGE_SIZE })
      .then(value => { if (active) setOverview(value && Array.isArray(value.list) && Array.isArray(value.suggestions) && value.coverage ? { kind: 'ok', value } : { kind: 'error' }) })
      .catch(() => { if (active) setOverview({ kind: 'error' }) })
    return () => { active = false }
  }, [host, allowed, filter, offset, refreshKey])

  useEffect(() => {
    if (!selectedId) { setDetail(null); return }
    let active = true
    setDetail({ kind: 'loading' })
    host.api.get<Detail>(`Fusanhe/insights/${encodeURIComponent(selectedId)}`)
      .then(value => { if (active) setDetail(value && value.id === selectedId ? { kind: 'ok', value } : { kind: 'error' }) })
      .catch(() => { if (active) setDetail({ kind: 'error' }) })
    return () => { active = false }
  }, [host, selectedId, detailRetry])

  const submit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setSelectedId(null)
    setOffset(0)
    setFilter({ q: draftQ.trim().slice(0, 100), status: draftStatus })
    setRefreshKey(key => key + 1)
  }
  const retry = () => setRefreshKey(key => key + 1)
  const data = overview.kind === 'ok' ? overview.value : null
  const coverage = data?.coverage
  const outbound = data?.outboundPaused
  const total = typeof data?.total === 'number' && data.total >= 0 ? data.total : null
  const page = Math.floor(offset / PAGE_SIZE) + 1

  return <div className="flex min-w-0 flex-col gap-5" role="region" aria-label={t('历史客户与今日建议')}>
    <header className="flex flex-wrap items-start justify-between gap-3">
      <div><h1 className="text-2xl font-semibold tracking-tight">{t('历史客户与今日建议')}</h1><p className="mt-1 text-sm text-muted-foreground">{t('Alibaba · 按会话核对 · 上海时间')}</p></div>
      <Button asChild variant="outline" className="min-h-11"><a href="#Home">{t('返回工作台')}</a></Button>
    </header>
    {overview.kind === 'loading' ? <OverviewLoading host={host} /> : overview.kind === 'denied' ?
      <Empty><EmptyHeader><EmptyTitle>{t('没有读取权限')}</EmptyTitle><EmptyDescription>{t('请联系管理员确认此模块的访问权限。')}</EmptyDescription></EmptyHeader></Empty>
      : overview.kind === 'error' ? <Alert variant="destructive" role="alert"><AlertTitle>{t('数据未能刷新，请勿依据旧统计进行对账。')}</AlertTitle><AlertDescription className="flex flex-wrap items-center gap-2">{t('读取失败或没有访问权限。请重试。')}<Button variant="outline" className="min-h-11" onClick={retry}>{t('重试')}</Button></AlertDescription></Alert>
        : data && <>
          <Alert variant={outbound === true ? 'default' : 'destructive'} role="status"><AlertTitle>{outbound === true ? t('全局停发已开启 · 本页只提供建议，下一步由人工执行。') : outbound === false ? t('注意：全局停发未开启。本页不会发送消息。') : t('外发状态未知。本页不会发送消息；请先核查发送开关。')}</AlertTitle></Alert>
          <section className="border-y py-4" aria-label={t('同步覆盖范围')}>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4 xl:grid-cols-7">
              <Metric host={host} label="平台可见会话" value={coverage?.platformVisible} />
              <Metric host={host} label="已导入会话" value={coverage?.imported} />
              <Metric host={host} label="同步失败" value={coverage?.failedSync} />
              <Metric host={host} label="身份待确认" value={coverage?.pendingIdentity} />
              <Metric host={host} label="分析完成" value={coverage?.analysisCompleted} />
              <Metric host={host} label="分析失败" value={coverage?.analysisFailed} />
              <Metric host={host} label="分析已过期" value={coverage?.analysisStale} />
            </dl>
            <div className="mt-3 flex flex-col gap-1 text-sm text-muted-foreground">
              <p>{coverage?.reason ? t(coverage.reason) : t('同步覆盖范围未核实')}{data.scope === 'own' ? ` ${t('当前仅显示本人负责的会话。')}` : ''}</p>
              <p>{t('最后同步')}：{dateTime(coverage?.lastSyncAt, host)} · {t('最后分析')}：{dateTime(coverage?.lastAnalysisAt, host)}</p>
            </div>
          </section>
          <section className="min-w-0" aria-label={t('今日建议')}>
            <div className="mb-3 flex flex-wrap items-baseline gap-2"><h2 className="text-base font-semibold">{t('今日建议')}</h2><p className="text-sm text-muted-foreground">{data.date || '—'} · {typeof data.suggestionTotal === 'number' ? data.suggestionTotal : '—'} {t('条')}{(data.suggestionTotal || 0) > 50 ? ` · ${t('仅显示优先 50 条')}` : ''}</p></div>
            {data.suggestions?.length ? <div className="max-w-full overflow-x-auto rounded-md border"><Table className="min-w-[680px]"><TableHeader><TableRow><TableHead>{t('优先级')}</TableHead><TableHead>{t('客户会话 / 依据')}</TableHead><TableHead>{t('原因与建议动作')}</TableHead><TableHead>{t('负责人')}</TableHead></TableRow></TableHeader><TableBody>{data.suggestions.map((item, index) => <TableRow key={item.id || index}><TableCell className="align-top font-medium">P{item.priority ?? '—'}</TableCell><TableCell className="align-top"><RecordLink type="ExternalConversation" id={item.id}>{item.name || '—'}</RecordLink></TableCell><TableCell className="min-w-64 align-top"><span className="font-medium">{item.reason ? t(item.reason) : '—'}</span><br /><span className="text-muted-foreground">{item.action ? t(item.action) : '—'}</span></TableCell><TableCell className="align-top">{item.owner || t('未分配')}</TableCell></TableRow>)}</TableBody></Table></div>
              : <Empty className="min-h-28 py-4"><EmptyHeader><EmptyTitle>{t('暂无建议')}</EmptyTitle><EmptyDescription>{t('暂无建议。导入真实会话后，系统按身份与跟进状态生成建议。')}</EmptyDescription></EmptyHeader></Empty>}
          </section>
          <section className="min-w-0 border-t pt-5" aria-label={t('历史客户会话')}>
            <h2 className="mb-3 text-base font-semibold">{t('历史客户会话')}</h2>
            <form onSubmit={submit} className="mb-3" aria-label={t('筛选历史会话')}>
              <FieldGroup className="flex flex-col gap-3 sm:flex-row sm:items-end">
                <Field className="min-w-0 flex-1"><FieldLabel htmlFor="fsh-insights-query">{t('搜索')}</FieldLabel><Input id="fsh-insights-query" value={draftQ} onChange={event => setDraftQ(event.target.value)} placeholder={t('客户会话名称 / 平台 ID')} maxLength={100} className="min-h-11" /></Field>
                <Field className="sm:w-52"><FieldLabel htmlFor="fsh-insights-status">{t('状态')}</FieldLabel><Select value={draftStatus || 'all'} onValueChange={value => setDraftStatus(value === 'all' ? '' : value)}><SelectTrigger id="fsh-insights-status" className="min-h-11 w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup>{[['all', '全部'], ['pending', '未分析'], ['completed', '已分析'], ['failed', '分析失败'], ['stale', '待重新分析'], ['unmatched', '身份待确认']].map(([value, label]) => <SelectItem key={value} value={value}>{t(label)}</SelectItem>)}</SelectGroup></SelectContent></Select></Field>
                <Button type="submit" className="min-h-11">{t('查询 / 刷新')}</Button>
              </FieldGroup>
            </form>
            {data.list?.length ? <div className="max-w-full overflow-x-auto rounded-md border"><Table className="min-w-[760px]"><TableHeader><TableRow><TableHead>{t('客户会话')}</TableHead><TableHead>{t('平台 ID')}</TableHead><TableHead>{t('身份')}</TableHead><TableHead>{t('负责人')}</TableHead><TableHead>{t('最近消息')}</TableHead><TableHead>{t('AI 分析')}</TableHead></TableRow></TableHeader><TableBody>{data.list.map((row, index) => <TableRow key={row.id || index}><TableCell><div className="flex flex-col items-start"><RecordLink type="ExternalConversation" id={row.id}>{row.name || '—'}</RecordLink>{row.customer && <RecordLink type={row.customer.type} id={row.customer.id}>{t('打开 CRM 客户')}</RecordLink>}</div></TableCell><TableCell>{row.externalId || '—'}</TableCell><TableCell><Badge variant={row.needsManualMatch ? 'secondary' : 'outline'}>{row.needsManualMatch ? t('待确认') : t('已关联')}</Badge></TableCell><TableCell>{row.owner || t('未分配')}</TableCell><TableCell className="whitespace-nowrap">{dateTime(row.lastMessageAt, host)}</TableCell><TableCell><div className="flex flex-wrap items-center gap-2"><Badge variant={row.analysisStatus === 'failed' ? 'destructive' : 'outline'}>{analysisLabel(host, row.analysisStatus)}</Badge><Button variant="link" className="min-h-11" type="button" onClick={() => setSelectedId(row.id)}>{t('查看分析')}</Button></div></TableCell></TableRow>)}</TableBody></Table></div>
              : <Empty className="min-h-28 py-4"><EmptyHeader><EmptyTitle>{t('暂无记录')}</EmptyTitle><EmptyDescription>{t('没有符合条件的历史会话。未同步的数据与模拟记录不会计入这里。')}</EmptyDescription></EmptyHeader></Empty>}
            <nav className="mt-3 flex flex-wrap items-center justify-end gap-3" aria-label={t('历史会话分页')}><Button variant="outline" className="min-h-11" disabled={offset === 0} onClick={() => { setSelectedId(null); setOffset(value => Math.max(0, value - PAGE_SIZE)) }}>{t('上一页')}</Button><span className="text-sm" role="status">{t('第')} {page} {t('页')} · {total === null ? '—' : total} {t('条会话')}</span><Button variant="outline" className="min-h-11" disabled={total === null || offset + (data.list?.length || 0) >= total} onClick={() => { setSelectedId(null); setOffset(value => value + PAGE_SIZE) }}>{t('下一页')}</Button></nav>
          </section>
          <section className="min-w-0 border-t pt-5" aria-label={t('客户分析')}>
            <h2 className="mb-3 text-base font-semibold">{t('客户分析')}</h2>
            {!selectedId ? <p className="text-sm text-muted-foreground">{t('选择会话的“查看分析”，核对画像与原始依据。')}</p>
              : detail?.kind === 'loading' ? <Skeleton className="h-24 w-full" role="status" aria-label={t('正在读取…')} />
                : detail?.kind === 'error' ? <Alert variant="destructive" role="alert"><AlertTitle>{t('分析读取失败或无权限，请重新选择会话。')}</AlertTitle><AlertDescription><Button variant="outline" className="min-h-11" onClick={() => setDetailRetry(value => value + 1)}>{t('重试')}</Button></AlertDescription></Alert>
                  : detail?.kind === 'ok' && <AnalysisDetail host={host} detail={detail.value} />}
          </section>
        </>}
  </div>
}

function AnalysisDetail({ host, detail }: { host: HostBridge; detail: Detail }) {
  const t = (key: string) => host.translate(key)
  return <div className="flex min-w-0 flex-col gap-3">
    <div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-semibold">{detail.name || '—'}</h3><Badge variant={detail.analysisStatus === 'failed' ? 'destructive' : 'outline'}>{analysisLabel(host, detail.analysisStatus)}</Badge></div>
    <p className="text-sm text-muted-foreground">{detail.analysisNotice ? t(detail.analysisNotice) : t('未提供')}{detail.analysisError ? ` · ${t('错误代码')}：${detail.analysisError}` : ''}</p>
    {detail.analysisStatus === 'stale' && <Alert><AlertTitle>{t('来源已有变化，下方为旧分析，请等待重新分析。')}</AlertTitle></Alert>}
    {detail.analysis && <>
      <dl className="grid min-w-0 gap-x-6 gap-y-3 border-y py-4 md:grid-cols-2">{fields.map(([label, key]) => <div key={key} className="min-w-0"><dt className="text-sm font-medium">{t(label)}</dt><dd className="mt-1 break-words text-sm text-muted-foreground"><Value value={detail.analysis?.[key]} host={host} /></dd></div>)}</dl>
      <p className="text-sm text-muted-foreground">{t('模型')}：{detail.model || '—'} · {t('生成时间')}：{dateTime(detail.analysisAt, host)} · {detail.promptVersion || '—'}</p>
      <div className="flex flex-wrap items-center gap-2 text-sm"><span className="font-medium">{t('分析依据')}：</span>{detail.evidence?.length ? detail.evidence.map(item => <RecordLink key={item.id} type="ExternalMessage" id={item.id}>{dateTime(item.sentAt, host)} {t(item.direction === 'inbound' ? '客户消息' : '我方消息')}</RecordLink>) : <span>{t('无可读取的证据')}</span>}</div>
    </>}
    <RecordLink type="ExternalConversation" id={detail.id}>{t('打开原始会话与消息记录')}</RecordLink>
  </div>
}
