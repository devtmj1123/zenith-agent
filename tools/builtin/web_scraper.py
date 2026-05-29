"""Free web scraper - no API key needed.
Replaces Firecrawl with httpx + BeautifulSoup + optional Playwright.
Returns clean markdown, extracts metadata, handles JS rendering.
Bot detection prevention: UA rotation, random delays, realistic headers.
"""
from __future__ import annotations
import asyncio
import random
import re
from typing import Optional

# User-Agent pool — rotate to avoid fingerprinting
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]


async def scrape(params: dict) -> dict:
    """Scrape URL to clean markdown. No API key needed.
    params: {url: str, render_js: bool (default False), max_length: int (default 10000)}
    """
    url = params.get("url")
    if not url:
        return {"success": False, "error": "Missing 'url' parameter"}

    render_js = params.get("render_js", False)
    max_length = params.get("max_length", 10000)

    # Try Playwright first if JS rendering requested
    if render_js:
        result = await _scrape_with_playwright(url, max_length)
        if result["success"]:
            return result
        # Fallback to httpx if Playwright fails

    return await _scrape_with_httpx(url, max_length)


async def _scrape_with_httpx(url: str, max_length: int) -> dict:
    """Scrape with httpx + BeautifulSoup (no JS rendering)."""
    try:
        import httpx
        from bs4 import BeautifulSoup, Tag
    except ImportError:
        return {"success": False, "error": "httpx or bs4 not installed. Run: pip install httpx beautifulsoup4"}

    try:
        # Random delay to appear human (0.5-2s)
        await asyncio.sleep(random.uniform(0.5, 2.0))

        ua = random.choice(_USER_AGENTS)
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            # Retry with different UA on bot detection
            if resp.status_code in (403, 429):
                await asyncio.sleep(random.uniform(2.0, 5.0))
                headers["User-Agent"] = random.choice(_USER_AGENTS)
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as retry_client:
                    resp = await retry_client.get(url)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract metadata
        metadata = _extract_metadata(soup, url)

        # Extract main content
        content = _extract_content(soup)

        # Convert to markdown
        markdown = _html_to_markdown(content)

        # Truncate
        if len(markdown) > max_length:
            markdown = markdown[:max_length] + "\n\n[Content truncated...]"

        return {
            "success": True,
            "data": {
                "url": url,
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "author": metadata.get("author", ""),
                "published": metadata.get("published", ""),
                "markdown": markdown,
                "length": len(markdown),
                "rendered_with": "httpx",
            },
        }
    except Exception as e:
        return {"success": False, "error": f"Scrape failed: {str(e)}"}


async def _scrape_with_playwright(url: str, max_length: int) -> dict:
    """Scrape with Playwright (handles JS-rendered pages)."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"success": False, "error": "playwright not installed. Run: pip install playwright && playwright install chromium"}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for content to load
            await page.wait_for_timeout(2000)

            html = await page.content()
            title = await page.title()
            await browser.close()

        soup = __import__("bs4").BeautifulSoup(html, "html.parser")
        metadata = _extract_metadata(soup, url)
        metadata["title"] = title or metadata.get("title", "")

        content = _extract_content(soup)
        markdown = _html_to_markdown(content)

        if len(markdown) > max_length:
            markdown = markdown[:max_length] + "\n\n[Content truncated...]"

        return {
            "success": True,
            "data": {
                "url": url,
                "title": metadata.get("title", ""),
                "description": metadata.get("description", ""),
                "author": metadata.get("author", ""),
                "published": metadata.get("published", ""),
                "markdown": markdown,
                "length": len(markdown),
                "rendered_with": "playwright",
            },
        }
    except Exception as e:
        return {"success": False, "error": f"Playwright scrape failed: {str(e)}"}


def _extract_metadata(soup, url: str) -> dict:
    """Extract metadata from HTML."""
    meta = {}

    # Title
    title_tag = soup.find("title")
    if title_tag:
        meta["title"] = title_tag.get_text(strip=True)

    # Meta tags
    for tag in soup.find_all("meta"):
        name = tag.get("name", "").lower()
        prop = tag.get("property", "").lower()
        content = tag.get("content", "")

        if name == "description" or prop == "og:description":
            meta["description"] = content
        elif name == "author":
            meta["author"] = content
        elif prop == "og:title" and "title" not in meta:
            meta["title"] = content
        elif prop == "article:published_time":
            meta["published"] = content
        elif name == "date":
            meta["published"] = content

    return meta


def _extract_content(soup) -> str:
    """Extract main content from HTML, removing boilerplate."""
    # Remove unwanted elements
    for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]):
        tag.decompose()

    # Try to find main content area
    main = (
        soup.find("article") or
        soup.find("main") or
        soup.find("div", {"role": "main"}) or
        soup.find("div", class_=re.compile(r"(content|article|post|entry|body)", re.I)) or
        soup.find("div", id=re.compile(r"(content|article|post|entry|body)", re.I))
    )

    if main:
        return str(main)
    return str(soup.body or soup)


def _html_to_markdown(html: str) -> str:
    """Convert HTML to clean markdown using block-based approach."""
    from bs4 import BeautifulSoup, NavigableString

    soup = BeautifulSoup(html, "html.parser")
    blocks = []

    def _inline_text(elem) -> str:
        """Extract text from an element, preserving inline formatting."""
        if isinstance(elem, NavigableString):
            return str(elem).strip()
        if not elem.name:
            return ""

        tag = elem.name.lower()
        text = "".join(_inline_text(c) for c in elem.children).strip()
        if not text:
            return ""

        if tag in ("strong", "b"):
            return f"**{text}**"
        if tag in ("em", "i"):
            return f"*{text}*"
        if tag == "code":
            return f"`{text}`"
        if tag == "a":
            href = elem.get("href", "")
            if href and href.startswith("http"):
                return f"[{text}]({href})"
            return text
        if tag == "br":
            return "\n"
        return text

    # Walk block-level elements
    for elem in soup.find_all(["h1","h2","h3","h4","h5","h6","p","li","pre","blockquote","table","div","section","article"]):
        tag = elem.name.lower()

        # Skip boilerplate containers
        if tag in ("nav", "footer", "header", "aside", "script", "style"):
            continue

        if tag in ("h1","h2","h3","h4","h5","h6"):
            level = int(tag[1])
            text = _inline_text(elem)
            if text:
                blocks.append(f"\n{'#' * level} {text}\n")
        elif tag == "pre":
            code = elem.get_text(strip=True)
            if code:
                blocks.append(f"\n```\n{code}\n```\n")
        elif tag == "blockquote":
            text = _inline_text(elem)
            if text:
                blocks.append(f"\n> {text}\n")
        elif tag == "li":
            text = _inline_text(elem)
            if text:
                blocks.append(f"- {text}")
        elif tag == "table":
            rows = []
            for tr in elem.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td","th"])]
                if cells:
                    rows.append("| " + " | ".join(cells) + " |")
            if rows:
                # Add header separator after first row
                if len(rows) > 1:
                    sep = "| " + " | ".join(["---"] * rows[0].count("|")) + " |"
                    rows.insert(1, sep)
                blocks.append("\n" + "\n".join(rows) + "\n")
        else:
            # p, div, section, article — extract as paragraph
            text = _inline_text(elem)
            if text and len(text) > 10:  # Skip tiny fragments
                blocks.append(f"\n{text}\n")

    markdown = "\n".join(blocks)

    # Clean up excessive newlines
    markdown = re.sub(r"\n{3,}", "\n\n", markdown)
    lines = [line.strip() for line in markdown.split("\n")]
    markdown = "\n".join(lines)

    return markdown.strip()
