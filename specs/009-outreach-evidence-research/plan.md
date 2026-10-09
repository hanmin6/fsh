# Implementation Plan: CRM 触达证据与 AI 背调

**Branch**: `009-outreach-evidence-research` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

## Summary

在 CRM 内新增可审计的 `OutreachEvidence` 和 `ProspectResearch`。先由 CRM 接收受控截图、客户快照和发送事实，再调用现有联网研究网关生成带来源的背调报告；暂不接 Muse、不创建 `OutboundTask`、不发送外部消息。截图使用现有私有 `MediaStorage`，实体权限和 `ServiceKernel` 负责访问与审计。

## Technical Context

**Language/Version**: PHP 8.3 / TypeScript React
**Primary Dependencies**: EspoCRM 10.0.8, existing `TextGateway`, `MediaStorage`, `ServiceKernel`
**Storage**: MariaDB entities plus private `data/fusanhe-media` files
**Testing**: Python contract tests, PHP metadata/lint checks, injected TextGateway tests
**Target Platform**: EspoCRM Docker server and CRM Web workbench
**Project Type**: CRM web application with PHP service/API and React workbench
**Performance Goals**: Evidence writes remain bounded and idempotent; research is an explicit long-running action and is never triggered by a GET.
**Constraints**: private screenshots, max 4 MiB per image, no public file URLs, no external send, no sensitive-attribute inference
**Scale/Scope**: one CRM instance, up to 50 evidence records per list view, one latest research snapshot per prospect

## Constitution Check

*GATE: pass — this is an additive, auditable CRM capability; no external send, credential handling or destructive migration is introduced.*

## Project Structure

```text
specs/009-outreach-evidence-research/
├── spec.md
├── plan.md
├── data-model.md
├── quickstart.md
└── tasks.md

custom/Espo/Custom/Resources/metadata/entityDefs/
├── OutreachEvidence.json
└── ProspectResearch.json
custom/Espo/Custom/Tools/Fusanhe/
├── OutreachEvidencePolicy.php
├── OutreachEvidenceService.php
└── Api/
    ├── PostOutreachEvidence.php
    ├── GetOutreachEvidence.php
    ├── GetOutreachScreenshot.php
    └── PostOutreachResearch.php
client/custom/ui/src/
└── outreach-evidence.tsx

tests/test_outreach_evidence_contract.py
```

**Structure Decision**: 复用现有 Fusanhe PHP service/API、Espo metadata 和 React workbench，不新建独立服务；截图由私有 MediaStorage 存储，研究复用 TextGateway 的搜索和证据校验。

## Implementation Order

1. Metadata、policy、routes 和 service contract。
2. Evidence create/read/screenshot API，确认幂等和 no-send 边界。
3. Research action、source filtering、failure/retry state。
4. CRM 客户详情展示和截图预览。
5. Offline contracts、PHP lint、compose/rebuild verification。
