"""Клиент защищённого API SwimRocket для версии коллег."""
from pathlib import Path

import requests


class ApiClient:
    def __init__(self, base_url, token="", timeout=45):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    @staticmethod
    def exchange_code(base_url, code):
        client = ApiClient(base_url)
        return client._request("POST", "/v1/setup/exchange", json={"code": code})

    def _request(self, method, path, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        response = self.session.request(method, self.base_url + path, **kwargs)
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            data = response.json()
        else:
            data = response.content
        if response.status_code >= 400:
            if isinstance(data, dict):
                message = data.get("error") or f"HTTP {response.status_code}"
            else:
                message = f"HTTP {response.status_code}"
            raise RuntimeError(f"{method} {path}: {message}")
        return data

    def me(self):
        return self._request("GET", "/v1/me")

    def create_job(self, metadata):
        return self._request("POST", "/v1/jobs", json=metadata)

    def upload_audio(self, job_id, role, file_path, progress=None):
        path = Path(file_path)
        with path.open("rb") as handle:
            return self._request(
                "PUT", f"/v1/jobs/{job_id}/audio/{role}", data=handle,
                headers={"Content-Type": "application/octet-stream"},
                timeout=7200,
            )

    def complete_job(self, job_id):
        return self._request("POST", f"/v1/jobs/{job_id}/complete", json={})

    def status(self, job_id):
        return self._request("GET", f"/v1/jobs/{job_id}")

    def download(self, job_id, name, target):
        data = self._request("GET", f"/v1/jobs/{job_id}/{name}", timeout=300)
        Path(target).write_bytes(data)
        return target
