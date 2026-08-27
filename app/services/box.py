"""888box asset storage service client with automatic multi-endpoint failover."""

import os
import requests
from typing import Optional, Dict, Any, List

DEFAULT_BOX_ENDPOINTS = [
    "https://box.david888.com",  # 主要節點
    "https://box.glsoft.ai",    # 備用節點 1
    "https://box.aiurl.tw",     # 備用節點 2
]


def get_box_endpoints() -> List[str]:
    """Retrieve list of 888box endpoints with primary and fallbacks."""
    custom = os.environ.get("BOX_API_ENDPOINTS", "")
    if custom:
        eps = [ep.strip().rstrip("/") for ep in custom.split(",") if ep.strip()]
        if eps:
            return eps
    base_url = os.environ.get("BOX_API_BASE_URL", "").strip().rstrip("/")
    if base_url:
        return [base_url] + [ep for ep in DEFAULT_BOX_ENDPOINTS if ep != base_url]
    return DEFAULT_BOX_ENDPOINTS.copy()


BOX_API_TOKEN = os.environ.get("BOX_API_TOKEN", "")


def upload_file_to_box(
    file_path: str,
    title: str = "",
    description: str = "",
    password: str = "",
    token: Optional[str] = None,
    timeout: int = 60
) -> Dict[str, Any]:
    """Upload local file (text, pdf, audio, video, etc.) to 888box with fallback."""
    endpoints = get_box_endpoints()
    api_token = token or BOX_API_TOKEN
    data = {}
    if title:
        data["title"] = title
    if description:
        data["description"] = description
    if password:
        data["password"] = password
    if api_token:
        data["token"] = api_token

    filename = os.path.basename(file_path)
    last_error = "No endpoints available"

    for ep in endpoints:
        url = f"{ep}/api.php?action=upload"
        try:
            with open(file_path, "rb") as f:
                files = {"file": (filename, f)}
                response = requests.post(url, files=files, data=data, timeout=timeout)

            res_json = response.json()
            if res_json.get("result") == "success":
                return {
                    "success": True,
                    "id": res_json.get("data", {}).get("id"),
                    "url": res_json.get("data", {}).get("url"),
                    "share_url": res_json.get("data", {}).get("share_url"),
                    "endpoint": ep,
                }
            else:
                last_error = res_json.get("message", f"Upload failed on {ep}")
                print(f"[888box] Upload failed on {ep}: {last_error}, trying fallback...")
        except Exception as e:
            last_error = str(e)
            print(f"[888box] Exception on {ep}: {e}, trying fallback...")

    return {"success": False, "error": last_error}


def upload_url_to_box(
    remote_url: str,
    title: str = "",
    description: str = "",
    password: str = "",
    token: Optional[str] = None,
    timeout: int = 60
) -> Dict[str, Any]:
    """Upload remote asset URL to 888box with fallback."""
    endpoints = get_box_endpoints()
    api_token = token or BOX_API_TOKEN
    payload = {"url": remote_url}
    if title:
        payload["title"] = title
    if description:
        payload["description"] = description
    if password:
        payload["password"] = password
    if api_token:
        payload["token"] = api_token

    last_error = "No endpoints available"

    for ep in endpoints:
        endpoint = f"{ep}/api.php?action=upload_url"
        try:
            response = requests.post(endpoint, data=payload, timeout=timeout)
            res_json = response.json()
            if res_json.get("result") == "success":
                return {
                    "success": True,
                    "id": res_json.get("data", {}).get("id"),
                    "url": res_json.get("data", {}).get("url"),
                    "share_url": res_json.get("data", {}).get("share_url"),
                    "endpoint": ep,
                }
            else:
                last_error = res_json.get("message", f"Upload by URL failed on {ep}")
                print(f"[888box] URL upload failed on {ep}: {last_error}, trying fallback...")
        except Exception as e:
            last_error = str(e)
            print(f"[888box] Exception on {ep}: {e}, trying fallback...")

    return {"success": False, "error": last_error}


def get_box_stats(token: Optional[str] = None, timeout: int = 15) -> Dict[str, Any]:
    """Get asset statistics from 888box with fallback."""
    endpoints = get_box_endpoints()
    api_token = token or BOX_API_TOKEN
    params = {}
    if api_token:
        params["token"] = api_token

    last_error = "No endpoints available"

    for ep in endpoints:
        endpoint = f"{ep}/api.php?action=stats"
        try:
            response = requests.get(endpoint, params=params, timeout=timeout)
            res_json = response.json()
            if res_json.get("result") == "success":
                return {
                    "success": True,
                    "data": res_json.get("data", {}),
                    "endpoint": ep,
                }
            else:
                last_error = res_json.get("message", f"Failed to get stats on {ep}")
        except Exception as e:
            last_error = str(e)

    return {"success": False, "error": last_error}
