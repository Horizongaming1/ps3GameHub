from __future__ import annotations

import logging
from urllib.parse import quote
from urllib.request import urlopen

from app.models.target import Target

logger = logging.getLogger(__name__)


class WebmanService:
    def __init__(self, timeout_sec: float) -> None:
        self.timeout_sec = timeout_sec

    def trigger_mount(self, target: Target, remote_iso_path: str) -> bool:
        if not target.webman_port:
            return False

        encoded_path = quote(remote_iso_path, safe="/")
        url = f"http://{target.ip_address}:{target.webman_port}/mount.ps3{encoded_path}"

        logger.info("Triggering webMAN mount for target_id=%s", target.id)
        with urlopen(url, timeout=self.timeout_sec) as response:  # noqa: S310
            if 200 <= response.status < 300:
                return True
            raise RuntimeError(f"webMAN returned HTTP status {response.status}")
