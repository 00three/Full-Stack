"""Asset proxy APIs used by browser-only export features."""

from __future__ import annotations

import ipaddress
import socket
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response


router = APIRouter(prefix="/assets", tags=["assets"])

_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_UA = "ai-breaking-news-export/1.0"


def _validate_remote_image_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="http/https 이미지만 지원합니다.")
    if not parsed.hostname:
        raise HTTPException(status_code=400, detail="이미지 호스트가 없습니다.")

    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror as exc:
        raise HTTPException(status_code=400, detail="이미지 호스트를 확인할 수 없습니다.") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(status_code=400, detail="허용되지 않은 이미지 호스트입니다.")

    return urllib.parse.urlunparse(parsed)


@router.get("/image-proxy")
def proxy_image(url: str):
    """Fetch a remote image through the backend so browser docx export avoids CORS."""
    safe_url = _validate_remote_image_url(url)
    request = urllib.request.Request(safe_url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(request, timeout=8) as remote:
            content_type = remote.headers.get("Content-Type", "application/octet-stream").split(";")[0]
            if not content_type.startswith("image/"):
                raise HTTPException(status_code=400, detail="이미지 응답이 아닙니다.")
            data = remote.read(_MAX_IMAGE_BYTES + 1)
    except HTTPException:
        raise
    except (urllib.error.URLError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail="이미지를 가져오지 못했습니다.") from exc

    if len(data) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="이미지가 너무 큽니다.")

    return Response(content=data, media_type=content_type)
