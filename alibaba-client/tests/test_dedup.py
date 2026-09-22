import os
import json
from alibaba_messenger.dedup import Deduplicator

def test_deduplication_lifecycle(tmp_path):
    record_file = str(tmp_path / "sent_records.json")
    dedup = Deduplicator(storage_file=record_file)
    
    buyer = "Test Buyer Inc"
    msg = "Happy New Year!"
    
    # 未发过时不重复
    assert dedup.is_duplicate(buyer, msg) is False
    
    # 记录发送
    dedup.record_sent(buyer, msg)
    
    # 再次判断应为重复
    assert dedup.is_duplicate(buyer, msg) is True
    
    # 消息内容改变不判定为重复
    assert dedup.is_duplicate(buyer, "Different Message") is False
    
    # 持久化文件存在且格式正确
    assert os.path.exists(record_file)
    with open(record_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert len(data) == 1
