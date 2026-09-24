import { useEffect, useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import type { OutboundState, ScreenProps } from '@/lib/host'

export const screenId = 'context-detail'

type ContextData = {
  type: 'KnowledgeDocument' | 'OutboundTask' | 'AIReplyDraft'
  conversationId?: string
  riskLevel?: string
}

export default function ContextDetail({ host, data }: ScreenProps<ContextData>) {
  const t = host.translate
  const [outbound, setOutbound] = useState<OutboundState | null>(null)
  const type = data?.type
  useEffect(() => {
    if (type === 'KnowledgeDocument') return
    let active = true
    void host.getOutboundState()
      .then(state => { if (active) setOutbound(state) })
      .catch(() => { if (active) setOutbound({ paused: null, status: 'unknown' }) })
    return () => { active = false }
  }, [host, type])

  if (type === 'KnowledgeDocument') {
    return <Alert><AlertTitle>{t('引用资料规则')}</AlertTitle><AlertDescription>{t('AI 只能使用“已审核”且在有效期内的资料。草稿及已过期文档不可作为回复依据。')}</AlertDescription></Alert>
  }
  const notice = outbound?.paused === true
    ? t('系统当前处于全局停发状态：批准只创建发送任务，不会实际发送。')
    : outbound?.paused === false
      ? t('全局停发已关闭：批准的任务可被执行端领取并实际发送。')
      : t('外发开关状态未知（无法读取状态接口），请勿假定任务不会实际发送。')

  return (
    <div className="flex flex-col gap-3">
      <Alert variant={outbound?.paused === null || !outbound ? 'destructive' : 'default'} role="status">
        <AlertTitle>{t('外发状态')}</AlertTitle>
        <AlertDescription>{notice}</AlertDescription>
      </Alert>
      {type !== 'OutboundTask' && (
        <Alert>
          <AlertTitle>{t('草稿审核')}</AlertTitle>
          <AlertDescription>
            <p>{t('请在会话中核对引用依据、编辑、批准或拒绝草稿。')}</p>
            {data?.riskLevel === 'high' && <p className="font-medium">{t('包含价格、MOQ、交期、认证、付款、折扣或承诺信息，需要人工确认。')}</p>}
            {host.can('ExternalConversation', 'read') && data?.conversationId
              ? <Button asChild variant="outline" size="sm"><a href={`#ExternalConversation/view/${encodeURIComponent(data.conversationId)}`}>{t('打开会话审核')}</a></Button>
              : <p>{t('没有读取权限')}</p>}
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}
