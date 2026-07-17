from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import json
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings


class YotoTokenStoreError(RuntimeError):
    pass


@dataclass
class StoredYotoTokens:
    access_token: str
    refresh_token: str | None
    token_type: str | None
    scope: str | None
    expires_at: datetime | None
    id_token: str | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_type": self.token_type,
            "scope": self.scope,
            "id_token": self.id_token,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "StoredYotoTokens":
        expires_at_raw = payload.get("expires_at")
        expires_at: datetime | None = None
        if isinstance(expires_at_raw, str) and expires_at_raw:
            expires_at = datetime.fromisoformat(expires_at_raw)
        return cls(
            access_token=str(payload["access_token"]),
            refresh_token=str(payload["refresh_token"]) if payload.get("refresh_token") else None,
            token_type=str(payload["token_type"]) if payload.get("token_type") else None,
            scope=str(payload["scope"]) if payload.get("scope") else None,
            id_token=str(payload["id_token"]) if payload.get("id_token") else None,
            expires_at=expires_at,
        )


def build_secret_key(*, credential_id: int) -> str:
    return f"yoto-credential-{credential_id}.json"


def build_storage_ref(*, secret_name: str, secret_namespace: str, secret_key: str) -> str:
    return f"k8s-secret:{secret_namespace}:{secret_name}:{secret_key}"


def parse_storage_ref(storage_ref: str) -> tuple[str, str, str]:
    parts = storage_ref.split(":", 3)
    if len(parts) != 4 or parts[0] != "k8s-secret":
        raise YotoTokenStoreError(f"Unsupported Yoto token storage reference: {storage_ref}")
    return parts[1], parts[2], parts[3]


def _service_account_paths() -> tuple[Path, Path]:
    base = Path("/var/run/secrets/kubernetes.io/serviceaccount")
    return base / "token", base / "ca.crt"


def _secret_api_url(*, namespace: str, name: str) -> str:
    return f"https://kubernetes.default.svc/api/v1/namespaces/{namespace}/secrets/{name}"


def _kubernetes_request_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


async def save_tokens_to_secret(
    *,
    credential_id: int,
    tokens: StoredYotoTokens,
) -> str:
    settings = get_settings()
    if settings.yoto_token_store_mode != "kubernetes_secret":
        raise YotoTokenStoreError(f"Unsupported Yoto token store mode: {settings.yoto_token_store_mode}")

    token_path, ca_path = _service_account_paths()
    if not token_path.exists() or not ca_path.exists():
        raise YotoTokenStoreError("Kubernetes service account credentials are not mounted in this container.")

    secret_key = build_secret_key(credential_id=credential_id)
    encoded_payload = base64.b64encode(json.dumps(tokens.to_payload()).encode("utf-8")).decode("ascii")
    body = {"data": {secret_key: encoded_payload}}

    async with httpx.AsyncClient(timeout=30, verify=str(ca_path)) as client:
        response = await client.patch(
            _secret_api_url(namespace=settings.yoto_token_secret_namespace, name=settings.yoto_token_secret_name),
            headers={
                **_kubernetes_request_headers(token_path.read_text(encoding="utf-8").strip()),
                "Content-Type": "application/merge-patch+json",
            },
            json=body,
        )
    if response.status_code >= 400:
        detail = response.text[:500] if response.text else "Kubernetes secret update failed."
        raise YotoTokenStoreError(detail)

    return build_storage_ref(
        secret_name=settings.yoto_token_secret_name,
        secret_namespace=settings.yoto_token_secret_namespace,
        secret_key=secret_key,
    )


async def load_tokens_from_secret(storage_ref: str) -> StoredYotoTokens:
    namespace, name, secret_key = parse_storage_ref(storage_ref)
    token_path, ca_path = _service_account_paths()
    if not token_path.exists() or not ca_path.exists():
        raise YotoTokenStoreError("Kubernetes service account credentials are not mounted in this container.")

    async with httpx.AsyncClient(timeout=30, verify=str(ca_path)) as client:
        response = await client.get(
            _secret_api_url(namespace=namespace, name=name),
            headers=_kubernetes_request_headers(token_path.read_text(encoding="utf-8").strip()),
        )
    if response.status_code >= 400:
        detail = response.text[:500] if response.text else "Kubernetes secret read failed."
        raise YotoTokenStoreError(detail)

    payload = response.json()
    secret_data = payload.get("data")
    if not isinstance(secret_data, dict) or secret_key not in secret_data:
        raise YotoTokenStoreError(f"Stored Yoto token payload {secret_key} was not found in Kubernetes Secret {name}.")

    try:
        decoded = base64.b64decode(str(secret_data[secret_key]))
        data = json.loads(decoded)
    except (ValueError, json.JSONDecodeError) as error:
        raise YotoTokenStoreError(f"Stored Yoto token payload {secret_key} is not valid JSON.") from error
    if not isinstance(data, dict):
        raise YotoTokenStoreError(f"Stored Yoto token payload {secret_key} is not a JSON object.")
    return StoredYotoTokens.from_payload(data)


async def delete_tokens_from_secret(storage_ref: str) -> None:
    namespace, name, secret_key = parse_storage_ref(storage_ref)
    token_path, ca_path = _service_account_paths()
    if not token_path.exists() or not ca_path.exists():
        raise YotoTokenStoreError("Kubernetes service account credentials are not mounted in this container.")

    async with httpx.AsyncClient(timeout=30, verify=str(ca_path)) as client:
        response = await client.patch(
            _secret_api_url(namespace=namespace, name=name),
            headers={
                **_kubernetes_request_headers(token_path.read_text(encoding="utf-8").strip()),
                "Content-Type": "application/merge-patch+json",
            },
            json={"data": {secret_key: None}},
        )
    if response.status_code >= 400:
        detail = response.text[:500] if response.text else "Kubernetes secret delete failed."
        raise YotoTokenStoreError(detail)
