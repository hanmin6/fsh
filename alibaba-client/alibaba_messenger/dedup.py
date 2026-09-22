# -*- coding: utf-8 -*-
import os
import json
import hashlib
from datetime import datetime
from typing import Dict
from alibaba_messenger.config import settings

class Deduplicator:
    def __init__(self, storage_file: str = None):
        self.storage_file = storage_file or settings.SENT_RECORDS_FILE
        self._records: Dict[str, str] = {}
        self._load()

    def _generate_key(self, buyer_name: str, message: str, date_str: str = None) -> str:
        date_str = date_str or datetime.now().strftime("%Y-%m-%d")
        normalized_msg = message.strip()
        msg_hash = hashlib.md5(normalized_msg.encode("utf-8")).hexdigest()[:12]
        return f"{buyer_name.strip()}_{date_str}_{msg_hash}"

    def _load(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self._records = json.load(f)
            except Exception:
                self._records = {}
        else:
            self._records = {}

    def _save(self):
        try:
            with open(self.storage_file, "w", encoding="utf-8") as f:
                json.dump(self._records, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[Warn] 保存防重记录文件失败: {e}")

    def is_duplicate(self, buyer_name: str, message: str) -> bool:
        key = self._generate_key(buyer_name, message)
        return key in self._records

    def record_sent(self, buyer_name: str, message: str):
        key = self._generate_key(buyer_name, message)
        self._records[key] = datetime.now().isoformat()
        self._save()

deduplicator = Deduplicator()
