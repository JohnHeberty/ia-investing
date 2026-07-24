from __future__ import annotations

import contextlib
import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import ClassVar


class SecretsManager(ABC):
    @abstractmethod
    def get_secret(self, key: str) -> str: ...

    @abstractmethod
    def get_secret_or_default(self, key: str, default: str) -> str: ...

    @abstractmethod
    def list_secrets(self, prefix: str) -> dict[str, str]: ...


class EnvSecretsManager(SecretsManager):
    def get_secret(self, key: str) -> str:
        value = os.environ.get(key)
        if value is None:
            raise KeyError(f"Secret {key!r} not found in environment")
        return value

    def get_secret_or_default(self, key: str, default: str) -> str:
        return os.environ.get(key, default)

    def list_secrets(self, prefix: str) -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if k.startswith(prefix)}


class VaultSecretsManager(SecretsManager):
    _VAULT_ADDR_ENV: ClassVar[str] = "VAULT_ADDR"
    _VAULT_TOKEN_ENV: ClassVar[str] = "VAULT_TOKEN"

    def __init__(self, addr: str | None = None, token: str | None = None) -> None:
        self._addr = addr or os.environ.get(self._VAULT_ADDR_ENV, "")
        self._token = token or os.environ.get(self._VAULT_TOKEN_ENV, "")
        if not self._addr or not self._token:
            raise RuntimeError("VaultSecretsManager requires both VAULT_ADDR and VAULT_TOKEN environment variables")

    def _read(self, path: str) -> str:
        url = f"{self._addr.rstrip('/')}/v1/{path.lstrip('/')}"
        headers = {"X-Vault-Token": self._token, "Accept": "application/json"}
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            secret_data = data.get("data", {}).get("data", {})
            if isinstance(secret_data, dict) and len(secret_data) == 1:
                return next(iter(secret_data.values()))
            if isinstance(secret_data, dict):
                return json.dumps(secret_data)
            return str(secret_data)
        except urllib.error.HTTPError as exc:
            raise KeyError(f"Vault secret at {path!r} not found: {exc}") from exc

    def get_secret(self, key: str) -> str:
        return self._read(key)

    def get_secret_or_default(self, key: str, default: str) -> str:
        try:
            return self._read(key)
        except KeyError:
            return default

    def list_secrets(self, prefix: str) -> dict[str, str]:
        url = f"{self._addr.rstrip('/')}/v1/{prefix.lstrip('/')}?list=true"
        headers = {"X-Vault-Token": self._token, "Accept": "application/json"}
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError:
            return {}
        keys = data.get("data", {}).get("keys", [])
        result: dict[str, str] = {}
        for k in keys:
            with contextlib.suppress(KeyError):
                result[k] = self._read(f"{prefix.rstrip('/')}/{k}")
        return result


def create_secrets_manager() -> SecretsManager:
    vault_addr = os.environ.get(VaultSecretsManager._VAULT_ADDR_ENV)
    vault_token = os.environ.get(VaultSecretsManager._VAULT_TOKEN_ENV)
    if vault_addr and vault_token:
        return VaultSecretsManager(addr=vault_addr, token=vault_token)
    return EnvSecretsManager()
