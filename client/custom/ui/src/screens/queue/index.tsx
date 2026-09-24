import { useCallback, useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from 'react'
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

export const screenId = 'queue'

type Row = Record<string, any> & { id: string }
type QueueData = { entity: string; statusOptions: string[] }
type Filters = { text: string; channelId: string; assignedUserId: string; country: string; status: string; unreadCount: string; sla: string; order: string }
type Page = { rows: Row[]; total: number | null }
const PAGE_SIZE = 50
const blank: Filters = { text: '', channelId: '', assignedUserId: '', country: '', status: '', unreadCount: '', sla: '', order: 'desc' }
const statusNames: Record<string, string> = {
  heartbeatStale: '心跳超时', new: '新询盘', pending: '待回复', drafted: '已有草稿', waitingApproval: '待审核',
  readyToSend: '待发送', sending: '发送中', sent: '已发送', failed: '失败', replied: '已回复', closed: '已关闭',
  aiAssist: 'AI 辅助', human: '人工接管', generated: '待审核', edited: '已修改', approved: '已审核', rejected: '已拒绝',
  low: '低风险', medium: '中风险', high: '高风险', draft: '草稿', expired: '已过期', online: '在线', offline: '离线',
  mock: '演示', real: '真实', mockSent: '模拟已发送', confirmed: '已确认', unlinked: '待确认',
}
const definitions: Record<string, { title: string; subtitle: string; sort: string; columns: [string, string][] }> = {
  ExternalConversation: { title: '统一询盘', subtitle: '客户、询盘与后续行动', sort: 'lastMessageAt', columns: [
    ['customer','客户 / 联系人'],['accountName','客户公司'],['channelName','渠道'],['country','国家'],['product','产品'],
    ['lastMessagePreview','最后消息'],['unreadCount','未读'],['waiting','等待时间'],['assignedUserName','接待人'],
    ['status','接待状态'],['controlMode','控制模式'],['lastMessageAt','最后消息时间'],
  ] },
  AIReplyDraft: { title: 'AI 草稿审核队列', subtitle: '逐条审核回复内容与引用依据', sort: 'createdAt', columns: [
    ['customer','客户'],['accountName','公司'],['channelName','渠道'],['product','产品'],['summaryZh','原始问题摘要'],
    ['suggestedLanguage','语言'],['riskLevel','风险'],['missingInformation','缺失信息'],['assignedUserName','负责人'],
    ['createdAt','创建时间'],['waiting','等待时间'],['status','状态'],['review','审核'],
  ] },
  KnowledgeDocument: { title: '知识文档', subtitle: '产品资料、版本与审核有效期', sort: 'modifiedAt', columns: [
    ['name','文档名称'],['category','分类'],['product','产品'],['sourceType','文件类型'],['version','版本'],
    ['approvalStatus','审核状态'],['effectiveFrom','生效日期'],['effectiveTo','失效日期'],['checksum','校验值'],['indexedAt','最后索引时间'],
  ] },
  OutboundTask: { title: '发送任务', subtitle: '发送任务、执行结果与异常跟踪', sort: 'createdAt', columns: [
    ['conversationName','会话'],['customer','客户'],['channelName','渠道'],['status','状态'],['executionMode','执行模式'],
    ['idempotencyKey','幂等键'],['claimedBy','执行端'],['retryCount','重试'],['createdAt','创建时间'],
    ['completedAt','完成时间'],['platformMessageId','平台消息 ID'],['errorMessage','错误信息'],
  ] },
  AutomationAgent: { title: '平台执行端', subtitle: '平台执行端状态与最后心跳', sort: 'lastHeartbeatAt', columns: [
    ['name','执行端名称'],['status','状态'],['lastHeartbeatAt','最后心跳'],['capabilities','支持渠道'],['lastError','最近错误'],
  ] },
}
const statusVariant = (value: string): 'destructive' | 'secondary' | 'outline' =>
  ['failed','high','riskControl','loginExpired'].includes(value) ? 'destructive' :
    ['waitingApproval','generated','medium','human','heartbeatStale','mockSent'].includes(value) ? 'secondary' : 'outline'
const href = (scope: string, id?: string) => id ? `#${scope}/view/${encodeURIComponent(id)}` : undefined
const waitMinutes = (value?: string) => {
  if (!value) return null
  const date = Date.parse(value.replace(' ', 'T') + (/[zZ]|[+-]\d\d:\d\d$/.test(value) ? '' : 'Z'))
  return Number.isFinite(date) ? Math.max(0, Math.floor((Date.now() - date) / 60000)) : null
}
function statusValue(host: HostBridge, value: unknown): ReactNode {
  if (value == null || value === '') return '—'
  const key = String(value)
  return <Badge variant={statusVariant(key)}>{host.translate(statusNames[key] || key)}</Badge>
}
function RecordLink({ scope, id, label, host }: { scope: string; id?: string; label?: unknown; host: HostBridge }) {
  const text = String(label ?? '—')
  if (id && !host.can(scope, 'read')) return <>—</>
  return id && host.can(scope, 'read')
    ? <a className="inline-flex min-h-11 items-center font-medium underline-offset-4 hover:underline" href={href(scope, id)}>{text}</a>
    : <>{text}</>
}
function asText(value: unknown): string {
  if (Array.isArray(value)) return value.map((part) => typeof part === 'string' ? statusNames[part] || part : part?.name || part?.title || '资料').join('、') || '—'
  return value == null || value === '' ? '—' : String(value)
}
async function fetchPage(host: HostBridge, entity: string, def: typeof definitions[string], filters: Filters, offset: number): Promise<Page> {
  const where: Record<string, unknown>[] = []
  for (const [field, value] of Object.entries({ channelId: filters.channelId, assignedUserId: filters.assignedUserId,
    country: filters.country, [entity === 'KnowledgeDocument' ? 'approvalStatus' : 'status']: filters.status })) {
    if (value) where.push(value === 'unassigned' ? { type: 'isNull', attribute: field } : { type: 'equals', attribute: field, value })
  }
  if (filters.unreadCount) where.push({ type: 'greaterThan', attribute: 'unreadCount', value: 0 })
  if (filters.sla) where.push(
    { type: 'in', attribute: 'status', value: ['new','pending','drafted','waitingApproval'] },
    { type: 'before', attribute: 'lastInboundAt', value: new Date(Date.now() - 120 * 60_000).toISOString().slice(0,19).replace('T',' ') },
  )
  const result = await host.api.get<{ list?: Row[]; total?: number }>(entity, {
    where, textFilter: filters.text, orderBy: def.sort, order: filters.order, offset, maxSize: PAGE_SIZE,
  })
  let rows = result.list || []
  if (['AIReplyDraft','OutboundTask'].includes(entity) && host.can('ExternalConversation', 'read')) {
    const ids = [...new Set(rows.map((row) => row.conversationId).filter(Boolean))]
    if (ids.length) {
      try {
        const related = await host.api.get<{ list: Row[] }>('ExternalConversation', { where: [{ type: 'in', attribute: 'id', value: ids }], maxSize: PAGE_SIZE })
        const byId = new Map(related.list.map((row) => [row.id,row]))
        rows = rows.map((row) => ({ ...byId.get(row.conversationId), ...row,
          accountName: row.accountName || byId.get(row.conversationId)?.accountName,
          contactName: row.contactName || byId.get(row.conversationId)?.contactName,
          contactId: row.contactId || byId.get(row.conversationId)?.contactId,
          leadId: row.leadId || byId.get(row.conversationId)?.leadId,
          leadName: row.leadName || byId.get(row.conversationId)?.leadName,
          accountId: row.accountId || byId.get(row.conversationId)?.accountId,
          channelName: row.channelName || byId.get(row.conversationId)?.channelName,
          product: row.product || byId.get(row.conversationId)?.product,
        }))
      } catch { /* Related scope can be narrower than the list scope. */ }
    }
  }
  if (['ExternalConversation','AIReplyDraft','OutboundTask'].includes(entity)) {
    const leadIds = [...new Set(rows.map((row) => row.leadId).filter(Boolean))]
    if (leadIds.length && host.can('Lead', 'read')) {
      try {
        const leads = await host.api.get<{ list: Row[] }>('Lead', { where: [{ type: 'in', attribute: 'id', value: leadIds }], maxSize: PAGE_SIZE, select: 'id,accountName' })
        const byId = new Map(leads.list.map((row) => [row.id,row]))
        rows = rows.map((row) => ({ ...row, accountName: row.accountName || byId.get(row.leadId)?.accountName }))
      } catch { /* Optional enrichment. */ }
    }
  }
  if (entity === 'ExternalConversation' && host.can('ExternalMessage','read')) {
    await Promise.all(rows.filter((row) => !row.lastMessagePreview).map(async (row) => {
      try {
        const result = await host.api.get<{list:Row[]}>('ExternalMessage', {
          where:[{type:'equals',attribute:'conversationId',value:row.id}],orderBy:'sentAt',order:'desc',maxSize:1,select:'id,body',
        })
        row.lastMessagePreview = result.list?.[0]?.body
      } catch { /* A message can be hidden by record-level ACL. */ }
    }))
  }
  return { rows, total: typeof result.total === 'number' && result.total >= 0 ? result.total : null }
}
function Cell({ row, field, entity, host }: { row: Row; field: string; entity: string; host: HostBridge }) {
  let value = row[field]
  if (entity === 'AutomationAgent' && field === 'status' && value === 'online' && (waitMinutes(row.lastHeartbeatAt) ?? 999) > 5) value = 'heartbeatStale'
  if (entity === 'KnowledgeDocument' && field === 'approvalStatus' && row.effectiveTo && row.effectiveTo < new Date().toISOString().slice(0,10)) value = 'expired'
  let content: ReactNode
  if (field === 'customer') {
    const scope = row.contactId ? 'Contact' : row.leadId ? 'Lead' : 'Account'
    content = <RecordLink host={host} scope={scope} id={row.contactId || row.leadId || row.accountId} label={row.contactName || row.leadName || row.accountName || row.name} />
  } else if (field === 'name') content = <RecordLink host={host} scope={entity} id={row.id} label={value} />
  else if (field === 'accountName') content = <RecordLink host={host} scope="Account" id={row.accountId} label={value} />
  else if (field === 'conversationName' || field === 'review') content = <RecordLink host={host} scope="ExternalConversation" id={row.conversationId} label={field === 'review' ? host.translate('打开会话审核') : value} />
  else if (['status','approvalStatus','riskLevel','controlMode','executionMode'].includes(field)) content =
    entity === 'OutboundTask' && field === 'status' && value === 'pending' ? <Badge variant="outline">{host.translate('待执行')}</Badge> : statusValue(host, value)
  else if (field === 'waiting') {
    const closed = ['sent','replied','closed','approved','rejected'].includes(row.status)
    const minutes = waitMinutes(entity === 'ExternalConversation' ? row.lastInboundAt : row.createdAt)
    content = closed || minutes == null ? '—' : <span className={minutes >= 120 ? 'font-medium text-destructive' : ''}>{minutes} {host.translate('分钟')}</span>
  } else if (field === 'suggestedLanguage') content = host.translate(({ en: '英语', zh: '中文', zh_CN: '简体中文' } as Record<string,string>)[String(value)] || asText(value))
  else if (field === 'checksum' || field === 'idempotencyKey') content = value ? `${String(value).slice(0,12)}…` : '—'
  else content = asText(value)
  return <TableCell className="max-w-64 break-words align-top" title={asText(value)}>{content}</TableCell>
}
function FilterSelect({ label, value, onChange, options, t }: { label: string; value: string; onChange: (value: string) => void; options: [string,string][]; t: (value: string) => string }) {
  const id = useId()
  return <Field className="min-w-36 flex-1"><FieldLabel htmlFor={id}>{t(label)}</FieldLabel><Select value={value || '_all'} onValueChange={(v) => onChange(v === '_all' ? '' : v)}>
    <SelectTrigger id={id} className="min-h-11 w-full"><SelectValue /></SelectTrigger>
    <SelectContent><SelectGroup>{options.map(([key,text]) => <SelectItem key={key} value={key || '_all'}>{t(text)}</SelectItem>)}</SelectGroup></SelectContent>
  </Select></Field>
}
export default function QueueScreen({ host, data }: ScreenProps<QueueData>) {
  const entity = data?.entity || ''
  const def = definitions[entity]
  const [filters, setFilters] = useState<Filters>(blank)
  const [submitted, setSubmitted] = useState<Filters>(blank)
  const [offset, setOffset] = useState(0)
  const [page, setPage] = useState<Page | null>(null)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(true)
  const [reload, setReload] = useState(0)
  const [channels, setChannels] = useState<[string,string][]>([])
  const [users, setUsers] = useState<[string,string][]>([])
  const [outbound, setOutbound] = useState<boolean | null>(null)
  const generation = useRef(0)
  const t = (label: string) => host.translate(label)
  const setFilter = (key: keyof Filters, value: string, immediate = true) => {
    const next = { ...filters, [key]: value }
    setFilters(next)
    if (immediate) { setOffset(0); setSubmitted(next) }
  }
  const submit = (event: FormEvent) => { event.preventDefault(); setOffset(0); setSubmitted({ ...filters }) }
  const load = useCallback(() => { setReload((n) => n + 1) }, [])
  useEffect(() => {
    if (entity !== 'ExternalConversation') return
    let active = true
    const fetchOptions = async (scope: string, setter: (rows: [string,string][]) => void) => {
      if (!host.can(scope, 'read')) return
      try {
        const response = await host.api.get<{ list: Row[] }>(scope, { maxSize: 200, orderBy: 'name' })
        if (active) setter((response.list || []).map((row) => [row.id, row.name]))
      } catch { /* Directory access can be more restrictive. */ }
    }
    void fetchOptions('ExternalChannel', setChannels)
    void fetchOptions('User', setUsers)
    return () => { active = false }
  }, [host, entity])
  useEffect(() => {
    if (entity !== 'OutboundTask') return
    let active = true
    void host.getOutboundState().then((state) => { if (active) setOutbound(state.paused) }).catch(() => { if (active) setOutbound(null) })
    return () => { active = false }
  }, [host, entity, reload])
  useEffect(() => {
    if (!def || !host.can(entity, 'read')) return
    const request = ++generation.current
    setLoading(true); setError(false)
    void fetchPage(host, entity, def, submitted, offset).then((next) => {
      if (request === generation.current) setPage(next)
    }).catch(() => { if (request === generation.current) setError(true) })
      .finally(() => { if (request === generation.current) setLoading(false) })
    return () => { generation.current += 1 }
  }, [host, entity, def, submitted, offset, reload])
  if (!def) return <Alert variant="destructive"><AlertTitle>{t('未知列表')}</AlertTitle></Alert>
  if (!host.can(entity, 'read')) return <Empty><EmptyHeader><EmptyTitle>{t('没有读取权限')}</EmptyTitle></EmptyHeader></Empty>
  const last = page?.total != null ? offset + PAGE_SIZE >= page.total : (page?.rows.length || 0) < PAGE_SIZE
  return <section className="flex min-w-0 flex-col gap-5" aria-label={t(def.title)}>
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h1 className="text-2xl font-semibold tracking-tight">{t(def.title)}</h1><p className="mt-1 text-sm text-muted-foreground">{t(def.subtitle)}</p></div><Button variant="outline" className="min-h-11" onClick={load} disabled={loading}>{t('刷新')}</Button></header>
    {entity === 'OutboundTask' && <Alert variant={outbound === true ? 'default' : 'destructive'} role="status"><AlertTitle>{outbound === true ? t('全局停发已开启') : outbound === false ? t('全局停发未开启') : t('外发开关状态未知')}</AlertTitle><AlertDescription>{outbound === true ? t('批准只创建发送任务，不会实际发送。') : outbound === false ? t('批准的任务可由执行端领取并实际发送。') : t('无法读取状态接口，请勿假定任务不会实际发送。')}</AlertDescription></Alert>}
    {entity === 'KnowledgeDocument' && <Alert><AlertDescription>{t('AI 只能使用“已审核”且在有效期内的资料。草稿及已过期文档不可作为回复依据。')}</AlertDescription></Alert>}
    <form onSubmit={submit} className="rounded-lg border p-4"><FieldGroup className="gap-4"><div className="flex flex-wrap items-end gap-3">
      <Field className="min-w-44 flex-[2]"><FieldLabel htmlFor="queue-search">{t('搜索')}</FieldLabel><Input id="queue-search" type="search" className="min-h-11" value={filters.text} onChange={(e) => setFilter('text', e.target.value, false)} placeholder={t('搜索名称或询盘内容')} /></Field>
      {entity === 'ExternalConversation' && <>
        <FilterSelect label="渠道" value={filters.channelId} onChange={(v) => setFilter('channelId',v)} t={t} options={[["","全部渠道"],...channels]} />
        <FilterSelect label="负责人" value={filters.assignedUserId} onChange={(v) => setFilter('assignedUserId',v)} t={t} options={[["","全部负责人"],["unassigned","未分配"],...users]} />
        <Field className="min-w-36 flex-1"><FieldLabel htmlFor="queue-country">{t('国家')}</FieldLabel><Input id="queue-country" className="min-h-11" value={filters.country} onChange={(e) => setFilter('country',e.target.value,false)} placeholder={t('国家 / 地区')} /></Field>
      </>}
      <FilterSelect label="状态" value={filters.status} onChange={(v) => setFilter('status',v)} t={t} options={[["","全部状态"],...(data?.statusOptions || []).map((v): [string,string] => [v, entity === 'OutboundTask' && v === 'pending' ? '待执行' : statusNames[v] || v])]} />
      {entity === 'ExternalConversation' && <>
        <FilterSelect label="未读" value={filters.unreadCount} onChange={(v) => setFilter('unreadCount',v)} t={t} options={[["","全部"],["1","仅未读"]]} />
        <FilterSelect label="SLA" value={filters.sla} onChange={(v) => setFilter('sla',v)} t={t} options={[["","全部"],["1","超过 120 分钟"]]} />
      </>}
      <FilterSelect label="排序" value={filters.order} onChange={(v) => setFilter('order',v)} t={t} options={[["desc","最新在前"],["asc","最早在前"]]} />
    </div><div className="flex flex-wrap gap-2"><Button type="submit" className="min-h-11">{t('查询')}</Button><Button type="button" variant="ghost" className="min-h-11" onClick={() => { setFilters(blank); setSubmitted(blank); setOffset(0) }}>{t('清除筛选')}</Button></div></FieldGroup></form>
    <div aria-live="polite" className="min-w-0">{loading ? <div role="status" className="flex flex-col gap-2"><Skeleton className="h-12" /><Skeleton className="h-12" /><Skeleton className="h-12" /></div> : error ? <Alert variant="destructive"><AlertTitle>{t('无法加载记录')}</AlertTitle><AlertDescription>{t('请检查访问权限或点击刷新重试。')} <Button variant="outline" onClick={load}>{t('重试')}</Button></AlertDescription></Alert> : !page?.rows.length ? <Empty><EmptyHeader><EmptyTitle>{t('暂无符合条件的记录')}</EmptyTitle><EmptyDescription>{t('可清除筛选或稍后刷新。')}</EmptyDescription></EmptyHeader></Empty> : <div className="max-w-full overflow-x-auto rounded-lg border"><Table className="min-w-max"><TableHeader><TableRow>{def.columns.map(([field,label]) => <TableHead key={field} scope="col">{t(label)}</TableHead>)}</TableRow></TableHeader><TableBody>{page.rows.map((row) => <TableRow key={row.id} tabIndex={0} aria-label={`${t('打开记录')}：${row.name || row.contactName || row.leadName || row.id}`} className={row.unreadCount ? 'bg-muted/40' : ''} onClick={(e) => { if (!(e.target as HTMLElement).closest('a,button')) host.navigate(href(entity,row.id)!) }} onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); host.navigate(href(entity,row.id)!) } }}>{def.columns.map(([field]) => <Cell key={field} host={host} entity={entity} row={row} field={field} />)}</TableRow>)}</TableBody></Table></div>}</div>
    <nav className="flex flex-wrap items-center justify-end gap-3" aria-label={t('分页')}><span className="text-sm text-muted-foreground">{page?.rows.length ? offset + 1 : 0}–{offset + (page?.rows.length || 0)} / {page?.total ?? t('更多')}</span><Button variant="outline" className="min-h-11" disabled={loading || offset === 0} onClick={() => setOffset(Math.max(0,offset-PAGE_SIZE))}>{t('上一页')}</Button><Button variant="outline" className="min-h-11" disabled={loading || last} onClick={() => setOffset(offset+PAGE_SIZE)}>{t('下一页')}</Button></nav>
  </section>
}
