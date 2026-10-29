"""home-fau as SAML IdP (docs/specs/2026-10-29-home-fau-saml-idp).

Static checks on `home-fau.json`, each with negatives on a synthetic realm, then live
checks on a scripted SP-initiated login as alice (`e2e`).
"""

import copy
import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import httpx2
import pytest

from tests.conftest import KEYCLOAK, admin_token
from tests.saml import (
    EXC_C14N,
    SAML,
    SAMLP,
    authn_request,
    browser,
    login,
    saml_response,
    signature_problems,
)

ROOT = Path(__file__).resolve().parent.parent
REALM_FILE = ROOT / "keycloak/realms/home-fau.json"

SP_ENTITY_ID = "http://auth.localhost:8080/realms/aloysius"
ACS = f"{SP_ENTITY_ID}/broker/home-fau/endpoint"

# eduPerson and SCHAC OIDs, sent with NameFormat uri (SAML2 Core 8.2.2).
MAPPERS = {
    "eduPersonPrincipalName": ("urn:oid:1.3.6.1.4.1.5923.1.1.1.6", "false"),
    "eduPersonScopedAffiliation": ("urn:oid:1.3.6.1.4.1.5923.1.1.1.9", "true"),
    "schacHomeOrganization": ("urn:oid:1.3.6.1.4.1.25178.1.2.9", "false"),
}
MULTIVALUED = {"eduPersonScopedAffiliation"}

# Client attributes that must hold exactly these values.
CLIENT_ATTRIBUTES = {
    "saml_assertion_consumer_url_post": ACS,
    "saml.force.post.binding": "true",
    "saml.server.signature": "true",  # the Response
    "saml.assertion.signature": "true",  # the Assertion (SAML2 Profiles 4.1.3.5)
    "saml.signature.algorithm": "RSA_SHA256",
    "saml_signature_canonicalization_method": EXC_C14N,
    "saml.client.signature": "false",  # AuthnRequests stay unsigned
    "saml.encrypt": "false",
    "saml_name_id_format": "persistent",  # SAML2 Core 8.3.7
    "saml_force_name_id_format": "true",
}


def client_problems(realm: dict[str, Any]) -> list[str]:
    """Why `realm` doesn't serve exactly the aloysius SP with the spec's settings."""
    clients = [c for c in realm.get("clients", []) if c.get("protocol") == "saml"]
    if [c.get("clientId") for c in clients] != [SP_ENTITY_ID]:
        return [f"want exactly one SAML client {SP_ENTITY_ID}"]
    client = clients[0]
    problems = []
    if client.get("redirectUris") != [ACS]:
        problems.append("redirectUris must be exactly [ACS]")
    attributes = client.get("attributes", {})
    for name, want in CLIENT_ATTRIBUTES.items():
        if attributes.get(name) != want:
            problems.append(f"{name} must be {want}")
    if "saml_assertion_consumer_url_redirect" in attributes:
        problems.append("saml_assertion_consumer_url_redirect must be unset")
    for scopes in ("defaultClientScopes", "optionalClientScopes"):
        if client.get(scopes) != []:
            problems.append(f"{scopes} must be []")
    if client.get("fullScopeAllowed") is not False:
        problems.append("fullScopeAllowed must be false")
    return problems


def mapper_problems(client: dict[str, Any]) -> list[str]:
    """Why the client's mappers aren't exactly the three urn:oid attributes."""
    mappers = {m.get("name"): m for m in client.get("protocolMappers", [])}
    problems = []
    if sorted(mappers) != sorted(MAPPERS):
        problems.append(f"want mappers {sorted(MAPPERS)}, found {sorted(mappers)}")
    for name, (oid, aggregate) in MAPPERS.items():
        if name not in mappers:
            continue
        want = {
            "user.attribute": name,
            "attribute.name": oid,
            "attribute.nameformat": "URI Reference",
            "friendly.name": name,
            "aggregate.attrs": aggregate,
        }
        mapper = mappers[name]
        if mapper.get("protocolMapper") != "saml-user-attribute-mapper":
            problems.append(f"{name} must be a saml-user-attribute-mapper")
        for key, value in want.items():
            if mapper.get("config", {}).get(key) != value:
                problems.append(f"{name} {key} must be {value}")
    return problems


def profile_problems(realm: dict[str, Any], client: dict[str, Any]) -> list[str]:
    """Why a mapped attribute isn't declared, admin-only, in the user profile."""
    # config-cli applies `userProfile` only with this flag (tasks.md, task 1).
    problems = []
    if realm.get("attributes", {}).get("userProfileEnabled") != "true":
        problems.append("attributes.userProfileEnabled must be true")
    profile = realm.get("userProfile", {}).get("attributes", [])
    declared = {a["name"]: a for a in profile}
    for mapper in client.get("protocolMappers", []):
        name = mapper.get("config", {}).get("user.attribute")
        if name not in declared:
            problems.append(f"{name} is not declared in the user profile")
            continue
        permissions = declared[name].get("permissions", {})
        if permissions.get("edit") != ["admin"] or permissions.get("view") != ["admin"]:
            problems.append(f"{name} must be viewable and editable by admin only")
        if declared[name].get("multivalued", False) != (name in MULTIVALUED):
            problems.append(f"{name} multivalued must be {name in MULTIVALUED}")
    return problems


def user_problems(realm: dict[str, Any]) -> list[str]:
    """Why demo users don't take their password from `.env`."""
    users = realm.get("users", [])
    if not users:
        return ["no users"]
    want = [
        {"type": "password", "value": "$(env:DEMO_USER_PASSWORD)", "temporary": False}
    ]
    return [
        f"{u.get('username')} password must be $(env:DEMO_USER_PASSWORD)"
        for u in users
        if u.get("credentials") != want
    ]


def realm_problems(realm: dict[str, Any]) -> list[str]:
    problems = client_problems(realm) + user_problems(realm)
    for client in realm.get("clients", []):
        if client.get("clientId") == SP_ENTITY_ID:
            problems += mapper_problems(client) + profile_problems(realm, client)
    return problems


def good_realm() -> dict[str, Any]:
    """A minimal realm that meets the spec, for negatives to break."""
    return {
        "attributes": {"userProfileEnabled": "true"},
        "userProfile": {
            "attributes": [
                {
                    "name": name,
                    "permissions": {"view": ["admin"], "edit": ["admin"]},
                    "multivalued": name in MULTIVALUED,
                }
                for name in MAPPERS
            ]
        },
        "clients": [
            {
                "clientId": SP_ENTITY_ID,
                "protocol": "saml",
                "fullScopeAllowed": False,
                "redirectUris": [ACS],
                "defaultClientScopes": [],
                "optionalClientScopes": [],
                "attributes": dict(CLIENT_ATTRIBUTES),
                "protocolMappers": [
                    {
                        "name": name,
                        "protocol": "saml",
                        "protocolMapper": "saml-user-attribute-mapper",
                        "config": {
                            "user.attribute": name,
                            "attribute.name": oid,
                            "attribute.nameformat": "URI Reference",
                            "friendly.name": name,
                            "aggregate.attrs": aggregate,
                        },
                    }
                    for name, (oid, aggregate) in MAPPERS.items()
                ],
            }
        ],
        "users": [
            {
                "username": "alice",
                "credentials": [
                    {
                        "type": "password",
                        "value": "$(env:DEMO_USER_PASSWORD)",
                        "temporary": False,
                    }
                ],
            }
        ],
    }


def client(realm: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = realm["clients"][0]
    return result


def mapper(realm: dict[str, Any], name: str) -> dict[str, Any]:
    result: dict[str, Any] = next(
        m for m in client(realm)["protocolMappers"] if m["name"] == name
    )
    return result


def profile_attribute(realm: dict[str, Any], name: str) -> dict[str, Any]:
    result: dict[str, Any] = next(
        a for a in realm["userProfile"]["attributes"] if a["name"] == name
    )
    return result


def test_realm_problems_none_for_good_realm() -> None:
    assert realm_problems(good_realm()) == []


def test_wildcard_acs() -> None:
    realm = good_realm()
    client(realm)["redirectUris"] = [f"{SP_ENTITY_ID}/*"]
    assert realm_problems(realm) == ["redirectUris must be exactly [ACS]"]


def test_second_redirect_uri() -> None:
    realm = good_realm()
    client(realm)["redirectUris"].append("http://evil.example/acs")
    assert realm_problems(realm) == ["redirectUris must be exactly [ACS]"]


def test_assertion_signing_off() -> None:
    realm = good_realm()
    client(realm)["attributes"]["saml.assertion.signature"] = "false"
    assert realm_problems(realm) == ["saml.assertion.signature must be true"]


def test_client_signature_on() -> None:
    realm = good_realm()
    client(realm)["attributes"]["saml.client.signature"] = "true"
    assert realm_problems(realm) == ["saml.client.signature must be false"]


def test_transient_name_id() -> None:
    realm = good_realm()
    client(realm)["attributes"]["saml_name_id_format"] = "transient"
    assert realm_problems(realm) == ["saml_name_id_format must be persistent"]


def test_unknown_sp() -> None:
    realm = good_realm()
    client(realm)["clientId"] = "http://other.example/sp"
    assert realm_problems(realm)[0] == f"want exactly one SAML client {SP_ENTITY_ID}"


def test_default_client_scope() -> None:
    realm = good_realm()
    client(realm)["defaultClientScopes"] = ["role_list"]
    assert realm_problems(realm) == ["defaultClientScopes must be []"]


def test_mapper_basic_name_format() -> None:
    realm = good_realm()
    mapper(realm, "eduPersonPrincipalName")["config"]["attribute.nameformat"] = "Basic"
    assert realm_problems(realm) == [
        "eduPersonPrincipalName attribute.nameformat must be URI Reference"
    ]


def test_mapper_wrong_oid() -> None:
    realm = good_realm()
    config = mapper(realm, "schacHomeOrganization")["config"]
    config["attribute.name"] = "urn:oid:1.3.6.1.4.1.5923.1.1.1.6"
    assert realm_problems(realm) == [
        "schacHomeOrganization attribute.name must be urn:oid:1.3.6.1.4.1.25178.1.2.9"
    ]


def test_extra_mapper() -> None:
    realm = good_realm()
    extra = copy.deepcopy(mapper(realm, "schacHomeOrganization"))
    extra["name"] = "mail"
    extra["config"]["user.attribute"] = "email"
    client(realm)["protocolMappers"].append(extra)
    assert realm_problems(realm)[0].startswith("want mappers")


def test_mapped_attribute_not_declared() -> None:
    realm = good_realm()
    realm["userProfile"]["attributes"] = [
        a
        for a in realm["userProfile"]["attributes"]
        if a["name"] != "schacHomeOrganization"
    ]
    assert realm_problems(realm) == [
        "schacHomeOrganization is not declared in the user profile"
    ]


def test_user_editable_attribute() -> None:
    realm = good_realm()
    profile_attribute(realm, "eduPersonScopedAffiliation")["permissions"]["edit"] = [
        "admin",
        "user",
    ]
    assert realm_problems(realm) == [
        "eduPersonScopedAffiliation must be viewable and editable by admin only"
    ]


def test_affiliation_not_multivalued() -> None:
    realm = good_realm()
    profile_attribute(realm, "eduPersonScopedAffiliation")["multivalued"] = False
    assert realm_problems(realm) == [
        "eduPersonScopedAffiliation multivalued must be True"
    ]


def test_user_profile_flag_missing() -> None:
    realm = good_realm()
    del realm["attributes"]
    assert realm_problems(realm) == ["attributes.userProfileEnabled must be true"]


def test_literal_password() -> None:
    realm = good_realm()
    realm["users"][0]["credentials"][0]["value"] = "alice"
    assert realm_problems(realm) == ["alice password must be $(env:DEMO_USER_PASSWORD)"]


def test_home_fau_realm_file() -> None:
    problems = realm_problems(json.loads(REALM_FILE.read_text()))
    assert not problems, "home-fau.json: " + "; ".join(problems)


ALICE = {
    "eduPersonPrincipalName": ["alice@fau.de"],
    "eduPersonScopedAffiliation": ["member@fau.de", "staff@fau.de"],
    "schacHomeOrganization": ["fau.de"],
}


def test_alice_attributes() -> None:
    realm = json.loads(REALM_FILE.read_text())
    alice = next(u for u in realm["users"] if u["username"] == "alice")
    assert alice["attributes"] == ALICE


# Live checks (e2e): SAML2 Bindings 3.4 in, 3.5 out.
SSO = f"{KEYCLOAK}/realms/home-fau/protocol/saml"
IDP_ENTITY_ID = f"{KEYCLOAK}/realms/home-fau"
PERSISTENT = "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent"
URI_FORMAT = "urn:oasis:names:tc:SAML:2.0:attrname-format:uri"
SUCCESS = "urn:oasis:names:tc:SAML:2.0:status:Success"


def alice_login(
    password: str, issuer: str = SP_ENTITY_ID, acs: str = ACS
) -> tuple[str, httpx2.Response]:
    """A fresh browser's login as alice; returns the request ID and the last page."""
    request_id = f"_{uuid.uuid4().hex}"
    with browser() as client:
        page = login(
            client,
            SSO,
            authn_request(request_id, issuer, acs, SSO),
            "alice",
            password,
        )
    return request_id, page


def assertion_of(response: ET.Element) -> ET.Element:
    assertion = response.find(f"{{{SAML}}}Assertion")
    assert assertion is not None, "Response has no plain Assertion"
    return assertion


def attributes(assertion: ET.Element) -> dict[str, tuple[str | None, list[str]]]:
    """Attribute Name to (NameFormat, values) (SAML2 Core 2.7.3.1)."""
    return {
        a.get("Name", ""): (
            a.get("NameFormat"),
            [v.text or "" for v in a.iter(f"{{{SAML}}}AttributeValue")],
        )
        for a in assertion.iter(f"{{{SAML}}}Attribute")
    }


def name_id(assertion: ET.Element) -> ET.Element:
    element = assertion.find(f"{{{SAML}}}Subject/{{{SAML}}}NameID")
    assert element is not None, "Assertion has no NameID"
    return element


@pytest.fixture
def alice_response(dotenv: dict[str, str]) -> tuple[str, str, ET.Element]:
    request_id, page = alice_login(dotenv["DEMO_USER_PASSWORD"])
    result = saml_response(page)
    assert result is not None, f"no SAMLResponse (HTTP {page.status_code})"
    action, response = result
    return request_id, action, response


@pytest.mark.e2e
def test_response_goes_to_acs(alice_response: tuple[str, str, ET.Element]) -> None:
    # SAML2 Core 3.2.2: Destination, InResponseTo and StatusCode.
    request_id, action, response = alice_response
    assert action == ACS
    assert response.get("Destination") == ACS
    assert response.get("InResponseTo") == request_id
    status = response.find(f"{{{SAMLP}}}Status/{{{SAMLP}}}StatusCode")
    assert status is not None and status.get("Value") == SUCCESS


@pytest.mark.e2e
def test_assertion_audience_and_issuer(
    alice_response: tuple[str, str, ET.Element],
) -> None:
    assertion = assertion_of(alice_response[2])
    # SAML2 Core 2.5.1.4: the assertion is only for the aloysius SP.
    audiences = [a.text for a in assertion.iter(f"{{{SAML}}}Audience")]
    assert audiences == [SP_ENTITY_ID]
    assert assertion.findtext(f"{{{SAML}}}Issuer") == IDP_ENTITY_ID


@pytest.mark.e2e
def test_name_id_is_persistent_and_stable(
    alice_response: tuple[str, str, ET.Element], dotenv: dict[str, str]
) -> None:
    # SAML2 Core 8.3.7: opaque, and the same on every login to this SP.
    first = name_id(assertion_of(alice_response[2]))
    assert first.get("Format") == PERSISTENT
    assert first.text not in (None, "alice", "alice@fau.de")
    again = saml_response(alice_login(dotenv["DEMO_USER_PASSWORD"])[1])
    assert again is not None
    assert name_id(assertion_of(again[1])).text == first.text


@pytest.mark.e2e
def test_exactly_the_three_oid_attributes(
    alice_response: tuple[str, str, ET.Element],
) -> None:
    # SAML2 Core 8.2.2: NameFormat uri; ePSA is one Attribute with two values.
    assert attributes(assertion_of(alice_response[2])) == {
        MAPPERS[name][0]: (URI_FORMAT, values) for name, values in ALICE.items()
    }


@pytest.mark.e2e
def test_response_and_assertion_signed(
    alice_response: tuple[str, str, ET.Element], dotenv: dict[str, str]
) -> None:
    response = alice_response[2]
    cert = dotenv["HOME_FAU_SAML_CERT"]
    assert signature_problems(response, cert) == [], "Response"
    assert signature_problems(assertion_of(response), cert) == [], "Assertion"


@pytest.mark.e2e
def test_unknown_issuer_gets_no_response(dotenv: dict[str, str]) -> None:
    # SAML2 Core 3.4.1: the IdP serves only SPs it knows.
    _, page = alice_login(
        dotenv["DEMO_USER_PASSWORD"], issuer="http://unknown.example/sp"
    )
    assert saml_response(page) is None
    assert page.status_code == 400


@pytest.mark.e2e
def test_other_acs_gets_no_response(dotenv: dict[str, str]) -> None:
    # SAML2 Core 3.4.1: AssertionConsumerServiceURL must be a registered ACS.
    _, page = alice_login(dotenv["DEMO_USER_PASSWORD"], acs="http://evil.example/acs")
    assert saml_response(page) is None
    assert page.status_code == 400


@pytest.mark.e2e
def test_wrong_password_gets_login_form_again() -> None:
    _, page = alice_login("wrong-password")
    assert saml_response(page) is None
    assert 'name="password"' in page.text


def admin(env: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token(env)}"}


def alice_record(headers: dict[str, str]) -> dict[str, Any]:
    users = httpx2.get(
        f"{KEYCLOAK}/admin/realms/home-fau/users",
        params={"username": "alice", "exact": "true"},
        headers=headers,
    ).raise_for_status()
    record: dict[str, Any] = users.json()[0]
    return record


@pytest.mark.e2e
def test_profile_declares_admin_only_attributes(dotenv: dict[str, str]) -> None:
    profile = httpx2.get(
        f"{KEYCLOAK}/admin/realms/home-fau/users/profile", headers=admin(dotenv)
    ).raise_for_status()
    declared = {a["name"]: a for a in profile.json()["attributes"]}
    for name in MAPPERS:
        assert declared[name]["permissions"] == {"view": ["admin"], "edit": ["admin"]}
    assert profile.json().get("unmanagedAttributePolicy") is None


@pytest.mark.e2e
def test_alice_record_holds_attributes(dotenv: dict[str, str]) -> None:
    assert alice_record(admin(dotenv))["attributes"] == ALICE


@pytest.mark.e2e
def test_undeclared_attribute_is_dropped(dotenv: dict[str, str]) -> None:
    headers = admin(dotenv)
    record = alice_record(headers)
    record["attributes"] = {**record["attributes"], "foo": ["bar"]}
    httpx2.put(
        f"{KEYCLOAK}/admin/realms/home-fau/users/{record['id']}",
        json=record,
        headers=headers,
    ).raise_for_status()
    assert alice_record(headers)["attributes"] == ALICE
