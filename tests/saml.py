"""SAML helpers for scripted logins (docs/specs/2026-10-29-home-fau-saml-idp).

Each SAML hop is an explicit step: build an AuthnRequest, send it over HTTP-Redirect,
submit the login form, then read the HTTP-POST form that carries the Response.
"""

import base64
import xml.etree.ElementTree as ET
import zlib
from datetime import UTC, datetime
from html.parser import HTMLParser
from http.cookiejar import Cookie, DefaultCookiePolicy
from urllib.parse import urlencode
from urllib.request import Request

import httpx2

SAMLP = "urn:oasis:names:tc:SAML:2.0:protocol"
SAML = "urn:oasis:names:tc:SAML:2.0:assertion"
DS = "http://www.w3.org/2000/09/xmldsig#"
EXC_C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"
RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
POST_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"


def authn_request(request_id: str, issuer: str, acs: str, destination: str) -> str:
    """An unsigned AuthnRequest for a Response over HTTP-POST (SAML2 Core 3.4.1)."""
    instant = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f'<samlp:AuthnRequest xmlns:samlp="{SAMLP}" xmlns:saml="{SAML}" '
        f'ID="{request_id}" Version="2.0" IssueInstant="{instant}" '
        f'Destination="{destination}" AssertionConsumerServiceURL="{acs}" '
        f'ProtocolBinding="{POST_BINDING}">'
        f"<saml:Issuer>{issuer}</saml:Issuer></samlp:AuthnRequest>"
    )


def redirect_query(xml: str) -> str:
    """Raw DEFLATE, base64, URL-encode (SAML2 Bindings 3.4.4.1)."""
    deflate = zlib.compressobj(wbits=-15)
    data = deflate.compress(xml.encode()) + deflate.flush()
    return urlencode({"SAMLRequest": base64.b64encode(data).decode()})


class _FormParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "form" and self.action is None:
            self.action = values.get("action") or ""
        elif tag == "input" and values.get("type") == "hidden" and values.get("name"):
            self.fields[values["name"] or ""] = values.get("value") or ""


def parse_form(page: str) -> tuple[str, dict[str, str]] | None:
    """The first form's action and hidden inputs, or None if the page has no form."""
    parser = _FormParser()
    parser.feed(page)
    return None if parser.action is None else (parser.action, parser.fields)


def parse_xml(xml: str) -> ET.Element:
    # Messages from our own Keycloak or built by the test, not untrusted input.
    return ET.fromstring(xml)  # noqa: S314


def signature_problems(element: ET.Element, cert: str) -> list[str]:
    """Why `element` isn't signed as the spec wants. Structural, not cryptographic."""
    # SAML2 Core 5.4.1: an enveloped signature is a direct child of the signed element.
    signature = element.find(f"{{{DS}}}Signature")
    if signature is None:
        return ["no enveloped ds:Signature"]
    problems = []
    # SAML2 Core 5.4.2: the Reference URI is "#" plus the signed element's ID.
    reference = signature.find(f"{{{DS}}}SignedInfo/{{{DS}}}Reference")
    want = f"#{element.get('ID')}"
    if reference is None or reference.get("URI") != want:
        problems.append(f"Reference URI must be {want}")
    method = signature.find(f"{{{DS}}}SignedInfo/{{{DS}}}SignatureMethod")
    if method is None or method.get("Algorithm") != RSA_SHA256:
        problems.append("SignatureMethod must be rsa-sha256")
    # SAML2 Core 5.4.3: exclusive canonicalization.
    c14n = signature.find(f"{{{DS}}}SignedInfo/{{{DS}}}CanonicalizationMethod")
    if c14n is None or c14n.get("Algorithm") != EXC_C14N:
        problems.append("CanonicalizationMethod must be exc-c14n")
    certs = [
        "".join((c.text or "").split())
        for c in signature.iter(f"{{{DS}}}X509Certificate")
    ]
    if certs != [cert]:
        problems.append("KeyInfo cert is not the pinned cert")
    return problems


class _LocalhostIsSecure(DefaultCookiePolicy):
    """Send `Secure` cookies to `*.localhost` over HTTP, as browsers do.

    Keycloak marks its login cookies `Secure` even on plain HTTP. Browsers treat
    localhost as a secure context (W3C Secure Contexts 3.1); Python's cookiejar doesn't.
    """

    def return_ok_secure(self, cookie: Cookie, request: Request) -> bool:
        host = request.host.split(":")[0]
        return (
            host == "localhost"
            or host.endswith(".localhost")
            or bool(super().return_ok_secure(cookie, request))
        )


def browser() -> httpx2.Client:
    """A fresh client with its own cookie jar, like a new browser profile."""
    client = httpx2.Client(follow_redirects=True)
    client.cookies.jar.set_policy(_LocalhostIsSecure())
    return client


def login(
    client: httpx2.Client,
    sso_url: str,
    request_xml: str,
    username: str,
    password: str,
) -> httpx2.Response:
    """Send the AuthnRequest, then submit the IdP's login form if it shows one."""
    page = client.get(f"{sso_url}?{redirect_query(request_xml)}")
    form = parse_form(page.text)
    if form is None or "SAMLResponse" in form[1]:
        return page
    action, fields = form
    return client.post(
        action, data={**fields, "username": username, "password": password}
    )


def saml_response(page: httpx2.Response) -> tuple[str, ET.Element] | None:
    """The HTTP-POST form's action and decoded Response (SAML2 Bindings 3.5.4)."""
    form = parse_form(page.text)
    if form is None or "SAMLResponse" not in form[1]:
        return None
    action, fields = form
    return action, parse_xml(base64.b64decode(fields["SAMLResponse"]).decode())
