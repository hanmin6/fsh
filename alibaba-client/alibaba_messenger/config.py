# -*- coding: utf-8 -*-
import os
from pathlib import Path
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).resolve().parent.parent / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
    else:
        load_dotenv()
except ImportError:
    pass

@dataclass
class Settings:
    BASE_DIR: str = field(default_factory=lambda: os.path.dirname(os.path.abspath(__file__)))
    PROFILE_DIR: str | None = None
    LOGS_DIR: str | None = None
    SCREENSHOTS_DIR: str | None = None
    SENT_RECORDS_FILE: str | None = None
    
    ALIBABA_MSG_URL: str = "https://message.alibaba.com/message/default.htm"
    ALIBABA_LOGIN_FLAG: str = "passport.alibaba.com"
    
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    
    TYPING_DELAY_MIN_MS: int = 20
    TYPING_DELAY_MAX_MS: int = 80
    POST_SEND_COOLDOWN_MIN_SEC: float = 3.0
    POST_SEND_COOLDOWN_MAX_SEC: float = 6.0
    
    SEARCH_TIMEOUT_MS: int = 5000
    PAGE_ACTION_TIMEOUT_MS: int = 10000
    DEFAULT_QUEUE_TIMEOUT_SEC: int = 30

    CRM_API_URL: str = field(default_factory=lambda: os.getenv(
        "CRM_API_URL", "http://localhost:8080/api/v1"
    ).rstrip("/"))
    AGENT_KEY: str = field(default_factory=lambda: os.getenv(
        "FUSANHE_AGENT_KEY", "guangzhou-alibaba-01"
    ))
    AGENT_TOKEN: str = field(default_factory=lambda: os.getenv("FUSANHE_AGENT_TOKEN", ""))
    ACCOUNT_HANDLE: str = field(default_factory=lambda: os.getenv(
        "ALIBABA_ACCOUNT_HANDLE", "default"
    ))
    SYNC_INTERVAL_SECONDS: int = field(default_factory=lambda: int(os.getenv(
        "ALIBABA_SYNC_INTERVAL_SECONDS", "300"
    )))
    SYNC_BATCH_SIZE: int = field(default_factory=lambda: int(os.getenv(
        "ALIBABA_SYNC_BATCH_SIZE", "100"
    )))
    SYNC_DB_PATH: str | None = field(default_factory=lambda: os.getenv(
        "ALIBABA_SYNC_DB_PATH"
    ))
    BACKFILL_MAX_PAGES: int = field(default_factory=lambda: int(os.getenv(
        "BACKFILL_MAX_PAGES", "1000"
    )))

    def __post_init__(self):
        self.BASE_DIR = os.path.abspath(self.BASE_DIR)
        self.PROFILE_DIR = self.PROFILE_DIR or os.path.join(self.BASE_DIR, "profile")
        self.LOGS_DIR = self.LOGS_DIR or os.path.join(self.BASE_DIR, "logs")
        self.SCREENSHOTS_DIR = self.SCREENSHOTS_DIR or os.path.join(self.LOGS_DIR, "screenshots")
        self.SENT_RECORDS_FILE = self.SENT_RECORDS_FILE or os.path.join(self.LOGS_DIR, "sent_records.json")
        if self.SYNC_DB_PATH:
            if not os.path.isabs(self.SYNC_DB_PATH):
                self.SYNC_DB_PATH = os.path.join(self.BASE_DIR, self.SYNC_DB_PATH)
        else:
            self.SYNC_DB_PATH = os.path.join(self.BASE_DIR, "data", "alibaba_sync.db")

    def ensure_dirs(self):
        os.makedirs(self.PROFILE_DIR, exist_ok=True)
        os.makedirs(self.LOGS_DIR, exist_ok=True)
        os.makedirs(self.SCREENSHOTS_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(os.path.abspath(self.SYNC_DB_PATH)), exist_ok=True)

settings = Settings()
settings.ensure_dirs()
