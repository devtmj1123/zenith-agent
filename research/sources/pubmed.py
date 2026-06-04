"""PubMed API client. Free, no key needed for basic use."""
from __future__ import annotations
import httpx
from typing import List

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

class PubMedClient:
    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    async def search(self, query: str, max_results: int = 8) -> List[dict]:
        params = {
            "db": "pubmed", "term": query,
            "retmax": max_results, "retmode": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(f"{BASE}/esearch.fcgi", params=params)
                ids = r.json().get("esearchresult", {}).get("idlist", [])
                if not ids:
                    return []
                s = await client.get(f"{BASE}/esummary.fcgi", params={
                    "db": "pubmed", "id": ",".join(ids[:5]), "retmode": "json",
                })
                results = []
                for uid, art in s.json().get("result", {}).items():
                    if uid == "uids":
                        continue
                    results.append({
                        "title":    art.get("title", ""),
                        "year":     art.get("pubdate", "")[:4],
                        "source":   "pubmed",
                        "pmid":     uid,
                        "url":      f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                        "abstract": art.get("title", ""),  # summary only
                    })
                return results
        except Exception:
            return []
