"""SaaS-level coding test queries for Zenith agent.

Tests real-world development capability:
- API design, database modeling, auth, CRUD, deployment
- Full-stack features, not just snippets
- Each query should be completable in one agent session

Usage: Run each query through Zenith and score the result.
"""

TEST_QUERIES = [
    # ── Tier 1: Basic CRUD (should pass 100%) ──────────────
    {
        "tier": "T1-Basic",
        "query": "Create a Python FastAPI app with a /health endpoint that returns {status: ok, timestamp: current_time}",
        "expect": ["main.py", "fastapi", "/health", "uvicorn"],
        "max_time": 60,
    },
    {
        "tier": "T1-Basic",
        "query": "Build a REST API for a todo list with create, list, update, delete endpoints using FastAPI and SQLite",
        "expect": ["database", "create", "list", "update", "delete", "sqlite"],
        "max_time": 120,
    },
    {
        "tier": "T1-Basic",
        "query": "Create a Python CLI tool that takes a URL, fetches the page, and saves the HTML to a file. Use argparse for arguments.",
        "expect": ["argparse", "requests", "save", "file"],
        "max_time": 60,
    },

    # ── Tier 2: Auth + Database (should pass 80%) ──────────
    {
        "tier": "T2-Auth",
        "query": "Add JWT authentication to the todo API. Users should register with email/password, login to get a token, and all todo endpoints should require auth.",
        "expect": ["jwt", "register", "login", "token", "password", "hash"],
        "max_time": 180,
    },
    {
        "tier": "T2-Auth",
        "query": "Create a user profile API with avatar upload. Store avatars in an uploads/ directory. Support JPEG and PNG, max 5MB. Return the avatar URL in the profile.",
        "expect": ["upload", "avatar", "multipart", "file", "url", "size"],
        "max_time": 180,
    },
    {
        "tier": "T2-Auth",
        "query": "Build a rate limiter middleware for FastAPI. Limit to 100 requests per minute per IP. Return 429 with retry-after header when exceeded.",
        "expect": ["middleware", "rate", "limit", "429", "retry", "ip"],
        "max_time": 120,
    },

    # ── Tier 3: Full-Stack Features (should pass 60%) ──────
    {
        "tier": "T3-FullStack",
        "query": "Build a real-time chat app with React frontend and FastAPI WebSocket backend. Show messages in real-time, support multiple rooms.",
        "expect": ["websocket", "react", "chat", "room", "real-time"],
        "max_time": 300,
    },
    {
        "tier": "T3-FullStack",
        "query": "Create a URL shortener service. Generate short codes, redirect to original URL, track click count and referrer. Include a stats dashboard.",
        "expect": ["short", "redirect", "code", "stats", "click", "dashboard"],
        "max_time": 240,
    },
    {
        "tier": "T3-FullStack",
        "query": "Build a file sharing service. Upload files up to 100MB, generate shareable links with optional expiry, download with progress. Use local storage.",
        "expect": ["upload", "share", "link", "expiry", "download", "progress"],
        "max_time": 300,
    },

    # ── Tier 4: Complex Systems (should pass 40%) ──────────
    {
        "tier": "T4-Complex",
        "query": "Build a multi-tenant SaaS billing system. Plans (free/pro/enterprise), usage-based metering, invoice generation, Stripe integration (mock).",
        "expect": ["tenant", "plan", "billing", "invoice", "metering", "stripe"],
        "max_time": 600,
    },
    {
        "tier": "T4-Complex",
        "query": "Create a CI/CD pipeline runner. Accept YAML config defining stages (build, test, deploy), execute shell commands per stage, stream logs in real-time, report status.",
        "expect": ["pipeline", "stage", "yaml", "execute", "log", "status"],
        "max_time": 600,
    },
    {
        "tier": "T4-Complex",
        "query": "Build an event sourcing system for an e-commerce store. Commands (place_order, cancel_order), events stored in append-only log, projections for read models, replay capability.",
        "expect": ["event", "command", "projection", "replay", "append", "log"],
        "max_time": 600,
    },

    # ── Tier 5: DevOps + Infrastructure (should pass 30%) ──
    {
        "tier": "T5-DevOps",
        "query": "Write a Dockerfile and docker-compose.yml for the todo API app. Include PostgreSQL, Redis for caching, and nginx reverse proxy. Add health checks.",
        "expect": ["dockerfile", "compose", "postgres", "redis", "nginx", "health"],
        "max_time": 240,
    },
    {
        "tier": "T5-DevOps",
        "query": "Create a Terraform config to deploy the API on AWS. EC2 instance, RDS PostgreSQL, S3 for uploads, security groups, and a load balancer.",
        "expect": ["terraform", "ec2", "rds", "s3", "security", "load_balancer"],
        "max_time": 300,
    },
    {
        "tier": "T5-DevOps",
        "query": "Write a GitHub Actions workflow that runs tests, builds Docker image, pushes to ECR, and deploys to ECS on push to main. Include rollback on failure.",
        "expect": ["actions", "docker", "ecr", "ecs", "deploy", "rollback"],
        "max_time": 300,
    },
]

# Scoring guide
SCORING = {
    "T1-Basic": {"pass": 1.0, "desc": "Must create working code, no errors"},
    "T2-Auth": {"pass": 0.8, "desc": "Auth flow works, edge cases may be missing"},
    "T3-FullStack": {"pass": 0.6, "desc": "Core feature works, may need polish"},
    "T4-Complex": {"pass": 0.4, "desc": "Architecture sound, some features incomplete"},
    "T5-DevOps": {"pass": 0.3, "desc": "Config valid, may need environment-specific tweaks"},
}


if __name__ == "__main__":
    print("SaaS Coding Test Queries")
    print("=" * 50)
    for tier in ["T1-Basic", "T2-Auth", "T3-FullStack", "T4-Complex", "T5-DevOps"]:
        queries = [q for q in TEST_QUERIES if q["tier"] == tier]
        print(f"\n{tier} ({len(queries)} queries, pass threshold: {SCORING[tier]['pass']:.0%})")
        for q in queries:
            print(f"  - {q['query'][:80]}...")
            print(f"    Expected: {', '.join(q['expect'])}")
            print(f"    Max time: {q['max_time']}s")
