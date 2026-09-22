# -*- coding: utf-8 -*-
from pathlib import Path


def test_task_payload_includes_inquiry_and_buyer():
    service_file = Path(__file__).resolve().parent.parent / "custom" / "Espo" / "Custom" / "Tools" / "Fusanhe" / "WorkflowService.php"
    content = service_file.read_text(encoding="utf-8")
    assert "function taskPayload" in content
    assert "'inquiryId'" in content, "taskPayload must contain 'inquiryId' for Alibaba Outbound Worker"
    assert "'buyerName'" in content, "taskPayload must contain 'buyerName' for Alibaba Outbound Worker"
    assert "'channelType'" in content, "taskPayload must contain 'channelType'"
