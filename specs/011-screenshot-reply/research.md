# Research
- Decision: 独立无状态接口。Reason: 旧 generate-draft 绑定已有会话且无视觉输入，直接扩展会扰动旧审核状态。Alternative: 复用旧接口，因独立截图无 conversationId 不采用。
- Decision: 两次调用。Reason: 先让人选择方向再生成；识别后不重复发送图片。Alternative: 一次生成三篇完整回复，违背确认流程。
- Decision: 复用当前 React 工作台、token、Lucide 图标和受权限保护的 HostBridge。Reason: 避免另建前端/认证体系。
- Decision: 预览用显式合成案例，真实模式缺配置报错。Reason: 不能用固定模板伪装识别结果。
- No unresolved technology questions; no research delegation needed.
