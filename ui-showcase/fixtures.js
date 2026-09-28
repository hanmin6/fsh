// Fictional fixtures for the offline showcase. No customer data or credentials.
window.showcaseFixtures = Object.freeze({
  Account: [
    { id: 'a1', name: 'North Harbor Foods LLC', billingAddressCountry: '美国', emailAddress: 'hello@northharbor.example', assignedUserId: 'u1', assignedUserName: '演示业务员', createdAt: '2026-09-26 08:20:00' },
    { id: 'a2', name: 'Westfield Ingredients Ltd.', billingAddressCountry: '英国', emailAddress: 'contact@westfield.example', assignedUserId: 'u2', assignedUserName: '王业务员', createdAt: '2026-09-25 06:50:00' },
  ],
  Contact: [
    { id: 'c1', name: 'Olivia Chen', accountId: 'a1', accountName: 'North Harbor Foods LLC', emailAddress: 'olivia@northharbor.example', assignedUserName: '演示业务员', createdAt: '2026-09-26 08:25:00' },
    { id: 'c2', name: 'Daniel Reed', accountId: 'a2', accountName: 'Westfield Ingredients Ltd.', assignedUserName: '王业务员', createdAt: '2026-09-25 06:55:00' },
  ],
  Lead: [
    { id: 'l1', name: '冷冻蓝莓采购询盘', accountName: 'North Harbor Foods LLC', status: 'Assigned', createdAt: '2026-09-26 08:30:00' },
    { id: 'l2', name: '冻干草莓样品询问', accountName: 'Westfield Ingredients Ltd.', status: 'In Process', createdAt: '2026-09-25 07:00:00' },
  ],
  Task: [{ id: 't1', name: '确认目的港与规格', status: 'Not Started', assignedUserId: 'u1', dateEnd: '2026-09-30 09:00:00', parentType: 'ExternalConversation', parentId: 'v1' }],
  ExternalConversation: [
    { id: 'v1', name: 'North Harbor Foods · 冷冻蓝莓', externalId: 'DEMO-ALI-001', status: 'pending', controlMode: 'aiAssist', accountId: 'a1', accountName: 'North Harbor Foods LLC', contactId: 'c1', contactName: 'Olivia Chen', channelId: 'ch1', channelName: '阿里国际站', country: '美国', product: 'IQF 冷冻蓝莓', assignedUserId: 'u1', assignedUserName: '演示业务员', lastMessageAt: '2026-09-26 08:31:00', lastInboundAt: '2026-09-26 08:31:00', lastMessagePreview: '请提供冷冻蓝莓规格和交货期', unreadCount: 1, identityId: 'i1', needsManualMatch: true },
    { id: 'v2', name: 'Westfield · 冻干草莓', externalId: 'DEMO-ALI-002', status: 'waitingApproval', controlMode: 'aiAssist', accountId: 'a2', accountName: 'Westfield Ingredients Ltd.', contactId: 'c2', contactName: 'Daniel Reed', channelId: 'ch1', channelName: '阿里国际站', country: '英国', product: '冻干草莓', assignedUserId: 'u2', assignedUserName: '王业务员', lastMessageAt: '2026-09-25 07:02:00', lastInboundAt: '2026-09-25 07:02:00', lastMessagePreview: '希望先寄送样品', unreadCount: 0, needsManualMatch: false },
  ],
  ExternalMessage: [
    { id: 'm1', conversationId: 'v1', sourceSequence: 1, externalId: 'DEMO-M-001', direction: 'inbound', senderName: 'Olivia Chen', body: 'Please share your IQF blueberry specification, MOQ, and lead time.', translatedBody: '请提供冷冻蓝莓规格、起订量和交期。', sentAt: '2026-09-26 08:31:00', deliveryStatus: 'received' },
    { id: 'm2', conversationId: 'v2', sourceSequence: 1, externalId: 'DEMO-M-002', direction: 'inbound', senderName: 'Daniel Reed', body: 'Could you send samples of freeze-dried strawberry?', translatedBody: '可以寄送冻干草莓样品吗？', sentAt: '2026-09-25 07:02:00', deliveryStatus: 'received' },
  ],
  AIReplyDraft: [{ id: 'd1', name: '冻干草莓样品回复', conversationId: 'v2', conversationName: 'Westfield · 冻干草莓', accountId: 'a2', accountName: 'Westfield Ingredients Ltd.', status: 'generated', summaryZh: '客户希望先查看冻干草莓样品。', draftText: 'Thank you for your interest. Please confirm the sample quantity and delivery address.', suggestedLanguage: 'en', riskLevel: 'low', missingInformation: ['样品数量', '收件地址'], channelName: '阿里国际站', product: '冻干草莓', assignedUserName: '王业务员', createdAt: '2026-09-25 07:12:00', citations: [] }],
  ExternalIdentity: [{ id: 'i1', name: '待确认身份', channelType: 'Alibaba', externalUserId: 'DEMO-BUYER-001', displayName: '采购联系人', linkStatus: 'unlinked', lastSeenAt: '2026-09-26 08:31:00' }],
  OutboundTask: [{ id: 'o1', name: '演示发送异常', conversationId: 'v1', conversationName: 'North Harbor Foods · 冷冻蓝莓', accountId: 'a1', accountName: 'North Harbor Foods LLC', status: 'failed', executionMode: 'mock', idempotencyKey: 'demo-task-001', retryCount: 1, errorMessage: '演示执行端离线', channelName: '阿里国际站', createdAt: '2026-09-26 09:00:00' }],
  KnowledgeDocument: [{ id: 'k1', name: 'IQF 冷冻蓝莓规格书', category: '产品资料', product: 'IQF 冷冻蓝莓', sourceType: 'PDF', version: 'v1', approvalStatus: 'approved', effectiveFrom: '2026-01-01', effectiveTo: '2027-01-01', checksum: 'demo-checksum-001', indexedAt: '2026-09-20 08:00:00', modifiedAt: '2026-09-20 08:00:00' }],
  ExternalChannel: [{ id: 'ch1', name: '阿里国际站', type: 'Alibaba', connectionStatus: 'healthy' }],
  AutomationAgent: [{ id: 'ag1', name: '广州执行端 · 演示', status: 'offline', mode: 'mock', capabilities: ['Alibaba'], lastHeartbeatAt: '2026-09-28 02:00:00', lastError: '演示环境未连接' }],
  User: [{ id: 'u1', name: '演示业务员' }, { id: 'u2', name: '王业务员' }],
});
