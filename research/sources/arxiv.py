"""arXiv API client. Completely free."""
from __future__ import annotations
import httpx
import xml.etree.ElementTree as ET
from typing import List

BASE = "https://export.arxiv.org/api/query"
NS   = {"a": "http://www.w3.org/2005/Atom"}

class ArxivClient:
    async def search(self, query: str, max_results: int = 8) -> List[dict]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(BASE, params={
                    "search_query": f"all:{query}",
                    "max_results": max_results,
                    "sortBy": "relevance",
                })
                root = ET.fromstring(r.text)
                results = []
                for entry in root.findall("a:entry", NS)[:max_results]:
                    title   = (entry.find("a:title",   NS) or entry).text or ""
                    summary = (entry.find("a:summary", NS) or entry).text or ""
                    url     = (entry.find("a:id",      NS) or entry).text or ""
                    year    = ((entry.find("a:published", NS) or entry).text or "")[:4]
                    results.append({
                        "title":    title.strip().replace("\n", " "),
                        "abstract": summary.strip()[:300],
                        "year":     year,
                        "source":   "arxiv",
                        "url":      url.strip(),
                    })
                return results
        except Exception:
            return []
