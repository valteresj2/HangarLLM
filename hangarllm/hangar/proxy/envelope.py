"""Envelope encryption: the salt key is stored only as ciphertext that a KMS must open at startup.

Someone holding the database and the wrapped value still needs KMS access to read stored credentials.

Create the wrapped value from an existing salt, so stored credentials stay readable::

    python -m hangarllm.hangar.proxy.envelope wrap --salt-file /run/secrets/salt_key
"""

import argparse
import base64
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, Protocol

import httpx

SALT_ENV_VAR: Final = "HANGARLLM_SALT_KEY"
WRAPPED_ENV_VAR: Final = "HANGARLLM_SALT_KEY_WRAPPED"
PROVIDER_ENV_VAR: Final = "HANGARLLM_KMS_PROVIDER"
KEY_ID_ENV_VAR: Final = "HANGARLLM_KMS_KEY_ID"
_TIMEOUT: Final = httpx.Timeout(15.0, connect=5.0)


class EnvelopeError(Exception):
    pass


class KmsClient(Protocol):
    def wrap(self, plaintext: bytes) -> str: ...

    def unwrap(self, wrapped: str) -> bytes: ...


@dataclass(frozen=True, slots=True)
class AwsKms:
    key_id: str

    def _client(self):
        import boto3

        return boto3.client("kms", region_name=os.getenv("AWS_REGION_NAME") or os.getenv("AWS_REGION"))

    def wrap(self, plaintext: bytes) -> str:
        response: Final = self._client().encrypt(KeyId=self.key_id, Plaintext=plaintext)
        return base64.b64encode(response["CiphertextBlob"]).decode()

    def unwrap(self, wrapped: str) -> bytes:
        return self._client().decrypt(KeyId=self.key_id, CiphertextBlob=base64.b64decode(wrapped))["Plaintext"]


def _checked_json(response: httpx.Response, provider: str) -> dict[str, object]:
    if response.status_code != 200:
        raise EnvelopeError(f"{provider} returned HTTP {response.status_code}")
    return response.json()


@dataclass(frozen=True, slots=True)
class GcpKms:
    key_id: str

    def _headers(self) -> dict[str, str]:
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloudkms"])
        credentials.refresh(google.auth.transport.requests.Request())
        return {"Authorization": f"Bearer {credentials.token}"}

    def _call(self, verb: str, body: Mapping[str, str]) -> dict[str, object]:
        url: Final = f"https://cloudkms.googleapis.com/v1/{self.key_id}:{verb}"
        return _checked_json(httpx.post(url, json=dict(body), headers=self._headers(), timeout=_TIMEOUT), "Cloud KMS")

    def wrap(self, plaintext: bytes) -> str:
        return str(self._call("encrypt", {"plaintext": base64.b64encode(plaintext).decode()})["ciphertext"])

    def unwrap(self, wrapped: str) -> bytes:
        return base64.b64decode(str(self._call("decrypt", {"ciphertext": wrapped})["plaintext"]))


@dataclass(frozen=True, slots=True)
class VaultTransit:
    key_id: str
    address: str
    token: str
    namespace: str | None = None

    def _call(self, verb: str, body: Mapping[str, str]) -> Mapping[str, str]:
        headers: Final = {"X-Vault-Token": self.token, **({"X-Vault-Namespace": self.namespace} if self.namespace else {})}
        url: Final = f"{self.address.rstrip('/')}/v1/transit/{verb}/{self.key_id}"
        payload: Final = _checked_json(httpx.post(url, json=dict(body), headers=headers, timeout=_TIMEOUT), "Vault")
        data: Final = payload.get("data")
        if not isinstance(data, Mapping):
            raise EnvelopeError("Vault returned no data")
        return data

    def wrap(self, plaintext: bytes) -> str:
        return self._call("encrypt", {"plaintext": base64.b64encode(plaintext).decode()})["ciphertext"]

    def unwrap(self, wrapped: str) -> bytes:
        return base64.b64decode(self._call("decrypt", {"ciphertext": wrapped})["plaintext"])


def kms_client(environ: Mapping[str, str]) -> KmsClient:
    provider: Final = environ.get(PROVIDER_ENV_VAR, "").strip().lower()
    key_id: Final = environ.get(KEY_ID_ENV_VAR, "").strip()
    if not key_id:
        raise EnvelopeError(f"{KEY_ID_ENV_VAR} is required")
    match provider:
        case "aws":
            return AwsKms(key_id)
        case "gcp":
            return GcpKms(key_id)
        case "vault":
            address: Final = environ.get("HCP_VAULT_ADDR", "")
            token: Final = environ.get("HCP_VAULT_TOKEN", "")
            if not address or not token:
                raise EnvelopeError("The vault provider needs HCP_VAULT_ADDR and HCP_VAULT_TOKEN")
            return VaultTransit(key_id, address, token, environ.get("HCP_VAULT_NAMESPACE"))
        case _:
            raise EnvelopeError(f"{PROVIDER_ENV_VAR} must be aws, gcp or vault, got '{provider}'")


def unwrap_salt_key_from_kms(
    environ: Mapping[str, str] = os.environ,
    client_factory: Callable[[Mapping[str, str]], KmsClient] = kms_client,
) -> str | None:
    """Open the wrapped salt key and return it for this process, or None when no envelope is configured."""
    wrapped: Final = environ.get(WRAPPED_ENV_VAR)
    if not wrapped:
        return None
    if environ.get(SALT_ENV_VAR):
        raise EnvelopeError(f"Set either {SALT_ENV_VAR} or {WRAPPED_ENV_VAR}, not both")
    try:
        return client_factory(environ).unwrap(wrapped.strip()).decode()
    except EnvelopeError:
        raise
    except Exception as error:
        raise EnvelopeError(f"The KMS could not open the salt key: {type(error).__name__}") from error


def install_salt_key_from_kms() -> None:
    salt: Final = unwrap_salt_key_from_kms()
    if salt is not None:
        os.environ[SALT_ENV_VAR] = salt


def main() -> None:
    parser: Final = argparse.ArgumentParser(description="Wrap a salt key with the configured KMS")
    parser.add_argument("command", choices=["wrap"])
    parser.add_argument("--salt-file", required=True)
    args: Final = parser.parse_args()
    with open(args.salt_file, encoding="utf-8") as salt_file:
        salt: Final = salt_file.read().strip()
    print(kms_client(os.environ).wrap(salt.encode()))


if __name__ == "__main__":
    main()
