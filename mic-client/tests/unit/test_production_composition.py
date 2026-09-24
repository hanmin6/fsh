from __future__ import annotations

from pathlib import Path

from mic_gateway.adapters.made_in_china import MadeInChinaAdapter
from mic_gateway.browser.runtime import BrowserRuntime
from mic_gateway.config import Settings
from mic_gateway.main import create_app
from mic_gateway.messaging.outbox import OutboxWorker
from mic_gateway.monitoring.status import StatusService
from mic_gateway.runtime.scheduler import GatewayScheduler
from mic_gateway.sync.engine import SyncEngine


def test_production_app_composes_browser_sync_and_outbox(tmp_path: Path) -> None:
    app = create_app(Settings(app_data_dir=tmp_path), production=True)

    assert isinstance(app.state.browser_runtime, BrowserRuntime)
    assert isinstance(app.state.adapter, MadeInChinaAdapter)
    assert isinstance(app.state.sync_engine, SyncEngine)
    assert isinstance(app.state.outbox_worker, OutboxWorker)
    assert isinstance(app.state.status_service, StatusService)
    assert isinstance(app.state.scheduler, GatewayScheduler)
