import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from '@/components/ui/empty'
import { Field, FieldGroup, FieldLabel } from '@/components/ui/field'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import type { HostBridge, ScreenProps } from '@/lib/host'
import { canApproveDraft, canEditDraft, outboundDescription, type Draft } from './policy'

export const screenId = 'conversation'
type Row = Record<string, any> & { id: string }
type Data = { conversationId: string; initialConversation?: Row }
type Snapshot = { conversation: Row; messages: Row[]; messageTotal: number; drafts: Row[]; conversations: Row[]; tasks: Row[]; identity: Row | null; handoffTasks: Row[] }
type Candidate = { type: string; id: string; name: string; emailAddress?: string; phoneNumber?: string }
const statusNames: Record<string, string> = {
  new: '新询盘', pending: '待回复', drafted: '已有草稿', waitingApproval: '待审核', readyToSend: '待发送',
  sending: '发送中', sent: '已发送', failed: '失败', replied: '已回复', closed: '已关闭', aiAssist: 'AI 辅助', human: '人工接管',
  generated: '待审核', edited: '已修改', approved: '已审核', rejected: '已拒绝', low: '低风险', medium: '中风险', high: '高风险',
  confirmed: '已确认', unlinked: '待确认', inbound: '收到', outbound: '发出', received: '已接收', queued: '已排队', mockSent: '模拟已发送', delivered: '已送达',
}
const href = (scope: string, id?: string) => id ? `#${scope}/view/${encodeURIComponent(id)}` : undefined
function Link({ host, scope, id, children }: { host: HostBridge; scope: string; id?: string; children: ReactNode }) {
  if (id && !host.can(scope, 'read')) return <>—</>
  return id && host.can(scope, 'read') ? <a href={href(scope,id)} className="font-medium underline-offset-4 hover:underline">{children}</a> : <>{children}</>
}
function Status({ host, value }: { host: HostBridge; value?: string }) {
  if (!value) return <>—</>
  const variant = ['failed','high'].includes(value) ? 'destructive' : ['waitingApproval','generated','medium','human','unlinked','mockSent'].includes(value) ? 'secondary' : 'outline'
  return <Badge variant={variant}>{host.translate(statusNames[value] || value)}</Badge>
}
const readable = (value: unknown) => value == null || value === '' ? '—' : String(value)
const since = (value?: string) => {
  if (!value) return null
  const timestamp = Date.parse(value.replace(' ','T') + (/[zZ]|[+-]\d\d:\d\d$/.test(value) ? '' : 'Z'))
  return Number.isFinite(timestamp) ? Math.max(0,Math.floor((Date.now()-timestamp)/60000)) : null
}
async function loadSnapshot(host: HostBridge, id: string): Promise<Snapshot> {
  const where = [{ type: 'equals', attribute: 'conversationId', value: id }]
  const conversation = await host.api.get<Row>(`ExternalConversation/${encodeURIComponent(id)}`)
  const [messageResult, draftResult, conversationResult, taskResult, identity, handoffResult] = await Promise.all([
    host.can('ExternalMessage','read') ? host.api.get<{list:Row[];total?:number}>('ExternalMessage', { where, orderBy:'sourceSequence',order:'asc',maxSize:200 }) : Promise.resolve({list:[],total:0}),
    host.can('AIReplyDraft','read') ? host.api.get<{list:Row[]}>('AIReplyDraft', { where,orderBy:'createdAt',order:'desc',maxSize:20 }) : Promise.resolve({list:[]}),
    host.api.get<{list:Row[]}>('ExternalConversation', {orderBy:'lastMessageAt',order:'desc',maxSize:50}),
    host.can('OutboundTask','read') ? host.api.get<{list:Row[]}>('OutboundTask', {where,orderBy:'createdAt',order:'desc',maxSize:20}) : Promise.resolve({list:[]}),
    conversation.identityId && host.can('ExternalIdentity','read') ? host.api.get<Row>(`ExternalIdentity/${encodeURIComponent(conversation.identityId)}`).catch(() => null) : Promise.resolve(null),
    host.can('Task','read') ? host.api.get<{tasks:Row[]}>(`Fusanhe/conversation/${encodeURIComponent(id)}/handoff-tasks`).catch(() => ({tasks:[]})) : Promise.resolve({tasks:[]}),
  ])
  const conversations = conversationResult.list || []
  const leadIds = [...new Set(conversations.map((row) => row.leadId).filter(Boolean))]
  if (leadIds.length && host.can('Lead','read')) {
    try {
      const result = await host.api.get<{list:Row[]}>('Lead',{where:[{type:'in',attribute:'id',value:leadIds}],select:'id,accountName',maxSize:50})
      const byId = new Map(result.list.map((row) => [row.id,row]))
      conversations.forEach((row) => { row.accountName ||= byId.get(row.leadId)?.accountName })
    } catch { /* Optional lead enrichment. */ }
  }
  return { conversation, messages:messageResult.list || [], messageTotal:messageResult.total ?? messageResult.list?.length ?? 0,
    drafts:draftResult.list || [], conversations, tasks:taskResult.list || [], identity, handoffTasks:handoffResult.tasks || [] }
}
function Detail({ label, children }: { label: string; children: ReactNode }) {
  return <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] gap-2 py-1 text-sm"><dt className="text-muted-foreground">{label}</dt><dd className="min-w-0 break-words">{children}</dd></div>
}
function Timeline({ host, messages, tasks, total }: { host:HostBridge; messages:Row[]; tasks:Row[]; total:number }) {
  const t = (label:string) => host.translate(label)
  if (!host.can('ExternalMessage','read')) return <Empty><EmptyHeader><EmptyTitle>{t('没有消息读取权限')}</EmptyTitle></EmptyHeader></Empty>
  if (!messages.length) return <Empty><EmptyHeader><EmptyTitle>{t('暂无消息')}</EmptyTitle><EmptyDescription>{t('接收到询盘后，原文、译文和发送状态将在这里显示。')}</EmptyDescription></EmptyHeader></Empty>
  return <><ol className="flex min-w-0 flex-col gap-3" aria-label={t('消息时间线')}>{messages.map((message) => {
    const attachments = Array.isArray(message.attachmentMetadata) ? message.attachmentMetadata : message.attachmentMetadata?.files || []
    const task = tasks.find((item) => item.platformMessageId && item.platformMessageId === message.externalId)
    return <li key={message.id} className={message.direction === 'outbound' ? 'self-end sm:max-w-[88%]' : 'self-start sm:max-w-[88%]'}><article className="min-w-0 rounded-lg border bg-card p-4 text-card-foreground shadow-sm">
      <header className="mb-2 flex flex-wrap items-baseline gap-2 text-sm"><strong>{t(statusNames[message.direction] || message.direction)} · {readable(message.senderName)}</strong><time className="text-muted-foreground" dateTime={message.sentAt}>{readable(message.sentAt)}</time></header>
      <div className="whitespace-pre-wrap break-words" aria-label={t('原文')}>{readable(message.body)}</div>
      {message.translatedBody && <details className="mt-3" open><summary className="cursor-pointer text-sm font-medium">{t('译文')}</summary><div className="mt-2 whitespace-pre-wrap break-words text-muted-foreground">{message.translatedBody}</div></details>}
      {attachments.length > 0 && <section className="mt-3 text-sm" aria-label={t('附件')}><h3 className="font-medium">{t('附件')}</h3><ul className="list-inside list-disc">{attachments.map((a:Row,index:number) => <li key={`${a.id || a.name || index}`}>{readable(a.name || a.fileName || t('附件'))}</li>)}</ul></section>}
      <footer className="mt-3 flex flex-wrap items-center gap-2"><Status host={host} value={message.deliveryStatus} />{message.direction === 'outbound' && message.deliveryStatus === 'mockSent' && <span className="text-xs text-muted-foreground">{t('模拟回执：演示环境回写结果，不代表真实客户已收到。')}</span>}</footer>
      {task?.errorMessage && <Alert variant="destructive" className="mt-3"><AlertTitle>{t('发送失败')}</AlertTitle><AlertDescription>{task.errorMessage}</AlertDescription></Alert>}
    </article></li>
  })}</ol>{total > 200 && <p className="mt-4 text-sm"><a href="#ExternalMessage" className="underline-offset-4 hover:underline">{t('超过 200 条，打开外部消息查看完整历史')}</a></p>}</>
}
function ConversationList({ host, rows, currentId }: { host:HostBridge; rows:Row[]; currentId:string }) {
  const t = (label:string) => host.translate(label)
  if (!rows.length) return <Empty><EmptyHeader><EmptyTitle>{t('暂无其他询盘')}</EmptyTitle></EmptyHeader></Empty>
  return <nav className="flex min-w-0 flex-col gap-2" aria-label={t('最近会话')}>{rows.map((row) => <a key={row.id} href={href('ExternalConversation',row.id)} aria-current={row.id === currentId ? 'page' : undefined} className="flex min-h-11 min-w-0 flex-col gap-1 rounded-lg border p-3 text-sm hover:bg-accent focus-visible:ring-2 focus-visible:ring-ring aria-[current=page]:bg-muted">
    <strong className="truncate">{readable(row.contactName || row.leadName || row.name)}</strong><span className="truncate text-muted-foreground">{readable(row.accountName)} · {readable(row.channelName)} · {readable(row.country)}</span>
    <span className="truncate" title={readable(row.lastMessagePreview)}>{readable(row.lastMessagePreview)}</span><span className="text-xs text-muted-foreground">{t(statusNames[row.status] || row.status || '未知')} · {t('未读')} {row.unreadCount || 0} · {['sent','replied','closed'].includes(row.status) ? t('已回复') : `${since(row.lastInboundAt) ?? '—'} ${t('分钟')}`}</span>
  </a>)}</nav>
}
export default function ConversationScreen({host,data}:ScreenProps<Data>) {
  const id = data?.conversationId
  const t = (label:string) => host.translate(label)
  const [snapshot,setSnapshot] = useState<Snapshot | null>(null)
  const [loading,setLoading] = useState(true)
  const [error,setError] = useState(false)
  const [busy,setBusy] = useState(false)
  const busyRef = useRef(false)
  const generation = useRef(0)
  const [pane,setPane] = useState('messages')
  const [outbound,setOutbound] = useState<boolean | null>(null)
  const [draftText,setDraftText] = useState('')
  const [approveOpen,setApproveOpen] = useState(false)
  const [reviewed,setReviewed] = useState(false)
  const [manualOpen,setManualOpen] = useState(false)
  const [manualText,setManualText] = useState('')
  const [handoffOpen,setHandoffOpen] = useState(false)
  const [handoffSummary,setHandoffSummary] = useState('')
  const [handoffUser,setHandoffUser] = useState('')
  const [handoffDate,setHandoffDate] = useState(new Date(Date.now()+3*86400000).toISOString().slice(0,10))
  const [users,setUsers] = useState<Row[]>([])
  const [candidates,setCandidates] = useState<Candidate[] | null>(null)
  const [candidateError,setCandidateError] = useState(false)
  const [selectedCandidate,setSelectedCandidate] = useState<Candidate | null>(null)
  const [createLeadOpen,setCreateLeadOpen] = useState(false)
  const [controlOpen,setControlOpen] = useState(false)
  const refresh = useCallback(async () => {
    if (!id || !host.can('ExternalConversation','read')) return
    const request = ++generation.current
    setLoading(true);setError(false)
    try {
      const next = await loadSnapshot(host,id)
      if (generation.current === request) { setSnapshot(next); setDraftText(next.drafts[0]?.draftText || '') }
    } catch { if (generation.current === request) setError(true) }
    finally { if (generation.current === request) setLoading(false) }
  },[host,id])
  useEffect(() => { void refresh(); return () => { generation.current += 1 } },[refresh])
  useEffect(() => { let active = true; void host.getOutboundState().then((s) => { if (active) setOutbound(s.paused) }).catch(() => { if (active) setOutbound(null) }); return () => { active = false } },[host,snapshot])
  const act = async (run:() => Promise<unknown>, success:string) => {
    if (busyRef.current) return
    busyRef.current = true;setBusy(true)
    let completed = false
    try { await run();completed = true;host.notify(t(success),'success');await refresh() }
    catch { host.notify(t(completed ? '操作已完成，请刷新页面查看最新状态。' : '操作未完成，请检查权限和记录状态后重试。'),'error') }
    finally { busyRef.current = false;setBusy(false) }
  }
  if (!id || !host.can('ExternalConversation','read')) return <Empty><EmptyHeader><EmptyTitle>{t('没有读取权限')}</EmptyTitle></EmptyHeader></Empty>
  if (error) return <Alert variant="destructive"><AlertTitle>{t('询盘工作台加载失败')}</AlertTitle><AlertDescription>{t('请确认消息读取权限后刷新。原生记录仍可在下方查看。')} <Button variant="outline" onClick={() => void refresh()}>{t('重试')}</Button></AlertDescription></Alert>
  if (!snapshot) return <div role="status" aria-label={t('正在加载询盘工作台…')} className="flex flex-col gap-3"><Skeleton className="h-12" /><Skeleton className="h-48" /><Skeleton className="h-48" /></div>
  const c = snapshot.conversation
  const draft: Row | undefined = snapshot.drafts[0]
  const editable = canEditDraft(host.can('AIReplyDraft','edit'),draft as Draft)
  const approvable = canApproveDraft(host.can('AIReplyDraft','edit'),host.can('OutboundTask','create'),draft as Draft)
  const isHuman = c.controlMode === 'human'
  const identity = snapshot.identity
  const canIdentify = !!identity && identity.linkStatus !== 'confirmed' && host.can('ExternalIdentity','edit')
  const canHandoff = host.can('Task','create') && host.can('ExternalConversation','read')
  const customerScope = c.contactId ? 'Contact' : c.leadId ? 'Lead' : 'Account'
  const customerId = c.contactId || c.leadId || c.accountId
  const findCandidates = async () => {
    if (!canIdentify || busy || !identity) return
    setCandidates(null);setCandidateError(false)
    try { const result = await host.api.get<{candidates:Candidate[]}>(`Fusanhe/identity/${encodeURIComponent(identity.id)}/candidates`,{conversationId:id});setCandidates(result.candidates || []) }
    catch { setCandidateError(true) }
  }
  const openHandoff = async () => {
    if (!canHandoff || busy) return
    setHandoffOpen(true)
    setHandoffUser(c.assignedUserId || '')
    if (host.can('User','read')) {
      try { const result = await host.api.get<{list:Row[]}>('User',{maxSize:100,orderBy:'name'});setUsers(result.list || []) }
      catch { setUsers([]) }
    }
  }
  const citations = Array.isArray(draft?.citedKnowledge) ? draft.citedKnowledge : []
  return <section className="flex min-w-0 flex-col gap-4" aria-label={t('询盘工作台')}>
    <header className="flex flex-wrap items-start justify-between gap-3"><div><h2 className="text-xl font-semibold tracking-tight">{t('询盘工作台')}</h2><p className="text-sm text-muted-foreground">{readable(c.name)} · {readable(c.channelName)}</p></div><Button variant="outline" className="min-h-11" disabled={loading || busy} onClick={() => void refresh()}>{t('刷新')}</Button></header>
    <Tabs value={pane} onValueChange={setPane} className="xl:hidden"><TabsList aria-label={t('会话分区')}><TabsTrigger value="customers">{t('会话')}</TabsTrigger><TabsTrigger value="messages">{t('消息')}</TabsTrigger><TabsTrigger value="review">{t('资料与审核')}</TabsTrigger></TabsList></Tabs>
    <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(190px,0.9fr)_minmax(0,2fr)_minmax(280px,1.2fr)]">
      <aside className={`min-w-0 rounded-lg border p-4 ${pane === 'customers' ? '' : 'hidden xl:block'}`} aria-label={t('最近会话')}><div className="mb-3 flex items-center justify-between gap-2"><h3 className="font-semibold">{t('最近会话')}</h3><a href="#ExternalConversation" className="text-sm underline-offset-4 hover:underline">{t('全部')}</a></div><ConversationList host={host} rows={snapshot.conversations} currentId={id} /></aside>
      <main className={`min-w-0 rounded-lg border p-4 ${pane === 'messages' ? '' : 'hidden xl:block'}`}><h3 className="mb-3 font-semibold">{t('消息时间线')} <span className="text-sm font-normal text-muted-foreground">{snapshot.messageTotal} {t('条')}</span></h3><Timeline host={host} messages={snapshot.messages} tasks={snapshot.tasks} total={snapshot.messageTotal} />
        {snapshot.tasks.filter((task) => task.status === 'failed').map((task) => <Alert key={task.id} variant="destructive" className="mt-3"><AlertTitle>{t('发送失败')}</AlertTitle><AlertDescription>{readable(task.errorMessage)} <Link host={host} scope="OutboundTask" id={task.id}>{t('查看任务')}</Link> {task.executionMode === 'mock' && <Status host={host} value="mockSent" />}</AlertDescription></Alert>)}
      </main>
      <aside className={`flex min-w-0 flex-col gap-5 rounded-lg border p-4 ${pane === 'review' ? '' : 'hidden xl:flex'}`} aria-label={t('资料与审核')}>
        <section><h3 className="mb-2 font-semibold">{t('接待控制')}</h3><div className="flex flex-wrap gap-2"><Status host={host} value={c.status} /><Status host={host} value={c.controlMode || 'aiAssist'} /></div>{host.can('ExternalConversation','edit') && <><Button variant="outline" className="mt-3 min-h-11" disabled={busy} onClick={() => setControlOpen(true)}>{isHuman ? t('恢复 AI 辅助') : t('人工接管')}</Button><p className="mt-2 text-sm text-muted-foreground">{t(isHuman ? '人工接管期间，未发送的自动任务不会被执行。' : 'AI 辅助模式：草稿需人工批准后才会创建发送任务。')}</p></>}</section>
        <section className="border-t pt-4"><h3 className="mb-2 font-semibold">{t('身份确认')}</h3>{!c.identityId ? <Empty className="min-h-28"><EmptyHeader><EmptyTitle>{t('尚未映射平台身份')}</EmptyTitle><EmptyDescription>{t('历史数据的新消息进入后将自动建立映射。')}</EmptyDescription></EmptyHeader></Empty> : <><dl><Detail label={t('状态')}><Status host={host} value={identity?.linkStatus || 'unlinked'} /></Detail><Detail label={t('关联客户')}>{identity?.linkStatus === 'confirmed' ? <Link host={host} scope={identity.accountId ? 'Account' : identity.contactId ? 'Contact' : 'Lead'} id={identity.accountId || identity.contactId || identity.leadId}>{readable(identity.accountName || identity.contactName || identity.leadName || t('已关联客户'))}</Link> : t('未关联')}</Detail><Detail label={t('平台身份')}>{readable(identity?.channelType)} · {readable(identity?.externalUserId || t('匿名访客（仅本会话）'))}</Detail>{identity?.emailAddress && <Detail label={t('邮箱')}>{identity.emailAddress}</Detail>}{identity?.phoneNumber && <Detail label={t('电话')}>{identity.phoneNumber}</Detail>}</dl>{canIdentify ? <><div className="mt-3 flex flex-wrap gap-2"><Button variant="outline" className="min-h-11" disabled={busy} onClick={() => void findCandidates()}>{t('查找匹配客户')}</Button><Button variant="outline" className="min-h-11" disabled={busy} onClick={() => setCreateLeadOpen(true)}>{t('建立线索建档')}</Button></div><p className="mt-2 text-sm text-muted-foreground">{t('公司名或姓名等弱匹配不会自动关联，需在此人工确认。')}</p>{candidateError && <Alert variant="destructive"><AlertDescription>{t('候选查询失败，请检查权限后重试。')}</AlertDescription></Alert>}{candidates && (candidates.length ? <ul className="mt-3 flex flex-col gap-2">{candidates.map((candidate) => <li key={`${candidate.type}:${candidate.id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-2"><span><Link host={host} scope={candidate.type} id={candidate.id}>{candidate.name}</Link><small className="ml-2 text-muted-foreground">{candidate.emailAddress || candidate.phoneNumber}</small></span><Button size="sm" variant="outline" className="min-h-11" onClick={() => setSelectedCandidate(candidate)}>{t('确认关联')}</Button></li>)}</ul> : <p className="mt-2 text-sm text-muted-foreground">{t('未找到邮箱或电话精确匹配的客户。请先在 CRM 建档，或使用线索建档。')}</p>)}</> : identity?.linkStatus !== 'confirmed' && <p className="mt-2 text-sm text-muted-foreground">{t('没有身份确认权限，请联系有权限的同事处理。')}</p>}</>}</section>
        <section className="border-t pt-4"><h3 className="mb-2 font-semibold">{t('客户信息')}</h3><dl><Detail label={t('客户')}><Link host={host} scope={customerScope} id={customerId}>{readable(c.contactName || c.leadName || c.accountName || t('尚未匹配'))}</Link></Detail><Detail label={t('公司')}><Link host={host} scope="Account" id={c.accountId}>{readable(c.accountName)}</Link></Detail><Detail label={t('渠道 / 国家')}>{readable(c.channelName)} / {readable(c.country)}</Detail><Detail label={t('接待人')}>{readable(c.assignedUserName || t('未分配'))}</Detail><Detail label={t('询盘产品')}>{readable(c.product)}</Detail></dl></section>
        <section className="border-t pt-4"><h3 className="mb-2 font-semibold">{t('转销售跟进')}</h3>{canHandoff ? <><Button variant="outline" className="min-h-11" disabled={busy} onClick={() => void openHandoff()}>{t('创建跟进任务')}</Button><ul className="mt-3 flex flex-col gap-2 text-sm">{snapshot.handoffTasks.length ? snapshot.handoffTasks.map((task) => <li key={task.id}><Link host={host} scope="Task" id={task.id}>{readable(task.name)}</Link> · {t(statusNames[task.status] || task.status || '未知')} · {readable(task.assignedUserName)} · {readable(task.dateEnd)}</li>) : <li className="text-muted-foreground">{t('尚未创建跟进任务。')}</li>}</ul></> : <p className="text-sm text-muted-foreground">{t('没有创建跟进任务的权限。')}</p>}</section>
        <section className="border-t pt-4"><h3 className="mb-2 font-semibold">{t('AI 回复与审核')}</h3><Alert variant={outbound === true ? 'default' : 'destructive'} role="status"><AlertTitle>{outbound === true ? t('全局停发已开启') : outbound === false ? t('全局停发未开启') : t('外发开关状态未知')}</AlertTitle><AlertDescription>{t(outboundDescription(outbound))}</AlertDescription></Alert>
          {host.can('AIReplyDraft','create') && <div className="mt-3 flex flex-wrap gap-2"><Button variant="outline" className="min-h-11" disabled={busy} onClick={() => void act(() => host.api.post(`Fusanhe/conversation/${encodeURIComponent(id)}/generate-draft`,{}),'AI 草稿已生成，请人工审核')}>{t('生成 AI 草稿')}</Button><Button variant="outline" className="min-h-11" disabled={busy} onClick={() => setManualOpen(true)}>{t('人工草稿')}</Button></div>}
          {!draft ? <Empty className="min-h-28"><EmptyHeader><EmptyTitle>{t('尚无 AI 草稿')}</EmptyTitle><EmptyDescription>{t('请先阅读客户消息，再生成建议回复或撰写人工草稿。')}</EmptyDescription></EmptyHeader></Empty> : <div className="mt-4 flex flex-col gap-3"><div className="flex flex-wrap items-center gap-2"><Status host={host} value={draft.status} /><Status host={host} value={draft.riskLevel} /><Link host={host} scope="AIReplyDraft" id={draft.id}>{t('草稿记录')}</Link>{draft.modelProvider === 'manual' && <Status host={host} value="human" />}</div><div><h4 className="font-medium">{t('AI 中文摘要')}</h4><p className="whitespace-pre-wrap break-words text-sm">{readable(draft.summaryZh)}</p></div>{draft.riskLevel === 'high' && <Alert variant="destructive"><AlertDescription>{t('包含价格、MOQ、交期、认证、付款、折扣或承诺信息，需要人工确认。')}</AlertDescription></Alert>}<div><h4 className="font-medium">{t('缺失信息')}</h4><p className="text-sm">{Array.isArray(draft.missingInformation) && draft.missingInformation.length ? draft.missingInformation.map((item:Row|string) => typeof item === 'string' ? item : item.name || item.label || t('待核实信息')).join('、') : t('无')}</p></div><details><summary className="cursor-pointer font-medium">{t('引用知识')}</summary>{citations.length ? <ul className="mt-2 flex flex-col gap-1 text-sm">{citations.map((item:Row|string,index:number) => { const certificate = typeof item === 'string' && item.startsWith('cert:');const scope = certificate ? 'FusanheCertificate' : 'KnowledgeDocument';const itemId = typeof item === 'string' ? certificate ? item.slice(5) : item : item.id || item.documentId;return <li key={`${itemId || index}`}><Link host={host} scope={scope} id={itemId}>{typeof item === 'string' ? t(certificate ? '查看证书' : '查看引用资料') : item.name || item.title || t('引用资料')}</Link></li> })}</ul> : <p className="mt-2 text-sm text-muted-foreground">{t('无引用资料，请人工核实')}</p>}</details><Field><FieldLabel htmlFor="conversation-draft">{t('英文回复草稿')} · {t(({en:'英语',zh:'中文',zh_CN:'简体中文'} as Record<string,string>)[draft.suggestedLanguage] || draft.suggestedLanguage || '语言未指定')}</FieldLabel><textarea id="conversation-draft" rows={9} className="w-full rounded-md border border-input bg-background p-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={draftText} onChange={(e) => setDraftText(e.target.value)} readOnly={!editable} /></Field><div className="flex flex-wrap gap-2"><Button variant="outline" className="min-h-11" disabled={!editable || busy || !draftText.trim()} onClick={() => void act(() => host.api.patch(`AIReplyDraft/${encodeURIComponent(draft.id)}`,{draftText,status:'edited'}),'修改已保存')}>{t('保存修改')}</Button><Button variant="ghost" className="min-h-11" disabled={!editable || busy} onClick={() => void act(() => host.api.patch(`AIReplyDraft/${encodeURIComponent(draft.id)}`,{status:'rejected'}),'草稿已拒绝')}>{t('拒绝草稿')}</Button></div><Button className="min-h-11" disabled={!approvable || busy || !draftText.trim()} onClick={() => { setReviewed(false);setApproveOpen(true) }}>{t('批准并创建发送任务')}</Button></div>}
        </section>
      </aside>
    </div>
    <AlertDialog open={approveOpen} onOpenChange={setApproveOpen}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{t('确认批准并创建任务')}</AlertDialogTitle><AlertDialogDescription>{t('请确认已核对回复内容、引用依据和商业承诺。此操作将批准草稿并创建发送任务。')}</AlertDialogDescription></AlertDialogHeader><Field orientation="horizontal"><input id="approve-reviewed" type="checkbox" checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} /><FieldLabel htmlFor="approve-reviewed">{t('我已完成人工审核')}</FieldLabel></Field><AlertDialogFooter><AlertDialogCancel>{t('取消')}</AlertDialogCancel><AlertDialogAction disabled={!reviewed || busy || !approvable || !draftText.trim()} onClick={(e) => { e.preventDefault(); if (!draft || !reviewed || busyRef.current || !approvable) return;setApproveOpen(false);void act(() => host.api.post(`Fusanhe/draft/${encodeURIComponent(draft.id)}/approve`,{draftText}), '已创建发送任务') }}>{t('确认批准并创建任务')}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    <AlertDialog open={controlOpen} onOpenChange={setControlOpen}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{t(isHuman ? '恢复 AI 辅助' : '人工接管')}</AlertDialogTitle><AlertDialogDescription>{t(isHuman ? '恢复后，已批准的任务可按全局外发开关继续执行。' : '接管后，未发送的自动任务会暂停执行。')}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>{t('取消')}</AlertDialogCancel><AlertDialogAction disabled={busy} onClick={(e) => { e.preventDefault();setControlOpen(false);void act(() => host.api.post(`Fusanhe/conversation/${encodeURIComponent(id)}/control`,{mode:isHuman ? 'aiAssist' : 'human'}), isHuman ? '已恢复 AI 辅助' : '已人工接管，自动任务已暂停执行') }}>{t('确认')}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    <AlertDialog open={!!selectedCandidate} onOpenChange={(open) => { if (!open) setSelectedCandidate(null) }}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{t('确认关联客户')}</AlertDialogTitle><AlertDialogDescription>{t('请核对平台身份与客户邮箱或电话。公司名、姓名等弱匹配不能作为自动关联依据。')} {selectedCandidate?.name}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>{t('取消')}</AlertDialogCancel><AlertDialogAction disabled={busy || !canIdentify} onClick={(e) => { e.preventDefault();const selected = selectedCandidate;setSelectedCandidate(null);if (selected && identity && canIdentify) void act(() => host.api.post(`Fusanhe/identity/${encodeURIComponent(identity.id)}/link`,{conversationId:id,targetType:selected.type,targetId:selected.id}), '已关联客户') }}>{t('确认关联')}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    <AlertDialog open={createLeadOpen} onOpenChange={setCreateLeadOpen}><AlertDialogContent><AlertDialogHeader><AlertDialogTitle>{t('建立线索建档')}</AlertDialogTitle><AlertDialogDescription>{t('将建立新线索并关联本会话，请先核对身份信息。')}</AlertDialogDescription></AlertDialogHeader><AlertDialogFooter><AlertDialogCancel>{t('取消')}</AlertDialogCancel><AlertDialogAction disabled={busy || !canIdentify} onClick={(e) => { e.preventDefault();setCreateLeadOpen(false);if (identity && canIdentify) void act(() => host.api.post(`Fusanhe/identity/${encodeURIComponent(identity.id)}/create-customer`,{conversationId:id,targetType:'Lead'}), '已建立线索并关联本会话') }}>{t('确认建档')}</AlertDialogAction></AlertDialogFooter></AlertDialogContent></AlertDialog>
    <Dialog open={manualOpen} onOpenChange={setManualOpen}><DialogContent><DialogHeader><DialogTitle>{t('人工草稿')}</DialogTitle><DialogDescription>{t('手动撰写回复，保存后走同一审核与发送任务流程。')}</DialogDescription></DialogHeader><FieldGroup><Field><FieldLabel htmlFor="manual-draft">{t('人工草稿内容')}</FieldLabel><textarea id="manual-draft" rows={6} className="w-full rounded-md border border-input bg-background p-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={manualText} onChange={(e) => setManualText(e.target.value)} /></Field></FieldGroup><DialogFooter><Button variant="outline" onClick={() => setManualOpen(false)}>{t('取消')}</Button><Button disabled={busy || !manualText.trim() || !host.can('AIReplyDraft','create')} onClick={() => { setManualOpen(false);void act(() => host.api.post(`Fusanhe/conversation/${encodeURIComponent(id)}/manual-draft`,{draftText:manualText}), '人工草稿已创建，请审核') }}>{t('创建人工草稿')}</Button></DialogFooter></DialogContent></Dialog>
    <Dialog open={handoffOpen} onOpenChange={setHandoffOpen}><DialogContent><DialogHeader><DialogTitle>{t('转销售跟进')}</DialogTitle><DialogDescription>{t('创建跟进任务，成功后可在任务中回到本会话。')}</DialogDescription></DialogHeader><FieldGroup><Field><FieldLabel htmlFor="handoff-summary">{t('需求摘要（必填）')}</FieldLabel><textarea id="handoff-summary" rows={3} className="w-full rounded-md border border-input bg-background p-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" value={handoffSummary} onChange={(e) => setHandoffSummary(e.target.value)} /></Field><Field><FieldLabel htmlFor="handoff-user">{t('负责人')}</FieldLabel><Select value={handoffUser || '_none'} onValueChange={(v) => setHandoffUser(v === '_none' ? '' : v)}><SelectTrigger id="handoff-user" className="min-h-11 w-full"><SelectValue /></SelectTrigger><SelectContent><SelectGroup><SelectItem value="_none">{t('未分配')}</SelectItem>{(users.length ? users : c.assignedUserId ? [{id:c.assignedUserId,name:c.assignedUserName || t('当前负责人')}] : []).map((user) => <SelectItem key={user.id} value={user.id}>{user.name}</SelectItem>)}</SelectGroup></SelectContent></Select></Field><Field><FieldLabel htmlFor="handoff-date">{t('截止日期')}</FieldLabel><Input id="handoff-date" type="date" className="min-h-11" value={handoffDate} onChange={(e) => setHandoffDate(e.target.value)} /></Field></FieldGroup><DialogFooter><Button variant="outline" onClick={() => setHandoffOpen(false)}>{t('取消')}</Button><Button disabled={busy || !canHandoff || !handoffSummary.trim()} onClick={() => { setHandoffOpen(false);void act(() => host.api.post(`Fusanhe/conversation/${encodeURIComponent(id)}/handoff`,{summary:handoffSummary,assignedUserId:handoffUser || undefined,dateEnd:handoffDate || undefined}), '跟进任务已创建') }}>{t('创建跟进任务')}</Button></DialogFooter></DialogContent></Dialog>
  </section>
}
