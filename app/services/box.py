"""888box asset storage service client."""

import os
import requests
from typing import Optional, Dict, Any

BOX_API_BASE_URL = os.environ.get("BOX_API_BASE_URL", "https://box.david888.com")
BOX_API_TOKEN = os.environ.get("BOX_API_TOKEN", "")


def upload_file_to_box(
    file_path: str,
    title: str = "",
    description: str = "",
    password: str = "",
    token: Optional[str] = None,
    timeout: int = 60
) -> Dict[str, Any]:
    """Upload local file (text, pdf, audio, video, etc.) to 888box."""
    url = f"{BOX_API_BASE_URL.rstrip('/')}/api.php?action=upload"
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

    try:
        filename = os.path.basename(file_path)
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
            }
        else:
            return {
                "success": False,
                "error": res_json.get("message", "Upload failed")
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def upload_url_to_box(
    remote_url: str,
    title: str = "",
    description: str = "",
    password: str = "",
    token: Optional[str] = None,
    timeout: int = 60
) -> Dict[str, Any]:
    """Upload remote asset URL to 888box."""
    endpoint = f"{BOX_API_BASE_URL.rstrip('/')}/api.php?action=upload_url"
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

    try:
        response = requests.post(endpoint, data=payload, timeout=timeout)
        res_json = response.json()
        if res_json.get("result") == "success":
            return {
                "success": True,
                "id": res_json.get("data", {}).get("id"),
                "url": res_json.get("data", {}).get("url"),
                "share_url": res_json.get("data", {}).get("share_url"),
            }
        else:
            return {
                "success": False,
                "error": res_json.get("message", "Upload by URL failed")
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_box_stats(token: Optional[str] = None, timeout: int = 15) -> Dict[str, Any]:
    """Get asset statistics from 888box."""
    endpoint = f"{BOX_API_BASE_URL.rstrip('/')}/api.php?action=stats"
    api_token = token or BOX_API_TOKEN
    params = {}
    if api_token:
        params["token"] = api_token
    try:
        response = requests.get(endpoint, params=params, timeout=timeout)
        res_json = response.json()
        if res_json.get("result") == "success":
            return {
                "success": True,
                "data": res_json.get("data", {})
            }
        else:
            return {
                "success": False,
                "error": res_json.get("message", "Failed to get stats")
            }
    except Exception as e:
        return {"success": False, "error": str(e)}
