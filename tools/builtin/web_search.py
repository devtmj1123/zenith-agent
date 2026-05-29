async def search(params: dict) -> dict:
    """Search the web using DuckDuckGo.
    params: {query: str, max_results: int (default 8), allowed_domains: list?, blocked_domains: list?}
    """
    query = params.get("query")
    if not query:
        return {"success": False, "error": "Missing 'query' parameter"}

    max_results = params.get("max_results", 8)
    allowed_domains = params.get("allowed_domains", [])
    blocked_domains = params.get("blocked_domains", [])

    try:
        from ddgs import DDGS
        import asyncio

        def _search():
            results = DDGS().text(query, max_results=max_results + 5)  # Fetch extra for filtering
            return results

        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _search)

        # Auto-filter: remove useless results + domain filtering
        formatted = []
        seen_urls = set()
        for r in results:
            title = r.get("title", "").strip()
            snippet = r.get("body", "").strip()
            url = r.get("href", "").strip()

            # Skip useless results
            if not title or not snippet or not url:
                continue
            if len(snippet) < 20:
                continue
            if url in seen_urls:
                continue

            # Domain filtering
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            if allowed_domains and not any(d in domain for d in allowed_domains):
                continue
            if blocked_domains and any(d in domain for d in blocked_domains):
                continue

            # Skip junk
            snippet_lower = snippet.lower()
            if any(x in snippet_lower for x in ["404", "page not found", "access denied"]):
                continue

            seen_urls.add(url)
            formatted.append({"title": title, "snippet": snippet, "url": url})
            if len(formatted) >= max_results:
                break

        return {
            "success": True,
            "data": {
                "query": query,
                "results": formatted,
                "count": len(formatted),
            },
        }
    except ImportError:
        return {"success": False, "error": "ddgs not installed. Run: pip install ddgs"}
    except Exception as e:
        return {"success": False, "error": f"Search failed: {str(e)}"}


async def fetch(params: dict) -> dict:
    """Fetch URL content and extract text.
    params: {url: str, max_length: int (default 5000)}
    """
    url = params.get("url")
    if not url:
        return {"success": False, "error": "Missing 'url' parameter"}

    max_length = params.get("max_length", 5000)

    try:
        import httpx
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "Zenith/1.0"})
            resp.raise_for_status()

            # Parse HTML and extract text
            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove script and style elements
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator="\n", strip=True)

            # Truncate if too long
            if len(text) > max_length:
                text = text[:max_length] + "..."

            return {
                "success": True,
                "data": {
                    "url": url,
                    "title": soup.title.string if soup.title else "",
                    "content": text,
                    "length": len(text),
                },
            }
    except ImportError:
        return {
            "success": False,
            "error": "httpx or bs4 not installed. Run: pip install httpx beautifulsoup4",
        }
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"HTTP {e.response.status_code}: {e.response.reason_phrase}"}
    except Exception as e:
        return {"success": False, "error": f"Fetch failed: {str(e)}"}


async def scrape(params: dict) -> dict:
    """Scrape URL using Firecrawl (returns clean markdown). Best for articles, docs, complex pages.
    Falls back to fetch() if no FIRECRAWL_API_KEY.
    params: {url: str}
    """
    url = params.get("url")
    if not url:
        return {"success": False, "error": "Missing 'url' parameter"}

    try:
        import os
        api_key = os.getenv("FIRECRAWL_API_KEY", "")
        if not api_key:
            return await fetch(params)  # Fallback to basic fetch

        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=api_key)
        result = app.scrape_url(url, params={"formats": ["markdown"]})

        return {
            "success": True,
            "data": {
                "url": url,
                "markdown": (result.get("markdown", "") or "")[:5000],
                "title": result.get("metadata", {}).get("title", ""),
                "description": result.get("metadata", {}).get("description", ""),
            },
        }
    except ImportError:
        return await fetch(params)  # Fallback
    except Exception as e:
        return {"success": False, "error": f"Scrape failed: {str(e)}"}
