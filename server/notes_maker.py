import os
import httpx
import asyncio
import markdownify
import readabilipy
from fastmcp import FastMCP
from dotenv import load_dotenv
from mcp import ErrorData, McpError
from pydantic import BaseModel, Field, AnyUrl
from mcp.server.auth.provider import AccessToken
from mcp.types import INVALID_PARAMS, INTERNAL_ERROR
from typing import Annotated, Optional, Literal, cast
from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair

load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN")
MY_NUMBER = os.environ.get("MY_NUMBER")

assert TOKEN is not None, "Please set AUTH_TOKEN in your .env file"
assert MY_NUMBER is not None, "Please set MY_NUMBER in your .env file"


class SimpleBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        k = RSAKeyPair.generate()
        super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
        self.token = token

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="puch-client",
                scopes=["*"],
                expires_at=None,
            )
        return None


class RichToolDescription(BaseModel):
    description: str
    use_when: str
    side_effects: str | None = None


USER_AGENT = "Puch/1.0 (Autonomous)"


def extract_content_from_html(html: str) -> str:
    """Extract and convert HTML content to Markdown format."""
    ret = readabilipy.simple_json.simple_json_from_html_string(
        html, use_readability=True)
    if not ret or not ret.get("content"):
        return "<error>Page failed to be simplified from HTML</error>"
    content = markdownify.markdownify(
        ret["content"], heading_style=markdownify.ATX)
    return content


mcp = FastMCP(
    "Notes Summarizer MCP Server",
    auth=SimpleBearerAuthProvider(TOKEN),
)


@mcp.tool
async def validate() -> str:
    return cast(str, MY_NUMBER)


class NotesMeta(BaseModel):
    title: Optional[str] = Field(default=None)
    byline: Optional[str] = Field(default=None)
    published_at: Optional[str] = Field(
        default=None, description="ISO-8601 publication date if available")
    canonical_url: Optional[str] = Field(default=None)
    reading_time_minutes: Optional[int] = Field(default=None)


class Citation(BaseModel):
    url: str
    title: Optional[str] = None
    fragment: Optional[str] = None


class FetchResult(BaseModel):
    meta: NotesMeta
    markdown: str
    links: list[str] = []


class SummarizeResult(BaseModel):
    meta: NotesMeta
    markdown: str
    key_points: list[str]
    citations: list[Citation]


async def _extract_url(url: str) -> FetchResult:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30)
        except httpx.HTTPError as e:
            raise McpError(ErrorData(code=INTERNAL_ERROR,
                           message=f"Failed to fetch {url}: {e!r}"))
        if resp.status_code >= 400:
            raise McpError(ErrorData(
                code=INTERNAL_ERROR, message=f"Failed to fetch {url} - status {resp.status_code}"))

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type:
        raise McpError(ErrorData(code=INVALID_PARAMS,
                       message=f"Unsupported content-type: {content_type}"))

    html = resp.text
    sj = readabilipy.simple_json.simple_json_from_html_string(
        html, use_readability=True)
    title = sj.get("title") if sj else None
    byline = sj.get("byline") if sj else None
    content_html = sj.get("content") if sj else None
    published = sj.get("date_published") if sj else None

    if not content_html:
        md = extract_content_from_html(html)
    else:
        md = markdownify.markdownify(
            content_html, heading_style=markdownify.ATX)

    links: list[str] = []
    try:
        from bs4 import BeautifulSoup
        from bs4.element import Tag as Bs4Tag

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            if isinstance(a, Bs4Tag):
                href = a.get("href")
                if isinstance(href, str) and href.startswith("http"):
                    links.append(href)
        links = list(dict.fromkeys(links))
    except Exception:
        links = []

    words = max(1, len(md.split()))
    reading_time = max(1, round(words / 200))

    meta = NotesMeta(
        title=title,
        byline=byline,
        published_at=published or None,
        canonical_url=str(resp.url),
        reading_time_minutes=reading_time,
    )
    result = FetchResult(meta=meta, markdown=md, links=links)
    return result


def _outline_from_markdown(md: str) -> list[str]:
    outline: list[str] = []
    for line in md.splitlines():
        if line.startswith("#"):
            outline.append(line.strip())
    if not outline:
        paras = [p.strip() for p in md.split("\n\n") if p.strip()]
        for i, p in enumerate(paras[:10], 1):
            first = p.split(". ")[0][:80]
            outline.append(f"- Section {i}: {first}…")
    return outline


def _summarize_markdown(md: str, length: Literal["short", "medium", "long"] = "medium") -> tuple[str, list[str]]:
    lines = [l.strip() for l in md.splitlines() if l.strip()]
    bullets: list[str] = []
    current_section = None
    for i, line in enumerate(lines):
        if line.startswith("#"):
            current_section = line.lstrip("# ")
            continue
        if current_section and len(bullets) < 20:
            sent = line.split(". ")[0]
            if sent:
                bullets.append(f"{current_section}: {sent.strip('. ')}.")
                current_section = None
    if not bullets:
        text = " ".join(lines)
        sentences = text.split(". ")
        bullets = [s.strip() + "." for s in sentences[:7] if s]

    n = {"short": 7, "medium": 15, "long": 30}[length]
    bullets = bullets[:n]
    md_summary = "\n".join(f"- {b}" for b in bullets)
    return md_summary, bullets


StructuredNotesDescription = RichToolDescription(
    description="Fetch a web page and return clean Markdown, metadata, and links.",
    use_when="The user provides a URL and wants readable notes or citations.",
)


@mcp.tool(description=StructuredNotesDescription.model_dump_json())
async def fetch_notes(
    url: Annotated[AnyUrl, Field(description="The URL to fetch and convert to Markdown")],
) -> str:
    res = await _extract_url(str(url))
    meta = res.meta
    header = [
        f"# {meta.title}" if meta.title else "# Page Notes",
        f"By: {meta.byline}" if meta.byline else None,
        f"Published: {meta.published_at}" if meta.published_at else None,
        f"Canonical: {meta.canonical_url}" if meta.canonical_url else None,
        f"Estimated reading time: {meta.reading_time_minutes} min" if meta.reading_time_minutes else None,
        "",
    ]
    header_md = "\n".join([h for h in header if h])
    links_md = "\n".join(f"- {l}" for l in res.links[:20])
    return (
        "Prepare the well structured notes that are easy to understandable from the below content."
        "Ensure concepts are clear and understandable, explain each concepts with ease."
        f"\n\n{header_md}\n\n"
        f"## Extracted Content\n\n{res.markdown}\n\n"
        f"## Links\n\n{links_md}"
    )


SummarizeUrlDescription = RichToolDescription(
    description="Summarize a URL into concise bullet points with citations.",
    use_when="The user wants a quick summary of a page with references.",
)


@mcp.tool(description=SummarizeUrlDescription.model_dump_json())
async def summarize_url(
    url: Annotated[AnyUrl, Field(description="The URL to summarize")],
    length: Annotated[Literal["short", "medium", "long"],
                      Field(description="Summary length")] = "medium",
) -> str:
    res = await _extract_url(str(url))
    summary_md, bullets = _summarize_markdown(res.markdown, length)
    citations = [f"[{i+1}] {res.meta.canonical_url}" for i in range(
        min(len(bullets), 5)) if res.meta.canonical_url]
    cite_md = "\n".join(citations)
    title = res.meta.title or "Summary"
    return (
        "prepare well-structured, easy-to-understand summary from the content below. "
        f"## {title}\n\n"
        f"## Key Points\n\n{summary_md}\n\n"
        f"## Citations\n\n{cite_md}\n\n"
    )


OutlineUrlDescription = RichToolDescription(
    description="Generate an outline (headings/sections) from a URL.",
    use_when="The user wants a structured outline for study or navigation.",
)


@mcp.tool(description=OutlineUrlDescription.model_dump_json())
async def outline_url(
    url: Annotated[AnyUrl, Field(description="The URL to outline")],
) -> str:
    res = await _extract_url(str(url))
    outline = _outline_from_markdown(res.markdown)
    outline_md = "\n".join(outline)

    return (
        "Create a study-friendly outline from the following structure. "
        "If headings are missing, the synthesized sections are provided.\n\n"
        f"## Outline\n\n{outline_md}\n\n"
    )


BatchSummarizeDescription = RichToolDescription(
    description="Summarize multiple URLs into a single study guide with citations.",
    use_when="The user provides many links and wants combined notes.",
)


@mcp.tool(description=BatchSummarizeDescription.model_dump_json())
async def batch_summarize(
    urls: Annotated[list[AnyUrl], Field(description="List of URLs to summarize")],
    length: Annotated[Literal["short", "medium", "long"], Field(
        description="Summary length for each")] = "medium",
) -> str:
    tasks = [_extract_url(str(u)) for u in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    sections: list[str] = []
    bibliography: list[str] = []
    for idx, r in enumerate(results, 1):
        if isinstance(r, BaseException):
            sections.append(f"## Source {idx}\n\n- Error: {r}")
            continue
        result: FetchResult = cast(FetchResult, r)
        summ_md, _ = _summarize_markdown(result.markdown, length)
        title = result.meta.title or f"Source {idx}"
        sections.append(f"## {title}\n\n{summ_md}")
        if result.meta.canonical_url:
            bibliography.append(
                f"[{idx}] {title} — {result.meta.canonical_url}")
    preface = (
        "Combine the following source summaries into a unified, easy-to-understand study guide. "
        "Avoid duplication, align terminology, and add brief transitions when needed."
    )
    return (
        f"{preface}\n\n# Study Guide\n\n" +
        "\n\n".join(sections) +
        ("\n\n## References\n\n" + "\n".join(bibliography) if bibliography else "")
    )


async def main():
    print("🚀 Starting MCP server on http://0.0.0.0:8086")
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8086)

if __name__ == "__main__":
    asyncio.run(main())
