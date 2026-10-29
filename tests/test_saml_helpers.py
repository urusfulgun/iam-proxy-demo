"""Unit tests for tests/saml.py (docs/specs/2026-10-29-home-fau-saml-idp)."""

import base64
import zlib
from urllib.parse import parse_qs

from tests.saml import (
    DS,
    EXC_C14N,
    RSA_SHA256,
    authn_request,
    parse_form,
    parse_xml,
    redirect_query,
    signature_problems,
)

CERT = "MIIBcert"
ID = "ID_assertion"


def signature(ref: str = f"#{ID}", method: str = RSA_SHA256, cert: str = CERT) -> str:
    return (
        f'<ds:Signature xmlns:ds="{DS}"><ds:SignedInfo>'
        f'<ds:CanonicalizationMethod Algorithm="{EXC_C14N}"/>'
        f'<ds:SignatureMethod Algorithm="{method}"/>'
        f'<ds:Reference URI="{ref}"/></ds:SignedInfo>'
        f"<ds:KeyInfo><ds:X509Data><ds:X509Certificate>{cert}"
        "</ds:X509Certificate></ds:X509Data></ds:KeyInfo></ds:Signature>"
    )


def assertion(sig: str) -> str:
    return (
        '<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" '
        f'ID="{ID}">{sig}</saml:Assertion>'
    )


def test_signature_problems_none_for_good_signature() -> None:
    assert signature_problems(parse_xml(assertion(signature())), CERT) == []


def test_signature_missing() -> None:
    assert signature_problems(parse_xml(assertion("")), CERT) == [
        "no enveloped ds:Signature"
    ]


def test_signature_references_other_id() -> None:
    element = parse_xml(assertion(signature(ref="#ID_other")))
    assert signature_problems(element, CERT) == ["Reference URI must be #ID_assertion"]


def test_signature_rsa_sha1() -> None:
    sha1 = "http://www.w3.org/2000/09/xmldsig#rsa-sha1"
    element = parse_xml(assertion(signature(method=sha1)))
    assert signature_problems(element, CERT) == ["SignatureMethod must be rsa-sha256"]


def test_signature_other_cert() -> None:
    element = parse_xml(assertion(signature(cert="MIIBother")))
    assert signature_problems(element, CERT) == ["KeyInfo cert is not the pinned cert"]


def test_redirect_query_round_trips() -> None:
    xml = authn_request("_id1", "http://sp", "http://sp/acs", "http://idp/sso")
    encoded = parse_qs(redirect_query(xml))["SAMLRequest"][0]
    # SAML2 Bindings 3.4.4.1: raw DEFLATE, then base64.
    assert zlib.decompress(base64.b64decode(encoded), -15).decode() == xml


def test_authn_request_fields() -> None:
    root = parse_xml(
        authn_request("_id1", "http://sp", "http://sp/acs", "http://idp/sso")
    )
    assert root.get("ID") == "_id1"
    assert root.get("AssertionConsumerServiceURL") == "http://sp/acs"
    assert root.get("Destination") == "http://idp/sso"


def test_parse_form_reads_action_and_hidden_inputs() -> None:
    page = (
        '<form name="x" method="post" action="http://sp/acs?a=1&amp;b=2">'
        '<input type="hidden" name="SAMLResponse" value="abc"/>'
        '<input type="hidden" name="RelayState" value=""/>'
        '<input type="submit" value="Go"/></form>'
    )
    assert parse_form(page) == (
        "http://sp/acs?a=1&b=2",
        {"SAMLResponse": "abc", "RelayState": ""},
    )


def test_parse_form_none_without_form() -> None:
    assert parse_form("<p>We are sorry...</p>") is None
