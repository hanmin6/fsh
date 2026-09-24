export type Draft = { id: string; status?: string; draftText?: string }
export function canEditDraft(canEdit: boolean, draft?: Draft): boolean {
  return !!draft && canEdit && ['generated', 'edited'].includes(draft.status || '')
}
export function canApproveDraft(canEdit: boolean, canCreateTask: boolean, draft?: Draft): boolean {
  return canEditDraft(canEdit, draft) && canCreateTask
}
export function outboundDescription(paused: boolean | null): string {
  return paused === true ? '批准只创建发送任务，不会实际发送。' : paused === false
    ? '批准的任务可由执行端领取并实际发送。' : '无法读取状态接口，请勿假定任务不会实际发送。'
}
