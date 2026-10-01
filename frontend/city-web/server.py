"""Fairfield city-web MCP server: read-only access to two public City sites.

Allowed sites (nothing else, enforced here AND by the `webproxy` Squid allowlist):
  - www.fairfield.ca.gov               City website (Granicus, behind Akamai)
  - pub-fairfield.escribemeetings.com  Agendas and minutes (eScribe)

Read-only: GET only, plus the one eScribe search endpoint (a POST that only
reads). Every request is written to the audit log with the LibreChat user, the
tool, the exact URL or search text, and the outcome.

All traffic goes through the HTTPS proxy in $HTTPS_PROXY. This container has
no other route off the Docker host.
"""

from __future__ import annotations

import io
import json
import os
import re
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Annotated
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import Field
from pypdf import PdfReader

CITY_SITE = "www.fairfield.ca.gov"
ESCRIBE = "pub-fairfield.escribemeetings.com"
ALLOWED_HOSTS = frozenset({CITY_SITE, ESCRIBE})
ESCRIBE_SEARCH_PATH = "/GetSearchData.asmx/GetSearchMeetingData"

# An honest, named client so TSS can ask Granicus/Akamai to allowlist it.
USER_AGENT = os.environ.get(
    "CITY_WEB_USER_AGENT",
    "FairfieldAIAssistant/1.0 (City of Fairfield TSS; read-only)",
)
PROXY = os.environ.get("HTTPS_PROXY")  # required; see main()
AUDIT_LOG = os.environ.get("CITY_WEB_AUDIT_LOG", "/logs/audit.jsonl")
MAX_BYTES = 100 * 1024 * 1024  # agenda packages can be large PDFs
MAX_REDIRECTS = 5
MAX_QUERY_CHARS = 200
PAGE_CHARS = 12_000  # text returned per read call
DOC_CACHE_SIZE = 8

_audit_lock = threading.Lock()


class Blocked(Exception):
    """The request is not allowed by policy (never sent)."""


def _audit(ctx: Context | None, tool: str, **fields) -> None:
    user = None
    try:
        user = (ctx.headers or {}).get("x-librechat-user") if ctx is not None else None
    except Exception:
        pass
    rec = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "user": user, "tool": tool, **fields}
    line = json.dumps(rec, ensure_ascii=False)
    print(line, flush=True)
    with _audit_lock, open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _check_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme != "https":
        raise Blocked("only https:// URLs are allowed")
    if parts.username or parts.password or parts.port not in (None, 443):
        raise Blocked("URLs with credentials or non-standard ports are not allowed")
    host = (parts.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise Blocked(f"{host or 'that host'} is not an approved site (allowed: {', '.join(sorted(ALLOWED_HOSTS))})")
    return parts.geturl()


def _client() -> httpx.Client:
    return httpx.Client(
        proxy=PROXY,
        timeout=httpx.Timeout(60.0, connect=15.0),
        follow_redirects=False,  # each hop is re-checked against the allowlist
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
    )


def _fetch(url: str, *, method: str = "GET", data: dict | None = None) -> tuple[str, str, bytes]:
    """Return (final_url, content_type, body). Raises Blocked or httpx errors."""
    url = _check_url(url)
    if method != "GET" and not (urlsplit(url).hostname == ESCRIBE and urlsplit(url).path == ESCRIBE_SEARCH_PATH):
        raise Blocked("read-only: only GET is allowed (plus the eScribe search endpoint)")
    with _client() as c:
        for _ in range(MAX_REDIRECTS + 1):
            with c.stream(method, url, data=data) as r:
                if r.is_redirect:
                    url = _check_url(urljoin(url, r.headers.get("location", "")))
                    method, data = "GET", None
                    continue
                # Bot protection is respected, never worked around: report it so TSS can get
                # the assistant allowlisted by the site's operator.
                if r.status_code in (403, 503):
                    operator = "Granicus (Akamai)" if urlsplit(url).hostname == CITY_SITE else "eScribe (Cloudflare)"
                    raise PermissionError(
                        f"{urlsplit(url).hostname} refused this request (HTTP {r.status_code}, bot protection by "
                        f"{operator}). The assistant does not work around bot protection. TSS can ask {operator} "
                        f"to allowlist the Fairfield AI Assistant (User-Agent '{USER_AGENT}'). Until then, give the "
                        f"user the link to open in their own browser: {url}"
                    )
                r.raise_for_status()
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf += chunk
                    if len(buf) > MAX_BYTES:
                        raise Blocked(f"document is larger than {MAX_BYTES // (1024 * 1024)} MB")
                return url, r.headers.get("content-type", ""), bytes(buf)
    raise Blocked("too many redirects")


def _clean(text: str) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _html_text(body: bytes) -> tuple[str, str]:
    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "nav", "footer", "header"]):
        tag.decompose()
    title = _clean(soup.title.get_text()) if soup.title else ""
    return title, _clean(soup.get_text("\n"))


class _Doc:
    def __init__(self, url: str, kind: str, title: str, pages: list[str]):
        self.url, self.kind, self.title, self.pages = url, kind, title, pages


_docs: OrderedDict[str, _Doc] = OrderedDict()
_docs_lock = threading.Lock()


def _load(url: str) -> _Doc:
    url = _check_url(url)
    with _docs_lock:
        if url in _docs:
            _docs.move_to_end(url)
            return _docs[url]
    final, ctype, body = _fetch(url)
    if "pdf" in ctype or body[:5] == b"%PDF-":
        reader = PdfReader(io.BytesIO(body))
        pages = [_clean(p.extract_text() or "") for p in reader.pages]
        doc = _Doc(final, "pdf", (reader.metadata or {}).get("/Title", "") or "", pages)
    else:
        title, text = _html_text(body)
        # Split long HTML into PAGE_CHARS "pages" so it can be read in parts.
        pages = [text[i : i + PAGE_CHARS] for i in range(0, max(len(text), 1), PAGE_CHARS)]
        doc = _Doc(final, "html", title, pages)
    with _docs_lock:
        _docs[url] = doc
        while len(_docs) > DOC_CACHE_SIZE:
            _docs.popitem(last=False)
    return doc


def _guard(ctx: Context | None, tool: str, target: str, fn):
    t0 = time.monotonic()
    try:
        out = fn()
        _audit(ctx, tool, target=target, outcome="ok", ms=int((time.monotonic() - t0) * 1000))
        return out
    except Blocked as e:
        _audit(ctx, tool, target=target, outcome="blocked", reason=str(e))
        return f"Not allowed: {e}"
    except PermissionError as e:
        _audit(ctx, tool, target=target, outcome="refused-by-site", reason=str(e))
        return str(e)
    except httpx.HTTPStatusError as e:
        _audit(ctx, tool, target=target, outcome="http-error", status=e.response.status_code)
        return f"The site returned HTTP {e.response.status_code} for {target}."
    except Exception as e:  # network errors, bad PDFs
        _audit(ctx, tool, target=target, outcome="error", reason=f"{type(e).__name__}: {e}"[:300])
        return f"Could not read {target}: {type(e).__name__}."


mcp = MCPServer(
    "city-web",
    instructions=(
        "Read-only access to two public City of Fairfield websites: www.fairfield.ca.gov and the "
        "agendas/minutes portal pub-fairfield.escribemeetings.com. Use search_meeting_documents to find "
        "agendas, minutes and agenda items; then find_in_document or read_city_page to read them. "
        "Cite the URL for every fact. Never put names, personal details or other confidential "
        "information into a search: searches are sent to these public websites."
    ),
)


@mcp.tool()
def search_meeting_documents(
    ctx: Context,
    query: Annotated[str, Field(description='Words to search for, e.g. "Measure P". Quote a phrase for an exact match.')],
    max_results: Annotated[int, Field(ge=1, le=50)] = 20,
) -> str:
    """Search City of Fairfield meeting agendas, minutes and agenda items (City Council, commissions,
    committees) on the eScribe portal. Returns meetings with dates, document titles and links."""
    q = query.strip()[:MAX_QUERY_CHARS]

    def run() -> str:
        if not q:
            raise Blocked("empty search")
        form = {
            "sEcho": "1", "iColumns": "1", "iDisplayStart": "0", "iDisplayLength": str(max_results),
            "searchText": q, "filterbyMeetingTypeIds": "", "filterbyMeetingTypeNames": "", "filterByDate": "",
            "filterByMeetingDocumentTypes": "", "filterByExtensions": "", "filterByLanguage": "",
            "includeConflicts": "false", "includeComments": "false",
        }
        _, _, body = _fetch(f"https://{ESCRIBE}{ESCRIBE_SEARCH_PATH}", method="POST", data=form)
        data = json.loads(body)
        lines = [f'eScribe search for {q!r}: {data.get("iTotalRecords", 0)} matching documents/items '
                 f'(showing up to {max_results} meetings).']
        for row in data.get("aaData", []):
            soup = BeautifulSoup(row, "html.parser")
            head = soup.select_one("tr.srch-grp-row")
            cells = [_clean(td.get_text(" ")) for td in head.find_all("td")] if head else []
            lines.append(f"\n- {cells[0] if cells else '?'} — {cells[1] if len(cells) > 1 else '?'}")
            for a in soup.select(".srch-Title a[href]"):
                kind = a.find_parent("tr").find_all("td")[-1].get_text(" ", strip=True)
                lines.append(f"    • {_clean(a.get('title') or a.get_text(' '))} [{kind}] {urljoin(f'https://{ESCRIBE}/', a['href'])}")
        return "\n".join(lines)

    return _guard(ctx, "search_meeting_documents", q, run)


@mcp.tool()
def find_in_document(
    ctx: Context,
    url: Annotated[str, Field(description="https URL on www.fairfield.ca.gov or pub-fairfield.escribemeetings.com (PDF or web page)")],
    terms: Annotated[list[str], Field(description='Words or phrases to find, e.g. ["Measure P"]')],
    max_hits: Annotated[int, Field(ge=1, le=40)] = 15,
) -> str:
    """Find where words appear in a City document (agenda package PDF, minutes, or web page).
    Returns each match with its page number and surrounding text. Best first step for long PDFs."""

    def run() -> str:
        doc = _load(url)
        pats = [re.compile(re.escape(t.strip()), re.I) for t in terms if t.strip()][:10]
        if not pats:
            raise Blocked("no search terms")
        hits = []
        for n, text in enumerate(doc.pages, 1):
            for p in pats:
                for m in p.finditer(text):
                    s, e = max(0, m.start() - 400), min(len(text), m.end() + 400)
                    hits.append(f"[page {n}] …{text[s:e]}…")
                    if len(hits) >= max_hits:
                        break
                if len(hits) >= max_hits:
                    break
            if len(hits) >= max_hits:
                break
        head = f"{doc.url} ({doc.kind}, {len(doc.pages)} pages{', ' + doc.title if doc.title else ''})"
        if not hits:
            return f"{head}\nNo matches for {terms}."
        return f"{head}\n{len(hits)} match(es) for {terms} (max {max_hits}):\n\n" + "\n\n".join(hits)

    return _guard(ctx, "find_in_document", url, run)


@mcp.tool()
def read_city_page(
    ctx: Context,
    url: Annotated[str, Field(description="https URL on www.fairfield.ca.gov or pub-fairfield.escribemeetings.com")],
    page: Annotated[int, Field(ge=1, description="Page of the document to read (PDF page, or part of a long web page)")] = 1,
    pages: Annotated[int, Field(ge=1, le=5, description="How many consecutive pages to return")] = 1,
) -> str:
    """Read the text of a City web page or document (PDF), a few pages at a time."""

    def run() -> str:
        doc = _load(url)
        last = min(len(doc.pages), page + pages - 1)
        if page > len(doc.pages):
            return f"{doc.url} has only {len(doc.pages)} page(s)."
        body = "\n\n".join(f"--- page {n} ---\n{doc.pages[n - 1][:PAGE_CHARS]}" for n in range(page, last + 1))
        more = f" Next: page={last + 1}." if last < len(doc.pages) else ""
        return f"{doc.url} ({doc.kind}, pages {page}-{last} of {len(doc.pages)}{', ' + doc.title if doc.title else ''}).{more}\n\n{body}"

    return _guard(ctx, "read_city_page", f"{url} p{page}+{pages}", run)


def main() -> None:
    if not PROXY:
        raise SystemExit("HTTPS_PROXY must be set: city-web only reaches the internet through the allowlisting proxy")
    os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8000,
        stateless_http=True,
        json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["city-web:8000", "city-web"],
            allowed_origins=[],
        ),
    )


if __name__ == "__main__":
    main()
