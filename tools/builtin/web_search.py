async def search(params: dict) -> dict:
    """Search the web (stub — placeholder until real search is integrated).
    params: {query: str}
    """
    query = params.get("query")
    if not query:
        return {"success": False, "error": "Missing 'query' parameter"}

    return {
        "success": True,
        "data": {
            "query": query,
            "results": [],
            "note": "Web search not yet integrated. This is a stub.",
        },
    }
