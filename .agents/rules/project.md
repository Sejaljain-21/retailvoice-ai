# RetailVoice AI — Project Rules

## Project Overview
**RetailVoice AI** (codename: NovaMart) is a production-quality AI-powered retail customer support voice agent built for a college major project demo. It consists of:
- **Backend**: FastAPI + SQLAlchemy (async) + SQLite, running on port 8000
- **Frontend**: React + TypeScript + Vite, running on port 5173
- **AI Voice Agent**: Named **Aura**, powered by Google Gemini (primary, free tier) with Groq as automatic fallback

## Tech Stack
| Layer | Technology |
|---|---|
| Backend API | FastAPI 0.115, Python 3.10 |
| Database | SQLite (aiosqlite) via SQLAlchemy async |
| LLM Primary | Google Gemini (`gemini-flash-lite-latest`) via OpenAI-compat endpoint |
| LLM Fallback | Groq (`openai/gpt-oss-20b`) — auto failover via `FallbackProvider` |
| STT | Browser Web Speech API (free, zero-config) |
| TTS | Browser Web Speech Synthesis API (free, zero-config) |
| Frontend | React 18, TypeScript, Vite, Tailwind-like custom CSS |
| Embeddings | Hashing-based (no download needed) |

## Architecture Rules

### Backend
- All LLM calls go through `app/services/llm/` — never call provider APIs directly from routes or orchestrator
- The provider chain is `GeminiProvider -> GroqProvider -> MockProvider` managed by `FallbackProvider`
- Gemini requires **thought signatures** (`extra_content`) to be preserved through multi-turn tool calls — this is already handled in `openai_compatible_provider.py` and `orchestrator.py`
- Agent tools are defined in `app/agent/tools.py` — always add new tools there
- Database seeding happens via `app/db/seed.py` — product images use `_PRODUCT_IMAGES` dict keyed by SKU
- Never use `picsum.photos` or random placeholder images — use curated Unsplash URLs

### Frontend
- The main voice/chat entry point is `src/pages/Support.tsx` + `src/components/chat/`
- The storefront is `src/pages/Storefront.tsx` — shows product grid from `/api/v1/catalog/products`
- The AI agent is called **Aura** (not "AI", not "bot") throughout the UI
- Voice agent widget is accessible from the storefront floating button

## API Keys & Credentials

### Active (FREE TIER)
- `GEMINI_API_KEY` — Google AI Studio free tier
- `GROQ_API_KEY` — Groq console free tier
- Both keys are in `.env` at repo root

### NOT USED (removed)
- Anthropic/Claude: removed (paid, not needed)
- Deepgram: removed (using browser STT instead)
- ElevenLabs: removed (using browser TTS instead)

## Environment Setup
```
LLM_PROVIDER=auto          # Gemini primary, Groq fallback
STT_PROVIDER=browser       # Free Web Speech API
TTS_PROVIDER=browser       # Free Web Speech Synthesis
SEED_ON_STARTUP=true       # Auto-seed demo data
```

## Running the Project
```powershell
# Backend
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Demo Accounts
| Role | Email | Password |
|---|---|---|
| Admin | admin@retailvoice.ai | Admin@123 |
| Supervisor | supervisor@retailvoice.ai | Demo@1234 |
| Agent | agent1@retailvoice.ai | Demo@1234 |
| Customer | customer@retailvoice.ai | Demo@1234 |

## Product Catalogue
21 seeded products across 6 categories:
- **Electronics**: Headphones, Earbuds, Smartphone, Laptop, Smartwatch, Power Bank
- **Fashion**: Running Shoes, Puffer Jacket, Cotton Tee, Backpack
- **Home & Kitchen**: Mixer Grinder, Air Purifier, Cookware Set, Cordless Vacuum
- **Beauty**: Vitamin C Serum, Anti-Hairfall Shampoo
- **Grocery**: Arabica Coffee, Groundnut Oil
- **Sports**: Yoga Mat, Dumbbells, Mountain Bike

## Key Decisions Made
1. **Gemini over Groq as primary**: Gemini `gemini-flash-lite-latest` is free, supports tool calling, and handles multi-turn tool conversations (with thought_signature workaround)
2. **Browser Speech over Deepgram/ElevenLabs**: 100% free, zero-config, good enough quality for demo
3. **SQLite over PostgreSQL**: Zero infrastructure needed for demo
4. **FallbackProvider pattern**: Automatic resilience — if Gemini hits rate limits, Groq takes over seamlessly
5. **Unsplash product images**: Curated relevant photos per SKU instead of random picsum images

## Coding Standards
- Always use async/await for database operations
- Never import `settings` inside a function body (use module-level or class-level)
- All new seed data images must be from Unsplash (images.unsplash.com) and verified to return HTTP 200
- Do not remove or change the FallbackProvider pattern without good reason — it ensures demo reliability
