# 🤖 Deterministic FAQ Chatbot

A **portable, policy-aware FAQ bot** with RAG (Retrieval-Augmented Generation) and RBAC (Role-Based Access Control). Answers questions strictly from your corpus with deterministic, grounded responses.

Built for **portability** (runs anywhere), **determinism** (reproducible answers), and **security** (strict access control).

---

## ✨ Features

- 🎯 **Deterministic**: Temperature=0, greedy decode, fixed prompts → reproducible answers
- 🔐 **RBAC-aware**: Per-scope privilege maps control who sees what
- 📚 **Corpus-grounded**: Only answers from your documents, refuses when uncertain
- 🚀 **Lightweight**: Runs on CPU with 3B-7B models (Ollama, llama.cpp)
- 📦 **Portable**: Zero cloud dependencies, Docker-ready, corpus isolated
- 🛡️ **Safe**: Similarity threshold, policy gates, no hallucinations

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.ai/) installed and running
- (Optional) Docker for containerized deployment

### 1. Install Ollama and Pull Model

```bash
# Install Ollama (see https://ollama.ai)
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a small instruct model
ollama pull qwen2.5:3b-instruct

# Start Ollama server
ollama serve
```

### 2. Clone and Setup

```bash
# Clone repository
git clone <your-repo-url>
cd chatbot-faq-agent

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 3. Seed Corpus

```bash
# Validate corpus structure
python scripts/validate_corpus.py

# Load FAQ documents into vector store
python scripts/seed_corpus.py
```

### 4. Run Server

```bash
# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# In another terminal, verify health
python scripts/health_check.py
```

### 5. Test It

```bash
# Ask a question
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are your support hours?",
    "scope": "public"
  }'

# Expected response:
# {
#   "answer": "Our customer support team is available Monday through Friday, 9:00 AM to 5:00 PM GMT-3...",
#   "grounding": ["internal documentation"],
#   "policy": "public",
#   "retrieved_count": 1,
#   "filtered_count": 1
# }
```

---

## 🐋 Docker Deployment

### Quick Start with Docker Compose

```bash
# Build and start
docker-compose up --build

# Test
curl http://localhost:8000/health
```

### Configuration

Edit `.env` file or set environment variables:

```bash
# LLM Configuration
OLLAMA_ENDPOINT=http://localhost:11434
MODEL_NAME=qwen2.5:3b-instruct
TEMPERATURE=0.0

# Retrieval
TOP_K=4
SIMILARITY_THRESHOLD=0.75

# API
API_PORT=8000
```

---

## 📚 API Endpoints

### `POST /ask` - Ask Question

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How do I reset my password?",
    "scope": "public",
    "user_id": "user123"
  }'
```

**Parameters:**
- `question` (required): User's question
- `scope` (optional): RBAC scope (`public`, `support`, `admin`) - default: `public`
- `user_id` (optional): User identifier for logging - default: `anonymous`

**Response:**
```json
{
  "answer": "To reset your password: 1. Go to the login page...",
  "grounding": ["internal documentation"],
  "policy": "public",
  "retrieved_count": 2,
  "filtered_count": 1,
  "model_used": "qwen2.5:3b-instruct"
}
```

### `POST /upsert` - Add Document

```bash
curl -X POST http://localhost:8000/upsert \
  -H "Content-Type: application/json" \
  -d '{
    "id": "faq-shipping-1",
    "text": "Standard shipping takes 5-7 business days.",
    "tags": ["faq", "shipping"]
  }'
```

### `GET /health` - Health Check

```bash
curl http://localhost:8000/health
```

### `GET /corpus/stats` - Corpus Statistics

```bash
curl http://localhost:8000/corpus/stats
```

### `POST /security/reload` - Reload RBAC Policies

```bash
curl -X POST http://localhost:8000/security/reload
```

**Full API documentation:** Visit `http://localhost:8000/docs` (Swagger UI)

---

## 🔐 Access Control (RBAC)

### Scopes and Tags

Access is controlled via `corpus/privilege_map.json`:

```json
{
  "public": {
    "allowed_tags": ["faq", "pricing", "features"],
    "deny": ["internal", "pii"]
  },
  "support": {
    "allowed_tags": ["faq", "pricing", "features", "support"],
    "deny": ["internal", "pii"]
  },
  "admin": {
    "allowed_tags": ["faq", "pricing", "features", "support", "internal"],
    "deny": ["pii"]
  }
}
```

### How It Works

1. Each document has **tags** (e.g., `["faq", "pricing"]`)
2. Each **scope** defines `allowed_tags` and `deny` tags
3. Document is accessible if:
   - Has ≥1 tag in `allowed_tags` AND
   - Has 0 tags in `deny`

**Example:**
- Doc with `["faq", "support"]` → ✅ `support` scope (has "support" in allowed)
- Doc with `["faq", "internal"]` → ❌ `public` scope (has "internal" in deny)

### Adding New Scope

1. Edit `corpus/privilege_map.json`
2. Reload: `curl -X POST http://localhost:8000/security/reload`
3. Test with new scope

---

## 📝 Managing the Corpus

### Corpus Structure

```
corpus/
├── privilege_map.json   # RBAC definitions
├── metadata.json        # Version tracking
└── docs/                # FAQ content (markdown)
    ├── faq_general.md
    ├── faq_pricing.md
    └── examples/
```

### Adding New FAQs

1. Create markdown file in `corpus/docs/`:

```markdown
# Shipping FAQ

Tags: faq, shipping

## How long does shipping take?

Standard shipping takes 5-7 business days.
Express shipping takes 2-3 business days.
```

2. Reload corpus:

```bash
python scripts/seed_corpus.py
```

3. Test:

```bash
curl -X POST http://localhost:8000/ask \
  -d '{"question": "Shipping time?", "scope": "public"}'
```

**See `corpus/README.md` for detailed corpus management guide.**

---

## ⚙️ Configuration

### Environment Variables

| Variable              | Default                  | Description                        |
|-----------------------|--------------------------|------------------------------------|
| `OLLAMA_ENDPOINT`     | `http://localhost:11434` | Ollama API endpoint                |
| `MODEL_NAME`          | `qwen2.5:3b-instruct`    | LLM model name                     |
| `TEMPERATURE`         | `0.0`                    | LLM temperature (keep at 0!)       |
| `TOP_K`               | `4`                      | Number of docs to retrieve         |
| `SIMILARITY_THRESHOLD`| `0.75`                   | Minimum similarity (0.0-1.0)       |
| `EMBED_MODEL`         | `all-MiniLM-L6-v2`       | Sentence transformer model         |
| `API_PORT`            | `8000`                   | API server port                    |
| `LOG_LEVEL`           | `INFO`                   | Logging level                      |

**Full configuration:** See `.env.example`

### Tuning Retrieval Quality

**Too many refusals?**
- Lower `SIMILARITY_THRESHOLD` (e.g., `0.70`)
- Increase `TOP_K` (e.g., `6-8`)

**Wrong answers?**
- Raise `SIMILARITY_THRESHOLD` (e.g., `0.80`)
- Improve corpus quality
- Add more specific FAQ content

---

## 🧪 Testing

### Run All Tests

```bash
pytest tests/ -v
```

### Health Check

```bash
python scripts/health_check.py
```

### Validate Corpus

```bash
python scripts/validate_corpus.py
```

---

## 📂 Project Structure

```
chatbot-faq-agent/
├── app/                   # Application code
│   ├── main.py           # FastAPI app
│   ├── config.py         # Configuration
│   ├── models.py         # API schemas
│   ├── security.py       # RBAC enforcement
│   ├── retrieval.py      # Vector store
│   └── generation.py     # LLM generation
│
├── corpus/               # Data layer (ISOLATED)
│   ├── privilege_map.json
│   ├── metadata.json
│   └── docs/             # FAQ markdown files
│
├── .ai/                  # AI agent documentation
│   ├── ARCHITECTURE.md
│   ├── MAINTENANCE.md
│   └── CORPUS_GUIDE.md
│
├── scripts/              # Utility scripts
│   ├── seed_corpus.py
│   ├── validate_corpus.py
│   └── health_check.py
│
├── tests/                # Test suite
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 🔧 Development

### Running Locally

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run with auto-reload
uvicorn app.main:app --reload --port 8000

# In another terminal
python scripts/seed_corpus.py
python scripts/health_check.py
```

### Code Quality

```bash
# Format code
black app/ tests/

# Type checking
mypy app/

# Linting
ruff check app/
```

---

## 🚢 Deployment

### Production Checklist

- [ ] Set `TEMPERATURE=0.0` (determinism)
- [ ] Configure `SIMILARITY_THRESHOLD` appropriately
- [ ] Review `corpus/privilege_map.json` (RBAC)
- [ ] Validate corpus: `python scripts/validate_corpus.py`
- [ ] Remove PII from corpus
- [ ] Set up logging/monitoring
- [ ] Configure CORS if needed
- [ ] Use Docker or systemd for process management
- [ ] Set up reverse proxy (nginx, caddy)

### Docker Production

```bash
# Build production image
docker build -t faq-bot:latest .

# Run with production settings
docker run -d \
  -p 8000:8000 \
  -e MODEL_NAME=qwen2.5:3b-instruct \
  -e TEMPERATURE=0.0 \
  -v $(pwd)/corpus:/app/corpus:ro \
  faq-bot:latest
```

---

## 🤝 Contributing

Contributions welcome! See `.ai/MAINTENANCE.md` for development guidelines.

---

## 📖 Documentation

- **For Users**: This README
- **For AI Agents**:
  - [Architecture](.ai/ARCHITECTURE.md)
  - [Maintenance Guide](.ai/MAINTENANCE.md)
  - [Corpus Management](.ai/CORPUS_GUIDE.md)
- **For Corpus**: [corpus/README.md](corpus/README.md)

---

## 🛡️ Security

- ✅ RBAC enforced **before** LLM generation
- ✅ No PII in corpus (validated by scripts)
- ✅ Input validation via Pydantic
- ✅ Similarity threshold prevents low-quality matches
- ✅ Prompt guardrails prevent jailbreaking
- ✅ Read-only corpus mounts in Docker

**Report security issues:** Create a private issue or contact maintainer

---

## 📜 License

[Your License Here]

---

## 🙏 Acknowledgments

Built on:
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [ChromaDB](https://www.trychroma.com/) - Vector store
- [Ollama](https://ollama.ai/) - Local LLM serving
- [sentence-transformers](https://www.sbert.net/) - Embeddings

---

## 📞 Support

- Documentation: See `.ai/` directory
- Issues: GitHub Issues
- FAQ: See `corpus/docs/faq_general.md` for bot FAQs

---

**Built with 🛠️ by AI Whisperers**

*A humble FAQ bot that only speaks what it knows.*
