# 7 · Deployment

---

## 7.1 Local development

```bash
./scripts/dev.sh          # macOS / Linux
.\scripts\dev.ps1         # Windows
```

Creates the virtual environment, installs both dependency sets, seeds the demo database
and starts the API on `:8000` and Vite on `:5173`.

The Vite dev server proxies `/api` and `/ws` to the backend, so the browser stays on one
origin and CORS, cookies and the WebSocket behave exactly as they do behind nginx in
production.

---

## 7.2 Docker

```bash
docker compose up --build                  # SQLite, zero configuration
docker compose --profile postgres up -d    # with PostgreSQL
```

| Service | Port | Notes |
|---|---|---|
| `frontend` | 3000 → 80 | nginx serving the built SPA, proxying `/api` and `/ws` |
| `backend` | 8000 | uvicorn, non-root user, healthcheck |
| `postgres` | 5432 | Optional profile |

**Backend image** — Python 3.12 slim, dependencies installed in a cached layer, build
tools removed afterwards, runs as UID 10001, healthcheck on `/api/v1/health`. SQLite
lives on a named volume so the database survives a restart.

**Frontend image** — two stages: Node builds, nginx serves. The runtime image contains
no Node and no source.

**nginx** handles three things that matter:

```nginx
location /ws/ {                       # WebSocket upgrade + 1 h idle timeout
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;
    proxy_buffering off;              # voice must not be buffered
}
location /assets/ { expires 1y; add_header Cache-Control "public, immutable"; }
location / { try_files $uri $uri/ /index.html; }   # SPA routing
```

Without `proxy_buffering off`, streamed `reply_delta` frames arrive in a batch and the
typing effect disappears. Without the long `proxy_read_timeout`, voice calls drop after
60 seconds.

---

## 7.3 Environment configuration

Every setting has a working default; an empty `.env` is valid.

### Must change for production

| Variable | Development | Production |
|---|---|---|
| `SECRET_KEY` | placeholder | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
| `APP_ENV` | `development` | `production` |
| `DEBUG` | `true` | `false` |
| `DATABASE_URL` | SQLite file | `postgresql+asyncpg://…` |
| `CORS_ORIGINS` | localhost | Your real origins only |
| `ALLOW_ANONYMOUS_ORDER_LOOKUP` | `true` | **`false`** |
| `SEED_ON_STARTUP` | `true` | `false` |

`ALLOW_ANONYMOUS_ORDER_LOOKUP` is the one to check twice. It exists so the storefront
demo works without an account; leaving it on in production lets anyone who guesses an
order number read its contents.

### Provider selection

| Goal | Settings |
|---|---|
| Zero cost, zero setup | Defaults — offline planner, browser speech, hashing embedder |
| Production quality | `ANTHROPIC_API_KEY=…`, `TTS_PROVIDER=elevenlabs`, `EMBEDDING_PROVIDER=sentence-transformers` |
| Fully self-hosted | `STT_PROVIDER=whisper`, `TTS_PROVIDER=pyttsx3`, plus `requirements-optional.txt` |
| Any browser, including Firefox | `STT_PROVIDER=whisper` (browser STT is Chrome/Edge/Safari only) |

---

## 7.4 PostgreSQL

```bash
DATABASE_URL=postgresql+asyncpg://retailvoice:password@postgres:5432/retailvoice
docker compose --profile postgres up -d
```

No code changes are needed — every column type is portable and no vendor-specific SQL is
used. Enums are stored as strings, and structured payloads use `JSON`, which PostgreSQL
maps to `jsonb`.

Schema creation currently uses `Base.metadata.create_all`, which is right for a project
at this stage and wrong for one with production data to protect. Before the first real
deployment, adopt Alembic:

```bash
pip install alembic && alembic init migrations
# point sqlalchemy.url at DATABASE_URL, target_metadata at app.models.Base.metadata
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Then remove the `create_all` call from `init_db.py`.

---

## 7.5 Scaling

The API is **stateless** — no in-process session state, no sticky routing needed for
REST. Conversation state lives in the database.

```
            ┌──────────────┐
  clients ─▶│ load balancer│─▶ backend ×N   (REST: any instance)
            │  (TLS here)  │─▶ backend ×N   (WS: sticky per connection)
            └──────────────┘        │
                                    ▼
                          PostgreSQL (primary + replica)
```

**WebSockets are the constraint.** Each voice session holds a connection to one
instance, so the balancer needs connection-level affinity (any layer-4 balancer gives
this naturally). A dropped instance ends its live calls; clients reconnect and resume
because conversation state is in the database, not the socket.

### Known bottlenecks, in the order they will bite

| # | Bottleneck | Symptom | Fix |
|---|---|---|---|
| 1 | Retrieval loads every chunk per query | Latency climbs past ~5,000 chunks | pgvector + HNSW; only `services/rag.py` changes |
| 2 | LLM round-trips | 1.5–3 s per tool-using turn | Prompt caching, parallel tool execution, a smaller model for routing |
| 3 | Per-turn conversation writes | Write contention at high concurrency | Batch telemetry writes; move `tool_call_logs` to append-only storage |
| 4 | Analytics aggregates scan live tables | Dashboard slows as history grows | Materialised views, or a nightly rollup table |

None of these are hit at demonstration scale; they are listed so the next engineer knows
where to look first.

---

## 7.6 Security checklist

Before exposing the system publicly:

- [ ] `SECRET_KEY` regenerated and injected as a secret, never committed
- [ ] `DEBUG=false`, `APP_ENV=production`
- [ ] `ALLOW_ANONYMOUS_ORDER_LOOKUP=false`
- [ ] `CORS_ORIGINS` restricted to real origins
- [ ] TLS terminated at the edge; HSTS enabled
- [ ] `SEED_ON_STARTUP=false` and demo accounts deleted
- [ ] Rate limiting at the ingress (`limit_req`) — the app has none by design
- [ ] PostgreSQL not exposed to the internet; backups and PITR configured
- [ ] `ENABLE_PII_REDACTION=true` confirmed
- [ ] Provider API keys in a secret manager, not the environment file
- [ ] Log shipping configured; verify no PII reaches the logs
- [ ] Dependency scan (`pip-audit`, `npm audit`) in CI

**Already handled in code:** bcrypt cost 12; short-lived access tokens with refresh;
role guards plus per-record ownership; Pydantic validation everywhere; PII redaction
before the first write; secret-pattern stripping on output; a 12 MB audio cap; generic
500s that never leak internals.

**Deliberately not handled in code:** rate limiting and WAF rules belong at the ingress,
where they can be tuned without a redeploy.

---

## 7.7 Observability

Structured logs already carry the useful line:

```
turn conversation=5f2c… intent=track_shipment sentiment=-0.34 tools=1 latency=612ms escalated=False
```

Every response carries `X-Process-Time-Ms`.

**Health endpoints**

| Endpoint | Use |
|---|---|
| `/api/v1/health` | Liveness probe — never touches the database |
| `/api/v1/ready` | Readiness probe — checks the database and every provider |
| `/api/v1/capabilities` | Which providers this instance actually resolved to |

`/capabilities` is more useful than it looks in production: provider factories degrade
gracefully on failure, so an instance can be serving traffic with `browser` speech when
you configured `whisper`. This endpoint is how you find out.

**Worth adding next:** Prometheus counters for turns, escalations and tool failures;
OpenTelemetry spans across the tool loop; alerts on escalation-rate spikes and tool
success-rate drops (both already computed by `analytics_service`).

---

## 7.8 CI/CD

```yaml
name: ci
on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r backend/requirements.txt
      - run: cd backend && python -m pytest
      - run: cd backend && python -m app.db.seed --reset && python evaluate.py

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "22", cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm --prefix frontend ci
      - run: npm --prefix frontend run typecheck
      - run: npm --prefix frontend run build
```

`evaluate.py` exits non-zero if Precision@1 falls below 70 % or the agent pass rate below
100 %, so retrieval and behaviour regressions fail the build rather than shipping
quietly.

---

## 7.9 Backup and recovery

| Asset | Strategy |
|---|---|
| PostgreSQL | Managed automated backups + PITR; test the restore |
| SQLite (demo) | Copy the volume; the file is the database |
| Knowledge base | Export via `GET /knowledge` — the source of truth for agent answers |
| Embeddings | Derived, never backed up — `POST /knowledge/reindex` rebuilds them |
| Configuration | Environment files in a secret manager, versioned |

Recovery order after a total loss: restore PostgreSQL → start the backend → run
`/knowledge/reindex` → verify with `python evaluate.py`.

---

## 7.10 Cost

At the defaults, running cost is **zero** — no LLM calls, no speech APIs, no vector
database.

With Claude Sonnet, using this project's own measurements (~2,700 tokens per
tool-using turn, 60/40 input/output):

| Volume | Approximate monthly LLM cost |
|---|---|
| 1,000 conversations | ~$21 |
| 10,000 conversations | ~$210 |
| 100,000 conversations | ~$2,100 |

Levers, in order of effect: route trivial turns to Haiku (the local NLU already
classifies them, so this is a small change); enable prompt caching for the system prompt,
which is large and identical across turns; trim replayed history below 12 turns.

Speech adds cost only when a hosted provider is selected — browser speech and local
Whisper are free, ElevenLabs and Deepgram are metered.
