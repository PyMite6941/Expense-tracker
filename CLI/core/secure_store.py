"""Encryption for credentials the app has to keep on disk.

WHAT THIS PROTECTS AGAINST, precisely — because overstating it is worse than
not having it:

  * The config file being readable if it is synced to OneDrive/Dropbox, ends up
    in a backup, is attached to a bug report, or is accidentally committed.
  * Anyone who gets ONE of the two files. The ciphertext and the key live
    separately; neither is useful alone.

WHAT IT DOES NOT PROTECT AGAINST:

  * Someone with full access to the machine and the user's account. The app has
    to be able to decrypt unattended so the Telegram/Discord bots can run, so
    the key must be readable by the same user the app runs as. That is an
    unavoidable consequence of unattended operation, not an oversight.

For a threat model that includes local attackers you need a passphrase the user
types each run, which rules out background bots. That tradeoff belongs to the
user, so `encrypt`/`decrypt` accept an optional passphrase and fall back to the
key file when none is given.

AES-256-GCM: authenticated, so tampering is detected rather than silently
decrypting to rubbish. Scrypt for passphrase derivation (memory-hard, so a
stolen file resists offline cracking far better than a plain hash).
"""
from __future__ import annotations

import base64
import json
import os
import secrets
from typing import Any, Dict, Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

# Marks a file as written by this module, so a plaintext config from an older
# build is recognised and upgraded rather than failing to parse.
_MAGIC = "fk-enc-v1"
_KEY_BYTES = 32          # AES-256
_NONCE_BYTES = 12        # GCM standard
_SALT_BYTES = 16
_SCRYPT_N = 2 ** 15      # ~32 MB, tuned to stay responsive in a Streamlit rerun


class DecryptionError(RuntimeError):
    """Wrong key, wrong passphrase, or the file has been tampered with."""


def _key_path(data_path: str) -> str:
    """Where the key for a given config file lives — deliberately beside it but
    in a separate file, so leaking one leaks nothing."""
    directory, name = os.path.split(os.path.abspath(data_path))
    return os.path.join(directory, f".{name}.key")


def _load_or_create_key(data_path: str) -> bytes:
    path = _key_path(data_path)
    if os.path.exists(path):
        with open(path, "rb") as fh:
            raw = base64.urlsafe_b64decode(fh.read().strip())
            if len(raw) == _KEY_BYTES:
                return raw
    key = AESGCM.generate_key(bit_length=256)
    with open(path, "wb") as fh:
        fh.write(base64.urlsafe_b64encode(key))
    try:
        # Owner read/write only. Best effort: on Windows this is largely
        # advisory, which is part of why the local-attacker case is out of scope.
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _derive(passphrase: str, salt: bytes) -> bytes:
    return Scrypt(salt=salt, length=_KEY_BYTES, n=_SCRYPT_N, r=8, p=1).derive(
        passphrase.encode("utf-8")
    )


def encrypt_dict(payload: Dict[str, Any], data_path: str,
                 passphrase: Optional[str] = None) -> Dict[str, str]:
    """Encrypt a config dict into an envelope safe to write to disk."""
    plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    nonce = secrets.token_bytes(_NONCE_BYTES)

    if passphrase:
        salt = secrets.token_bytes(_SALT_BYTES)
        key = _derive(passphrase, salt)
        salt_b64 = base64.urlsafe_b64encode(salt).decode()
    else:
        key = _load_or_create_key(data_path)
        salt_b64 = ""

    # The magic string is authenticated too, so an envelope cannot be relabelled.
    ct = AESGCM(key).encrypt(nonce, plaintext, _MAGIC.encode())
    return {
        "_format": _MAGIC,
        "kdf": "scrypt" if passphrase else "keyfile",
        "salt": salt_b64,
        "nonce": base64.urlsafe_b64encode(nonce).decode(),
        "data": base64.urlsafe_b64encode(ct).decode(),
    }


def decrypt_dict(envelope: Any, data_path: str,
                 passphrase: Optional[str] = None) -> Dict[str, Any]:
    """Decrypt an envelope. A plain dict from an older build passes straight
    through, so upgrading does not strand anyone's existing config."""
    if not isinstance(envelope, dict):
        return {}
    if envelope.get("_format") != _MAGIC:
        return envelope  # legacy plaintext config — caller re-saves it encrypted

    try:
        nonce = base64.urlsafe_b64decode(envelope["nonce"])
        ct = base64.urlsafe_b64decode(envelope["data"])
        if envelope.get("kdf") == "scrypt":
            if not passphrase:
                raise DecryptionError("This config needs its passphrase.")
            key = _derive(passphrase, base64.urlsafe_b64decode(envelope["salt"]))
        else:
            key = _load_or_create_key(data_path)
        return json.loads(AESGCM(key).decrypt(nonce, ct, _MAGIC.encode()))
    except InvalidTag as exc:
        raise DecryptionError(
            "Could not decrypt: wrong passphrase, wrong key file, or the file "
            "has been altered."
        ) from exc
    except (KeyError, ValueError, TypeError) as exc:
        raise DecryptionError(f"Config file is not readable: {exc}") from exc


def is_encrypted(envelope: Any) -> bool:
    return isinstance(envelope, dict) and envelope.get("_format") == _MAGIC


def load_secure(path: str, passphrase: Optional[str] = None) -> Dict[str, Any]:
    """Read a config file, encrypted or legacy plaintext. {} if absent."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}
    return decrypt_dict(raw, path, passphrase)


def save_secure(path: str, payload: Dict[str, Any],
                passphrase: Optional[str] = None) -> None:
    """Write a config file encrypted at rest."""
    envelope = encrypt_dict(payload, path, passphrase)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(envelope, fh, indent=2)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Encryption at rest for hosted (database) storage
#
# Different threat model from the credential store above. Here the SERVER holds
# the key, deliberately: hosted users still want net worth, forecasts and
# anomaly detection computed for them, and a server cannot total what it cannot
# read. This protects a leaked database credential, a stolen backup, or a
# snapshot copied somewhere it should not be — not the application itself.
#
# Saying that plainly matters. "Encrypted at rest" is often read as "nobody can
# read it", and that is not what this is.
# ---------------------------------------------------------------------------

_ROW_MAGIC = b"fk-row-v1"


class MissingKeyError(RuntimeError):
    """ET_ENCRYPTION_KEY is not set, so stored data cannot be read or written."""


def _rest_key() -> bytes:
    """The at-rest key, from the environment (Secret Manager in production).

    Never stored in the database — a key sitting beside the ciphertext it
    protects is not a key, it is a formality.
    """
    raw = (os.environ.get("ET_ENCRYPTION_KEY") or "").strip()
    if not raw:
        raise MissingKeyError(
            "ET_ENCRYPTION_KEY is not set. Hosted storage is encrypted at rest, "
            "so without it rows can be neither written nor read. Generate one "
            "with: python -c \"import base64,os;"
            "print(base64.urlsafe_b64encode(os.urandom(32)).decode())\""
        )
    try:
        key = base64.urlsafe_b64decode(raw)
    except Exception as exc:
        raise MissingKeyError("ET_ENCRYPTION_KEY is not valid base64.") from exc
    if len(key) != _KEY_BYTES:
        raise MissingKeyError(
            f"ET_ENCRYPTION_KEY must decode to {_KEY_BYTES} bytes "
            f"(got {len(key)}); it should be a base64 32-byte key."
        )
    return key


def encryption_enabled() -> bool:
    """True when at-rest encryption is configured. Lets the app report honestly
    rather than claiming protection it does not have."""
    try:
        _rest_key()
        return True
    except MissingKeyError:
        return False


def encrypt_row(payload: Dict[str, Any], aad: str = "") -> bytes:
    """Encrypt one row's fields for storage.

    `aad` binds the ciphertext to its context (table name + row id), so a row
    cannot be lifted from one table or org and replayed into another — the
    authentication check fails.
    """
    nonce = secrets.token_bytes(_NONCE_BYTES)
    plaintext = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    ct = AESGCM(_rest_key()).encrypt(nonce, plaintext, _ROW_MAGIC + aad.encode())
    return _ROW_MAGIC + nonce + ct


def decrypt_row(blob: Any, aad: str = "") -> Dict[str, Any]:
    """Decrypt a stored row. {} for an empty/absent value."""
    if not blob:
        return {}
    raw = bytes(blob)
    if not raw.startswith(_ROW_MAGIC):
        raise DecryptionError("Stored row is not in the expected encrypted format.")
    body = raw[len(_ROW_MAGIC):]
    nonce, ct = body[:_NONCE_BYTES], body[_NONCE_BYTES:]
    try:
        return json.loads(AESGCM(_rest_key()).decrypt(nonce, ct, _ROW_MAGIC + aad.encode()))
    except InvalidTag as exc:
        raise DecryptionError(
            "Row failed its authentication check — wrong key, or the row has "
            "been altered or moved between tables."
        ) from exc
