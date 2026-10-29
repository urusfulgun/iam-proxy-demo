"""Pinned home-realm keypairs (docs/specs/2026-10-29-realm-keypairs).

Messages name realms and variables only, never a key or cert value.
"""

import base64
import binascii
import json
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx2
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from tests.conftest import KEYCLOAK

ROOT = Path(__file__).resolve().parent.parent
REALMS = ROOT / "keycloak/realms"
HOMES = {"home-fau": "HOME_FAU", "home-bamberg": "HOME_BAMBERG"}
KEY_PROVIDERS = "org.keycloak.keys.KeyProvider"

# A PEM header or a long base64 run is an inline key or cert, e.g. from `make export`.
_INLINE_SECRET = re.compile(r"-----BEGIN|[A-Za-z0-9+/=]{200,}")


def _on(config: dict[str, list[str]], name: str) -> bool:
    # Keycloak treats a missing enabled/active as true.
    return config.get(name, ["true"]) == ["true"]


def key_problems(realm: dict[str, Any], prefix: str) -> list[str]:
    """Why `realm` doesn't sign with exactly the pinned `<prefix>_SAML_*` keypair."""
    providers = realm.get("components", {}).get(KEY_PROVIDERS, [])
    rsa = [
        p
        for p in providers
        if p.get("providerId") == "rsa"
        and _on(p.get("config", {}), "enabled")
        and _on(p.get("config", {}), "active")
    ]
    if len(rsa) != 1:
        return [f"want 1 enabled, active rsa provider, found {len(rsa)}"]
    config = rsa[0]["config"]
    problems = []
    if int(config.get("priority", ["0"])[0]) <= 100:
        problems.append("rsa provider priority must be above 100")
    if config.get("algorithm", ["RS256"]) != ["RS256"]:
        problems.append("rsa provider algorithm must be RS256")
    for field, var in (("privateKey", "PRIVATE_KEY"), ("certificate", "CERT")):
        if config.get(field) != [f"$(env:{prefix}_SAML_{var})"]:
            problems.append(f"{field} must be $(env:{prefix}_SAML_{var})")
    generated = [p for p in providers if p.get("providerId") == "rsa-generated"]
    if not generated or any(_on(p.get("config", {}), "enabled") for p in generated):
        problems.append("rsa-generated must be declared with enabled false")
    return problems


def has_inline_secret(text: str) -> bool:
    return bool(_INLINE_SECRET.search(text))


def pinned_realm(prefix: str) -> dict[str, Any]:
    return {
        "components": {
            KEY_PROVIDERS: [
                {
                    "name": "pinned",
                    "providerId": "rsa",
                    "config": {
                        "priority": ["200"],
                        "algorithm": ["RS256"],
                        "privateKey": [f"$(env:{prefix}_SAML_PRIVATE_KEY)"],
                        "certificate": [f"$(env:{prefix}_SAML_CERT)"],
                    },
                },
                {
                    "name": "rsa-generated",
                    "providerId": "rsa-generated",
                    "config": {"enabled": ["false"]},
                },
            ]
        }
    }


def providers(realm: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = realm["components"][KEY_PROVIDERS]
    return result


def test_key_problems_none_for_pinned_realm() -> None:
    assert key_problems(pinned_realm("HOME_FAU"), "HOME_FAU") == []


def test_key_problems_missing_provider() -> None:
    assert key_problems({"realm": "x"}, "HOME_FAU") == [
        "want 1 enabled, active rsa provider, found 0"
    ]


def test_key_problems_second_active_rsa_provider() -> None:
    realm = pinned_realm("HOME_FAU")
    providers(realm).append({**providers(realm)[0], "name": "other"})
    assert key_problems(realm, "HOME_FAU") == [
        "want 1 enabled, active rsa provider, found 2"
    ]


def test_key_problems_literal_key() -> None:
    realm = pinned_realm("HOME_FAU")
    providers(realm)[0]["config"]["privateKey"] = ["MIIEvQIBADANBgkq"]
    assert key_problems(realm, "HOME_FAU") == [
        "privateKey must be $(env:HOME_FAU_SAML_PRIVATE_KEY)"
    ]


def test_key_problems_other_realms_variable() -> None:
    assert key_problems(pinned_realm("HOME_BAMBERG"), "HOME_FAU") == [
        "privateKey must be $(env:HOME_FAU_SAML_PRIVATE_KEY)",
        "certificate must be $(env:HOME_FAU_SAML_CERT)",
    ]


def test_key_problems_low_priority() -> None:
    realm = pinned_realm("HOME_FAU")
    providers(realm)[0]["config"]["priority"] = ["100"]
    assert key_problems(realm, "HOME_FAU") == [
        "rsa provider priority must be above 100"
    ]


def test_key_problems_generated_left_enabled() -> None:
    realm = pinned_realm("HOME_FAU")
    providers(realm)[1]["config"] = {}
    assert key_problems(realm, "HOME_FAU") == [
        "rsa-generated must be declared with enabled false"
    ]


def test_key_problems_generated_not_declared() -> None:
    realm = pinned_realm("HOME_FAU")
    providers(realm).pop()
    assert key_problems(realm, "HOME_FAU") == [
        "rsa-generated must be declared with enabled false"
    ]


def test_inline_secret_detected() -> None:
    assert has_inline_secret('"x": "-----BEGIN PRIVATE KEY-----"')
    assert has_inline_secret('"x": "' + "A" * 200 + '"')


def test_inline_secret_ignores_env_reference() -> None:
    assert not has_inline_secret(json.dumps(pinned_realm("HOME_FAU")))


@pytest.mark.parametrize("path", sorted(REALMS.glob("*.json")), ids=lambda p: p.name)
def test_realm_file_is_json_without_inline_secret(path: Path) -> None:
    text = path.read_text()
    json.loads(text)
    assert not has_inline_secret(text), f"{path.name} holds an inline key or cert"


@pytest.mark.parametrize("realm", HOMES)
def test_home_realm_signs_with_pinned_key(realm: str) -> None:
    problems = key_problems(
        json.loads((REALMS / f"{realm}.json").read_text()), HOMES[realm]
    )
    assert not problems, f"{realm}: " + "; ".join(problems)


def pair_problems(key_b64: str, cert_b64: str, now: datetime) -> list[str]:
    """Why a `.env` key/cert pair (bare base64 DER) can't be the realm's signing key."""
    try:
        key = serialization.load_der_private_key(base64.b64decode(key_b64), None)
        cert = x509.load_der_x509_certificate(base64.b64decode(cert_b64))
    except ValueError, binascii.Error:
        return ["key or cert does not parse"]
    if not isinstance(key, rsa.RSAPrivateKey):
        return ["key is not RSA"]
    problems = []
    if key.key_size < 2048:
        problems.append(f"key has {key.key_size} bits, want at least 2048")
    if cert.public_key() != key.public_key():
        problems.append("cert does not match key")
    if cert.not_valid_after_utc < now + timedelta(days=365):
        problems.append("cert expires within 365 days")
    return problems


def make_pair(bits: int = 2048, days: int = 3650) -> tuple[str, str]:
    """A self-signed pair in the `.env` format, as `make keys` writes it."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=bits)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=max(0, -days) + 1))
        .not_valid_after(now + timedelta(days=days))
        .sign(key, hashes.SHA256())
    )
    der_key = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    der_cert = cert.public_bytes(serialization.Encoding.DER)
    return base64.b64encode(der_key).decode(), base64.b64encode(der_cert).decode()


NOW = datetime.now(UTC)


def test_pair_problems_none_for_good_pair() -> None:
    assert pair_problems(*make_pair(), NOW) == []


def test_pair_problems_mismatched_pair() -> None:
    key, _ = make_pair()
    _, cert = make_pair()
    assert pair_problems(key, cert, NOW) == ["cert does not match key"]


def test_pair_problems_short_key() -> None:
    assert pair_problems(*make_pair(bits=1024), NOW) == [
        "key has 1024 bits, want at least 2048"
    ]


def test_pair_problems_expired_cert() -> None:
    assert pair_problems(*make_pair(days=-1), NOW) == ["cert expires within 365 days"]


def test_pair_problems_garbage_hides_value() -> None:
    problems = pair_problems("s3cret", "s3cret", NOW)
    assert problems == ["key or cert does not parse"]
    assert "s3cret" not in str(problems)


@pytest.mark.parametrize("realm", HOMES)
def test_local_env_pair_is_valid(realm: str, dotenv: dict[str, str]) -> None:
    prefix = HOMES[realm]
    key = dotenv.get(f"{prefix}_SAML_PRIVATE_KEY", "")
    cert = dotenv.get(f"{prefix}_SAML_CERT", "")
    problems = pair_problems(key, cert, NOW)
    assert not problems, f"{realm} (.env {prefix}_SAML_*): " + "; ".join(problems)


def home_keys_differ(env: dict[str, str]) -> bool:
    keys = [env.get(f"{prefix}_SAML_PRIVATE_KEY") for prefix in HOMES.values()]
    return len(set(keys)) == len(keys)


def test_home_keys_differ_rejects_shared_key() -> None:
    key, _ = make_pair()
    env = {"HOME_FAU_SAML_PRIVATE_KEY": key, "HOME_BAMBERG_SAML_PRIVATE_KEY": key}
    assert not home_keys_differ(env)


def test_local_env_home_keys_differ(dotenv: dict[str, str]) -> None:
    assert home_keys_differ(dotenv), "home realms share a signing key in .env"


# SAML2 Metadata 2.4.1.1: a KeyDescriptor with use="signing" carries the signing cert.
_MD = "{urn:oasis:names:tc:SAML:2.0:metadata}"
_DS = "{http://www.w3.org/2000/09/xmldsig#}"


def signing_certs(descriptor: str) -> list[str]:
    # Metadata from our own Keycloak, not untrusted input.
    root = ET.fromstring(descriptor)  # noqa: S314
    return [
        "".join((cert.text or "").split())
        for kd in root.iter(f"{_MD}KeyDescriptor")
        if kd.get("use") == "signing"
        for cert in kd.iter(f"{_DS}X509Certificate")
    ]


def test_signing_certs_ignores_encryption_keys() -> None:
    xml = (
        f'<md:EntityDescriptor xmlns:md="{_MD[1:-1]}" xmlns:ds="{_DS[1:-1]}">'
        '<md:KeyDescriptor use="signing">'
        "<ds:X509Certificate> AB\nCD </ds:X509Certificate>"
        '</md:KeyDescriptor><md:KeyDescriptor use="encryption"><ds:X509Certificate>EF'
        "</ds:X509Certificate></md:KeyDescriptor></md:EntityDescriptor>"
    )
    assert signing_certs(xml) == ["ABCD"]


@pytest.mark.e2e
@pytest.mark.parametrize("realm", HOMES)
def test_descriptor_publishes_only_pinned_cert(
    realm: str, dotenv: dict[str, str]
) -> None:
    url = f"{KEYCLOAK}/realms/{realm}/protocol/saml/descriptor"
    certs = signing_certs(httpx2.get(url).raise_for_status().text)
    assert certs == [dotenv[f"{HOMES[realm]}_SAML_CERT"]], (
        f"{realm}: descriptor has {len(certs)} signing certs, want only the pinned one"
    )


@pytest.mark.e2e
@pytest.mark.parametrize("realm", HOMES)
def test_jwks_has_only_pinned_rs256_key(realm: str, dotenv: dict[str, str]) -> None:
    # RFC 7517 4.7: x5c[0] is the cert holding the JWK's public key.
    url = f"{KEYCLOAK}/realms/{realm}/protocol/openid-connect/certs"
    keys = httpx2.get(url).raise_for_status().json()["keys"]
    rs256 = [k for k in keys if k.get("alg") == "RS256" and k.get("use") == "sig"]
    assert [k["x5c"][0] for k in rs256] == [dotenv[f"{HOMES[realm]}_SAML_CERT"]], (
        f"{realm}: JWKS has {len(rs256)} RS256 sig key(s), want only the pinned one"
    )


def admin_token(env: dict[str, str]) -> str:
    response = httpx2.post(
        f"{KEYCLOAK}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": env["KC_BOOTSTRAP_ADMIN_USERNAME"],
            "password": env["KC_BOOTSTRAP_ADMIN_PASSWORD"],
        },
    )
    token: str = response.raise_for_status().json()["access_token"]
    return token


@pytest.mark.e2e
@pytest.mark.parametrize("realm", HOMES)
def test_default_keys_survive(realm: str, dotenv: dict[str, str]) -> None:
    response = httpx2.get(
        f"{KEYCLOAK}/admin/realms/{realm}/keys",
        headers={"Authorization": f"Bearer {admin_token(dotenv)}"},
    )
    active = {
        k["algorithm"]
        for k in response.raise_for_status().json()["keys"]
        if k["status"] == "ACTIVE"
    }
    assert {"RS256", "RSA-OAEP", "HS512", "AES"} <= active, (
        f"{realm}: active key algorithms are {sorted(active)}"
    )
