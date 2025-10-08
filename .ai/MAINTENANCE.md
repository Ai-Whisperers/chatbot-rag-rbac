# 🔧 Maintenance Guide

**For AI Agents**: This guide explains how to safely modify, extend, and debug this codebase.

---

## 🎯 Guiding Principles

1. **Determinism first**: Any change that affects LLM output must preserve reproducibility
2. **Backward compatibility**: Corpus format must remain stable
3. **Security cannot regress**: RBAC must always be enforced pre-generation
4. **Keep it simple**: Resist feature creep, optimize for maintainability

---

## 📝 Common Maintenance Tasks

### 1. Adding New FAQ Content

**Files involved**: `corpus/docs/`

**Steps**:
```bash
# 1. Create new markdown file
echo "# New FAQ\n\nQ: Question?\nA: Answer.\n\nTags: faq" > corpus/docs/new_faq.md

# 2. Update metadata
# Edit corpus/metadata.json - increment version, update timestamp

# 3. Load into vector store
python scripts/seed_corpus.py

# 4. Verify
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Question?", "scope": "public"}'
```

**Validation**:
- Run `python scripts/validate_corpus.py` before deploying
- Check that tags are consistent with `privilege_map.json`

---

### 2. Modifying RBAC Policies

**Files involved**: `corpus/privilege_map.json`

**Steps**:
```bash
# 1. Edit privilege_map.json
# Add new scope or modify existing ones

# 2. Reload policies (no restart needed!)
curl -X POST http://localhost:8000/security/reload

# 3. Test new scope
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Test?", "scope": "new_scope"}'
```

**Safety checks**:
- Always have at least one public scope
- Never remove the `deny` field (set to `[]` if no denials)
- Test with various scopes before deploying

---

### 3. Adjusting Retrieval Quality

**Files involved**: `app/config.py`, `.env`

**Key parameters**:

| Parameter              | Effect                                  | Recommendation      |
|------------------------|-----------------------------------------|---------------------|
| `TOP_K`                | More candidates = better recall         | 3-5 for small corpus, 10-20 for large |
| `SIMILARITY_THRESHOLD` | Higher = stricter matching              | 0.70-0.80 (default: 0.75) |
| `MAX_TOKENS`           | Longer answers allowed                  | 256-512 |

**Tuning process**:
1. Start with defaults
2. Test with real questions
3. If too many refusals → lower threshold or increase TOP_K
4. If wrong answers → raise threshold or reduce TOP_K
5. Document changes in `.env.example`

---

### 4. Changing LLM Model

**Files involved**: `.env`, potentially `app/generation.py`

**Steps**:
```bash
# 1. Pull new model in Ollama
ollama pull llama3.2:3b-instruct

# 2. Update environment
export MODEL_NAME=llama3.2:3b-instruct

# 3. Restart service
# Docker: docker-compose restart
# Local: restart uvicorn

# 4. Test answer quality
python scripts/health_check.py
```

**Model requirements**:
- Must support instruct/chat format
- Should be 3B-7B for CPU efficiency
- Must respect temperature=0 for determinism

**Recommended models**:
- `qwen2.5:3b-instruct` (default, balanced)
- `phi3:mini` (fast, compact)
- `llama3.2:3b-instruct` (high quality)

---

### 5. Adding New API Endpoints

**Files involved**: `app/main.py`, `app/models.py`

**Pattern to follow**:
```python
# 1. Define request/response models in app/models.py
class NewRequest(BaseModel):
    param: str = Field(..., description="Parameter description")

class NewResponse(BaseModel):
    result: str

# 2. Add endpoint in app/main.py
@app.post("/new_endpoint", response_model=NewResponse)
def new_endpoint(req: NewRequest):
    # Implement logic
    return NewResponse(result="OK")

# 3. Add tests in tests/test_integration.py
def test_new_endpoint():
    response = client.post("/new_endpoint", json={"param": "value"})
    assert response.status_code == 200
```

**Checklist**:
- [ ] Pydantic model for validation
- [ ] Docstring with parameter descriptions
- [ ] Error handling with proper HTTP codes
- [ ] Integration test
- [ ] Update API documentation

---

### 6. Optimizing Performance

**Bottlenecks and solutions**:

#### Slow LLM Generation
```bash
# Option 1: Use GPU-accelerated Ollama
ollama serve --gpu

# Option 2: Reduce MAX_TOKENS
export MAX_TOKENS=256

# Option 3: Use smaller model
export MODEL_NAME=phi3:mini
```

#### Slow Vector Search
```python
# In app/retrieval.py, enable query caching
from app.retrieval import cached_query

# Already implemented with @lru_cache
# Tune cache size in config.py:
EMBEDDING_CACHE_SIZE = 2000  # Increase for more caching
```

#### High Memory Usage
```bash
# Reduce embedding model size
export EMBED_MODEL=all-MiniLM-L6-v2  # Smaller than default

# Or use quantized models in Ollama
ollama pull qwen2.5:3b-instruct-q4_0  # 4-bit quantized
```

---

### 7. Debugging Common Issues

#### Issue: "I don't have that information" for valid questions

**Diagnosis**:
```python
# Check retrieved documents
response = requests.post("http://localhost:8000/ask", json={
    "question": "Your question here",
    "scope": "public"
})
print(response.json()["retrieved_count"])  # How many retrieved?
print(response.json()["filtered_count"])   # How many after RBAC?
```

**Solutions**:
- If `retrieved_count = 0`: Question doesn't match corpus → add relevant docs
- If `filtered_count = 0`: RBAC blocking → check tags and privilege_map
- If both > 0: Similarity too low → lower `SIMILARITY_THRESHOLD`

#### Issue: Wrong answers given

**Diagnosis**:
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
# Restart and check logs for retrieved context
```

**Solutions**:
- Conflicting information in corpus → consolidate or remove duplicates
- Irrelevant docs retrieved → increase `SIMILARITY_THRESHOLD`
- Model hallucinating → strengthen prompt guardrails in `generation.py`

#### Issue: Slow response times

**Diagnosis**:
```bash
# Profile endpoint
time curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Test?", "scope": "public"}'
```

**Solutions**:
- Check Ollama is running: `curl http://localhost:11434/api/tags`
- Monitor Ollama logs: `ollama logs`
- Reduce `MAX_TOKENS` or use smaller model

---

## 🧪 Testing Workflow

### Before Making Changes

```bash
# 1. Run existing tests
python -m pytest tests/

# 2. Check corpus validity
python scripts/validate_corpus.py

# 3. Verify API health
curl http://localhost:8000/health
```

### After Making Changes

```bash
# 1. Re-validate corpus (if modified)
python scripts/validate_corpus.py

# 2. Run tests
python -m pytest tests/ -v

# 3. Integration smoke test
python scripts/health_check.py

# 4. Manual QA
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What are your support hours?", "scope": "public"}'
```

---

## 📦 Dependency Management

### Adding New Dependencies

```bash
# 1. Install dependency
pip install new-package

# 2. Update requirements.txt
pip freeze | grep new-package >> requirements.txt

# 3. Test in clean environment
python -m venv .test-venv
source .test-venv/bin/activate  # Windows: .test-venv\Scripts\activate
pip install -r requirements.txt
python -m pytest tests/
```

**Dependency policy**:
- Minimize dependencies (fewer = more portable)
- Prefer standard library when possible
- Pin versions in `requirements.txt`
- Avoid transitive dependency bloat

### Updating Dependencies

```bash
# 1. Check for updates
pip list --outdated

# 2. Update specific package
pip install --upgrade package-name

# 3. Test thoroughly
python -m pytest tests/

# 4. Update requirements.txt
pip freeze > requirements.txt
```

---

## 🔄 Version Control Best Practices

### What to Commit

✅ **Do commit**:
- Application code (`app/`)
- Tests (`tests/`)
- Scripts (`scripts/`)
- Corpus content (`corpus/docs/`)
- RBAC policies (`corpus/privilege_map.json`)
- Documentation (`.ai/`, `README.md`)
- Configuration templates (`.env.example`)

❌ **Don't commit**:
- Environment variables (`.env`)
- Vector store data (`.chroma/`)
- Python cache (`__pycache__`, `*.pyc`)
- Virtual environments (`.venv/`)
- IDE settings (`.vscode/`, `.idea/`)

### Commit Message Format

```
<type>: <description>

[optional body]

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- refactor: Code refactoring
- test: Test additions/changes
- chore: Maintenance tasks
```

**Examples**:
```
feat: add batch upsert endpoint

docs: update corpus README with tagging guide

fix: correct similarity threshold in retrieval

refactor: extract policy hash to security module
```

---

## 🚨 Critical Paths - DO NOT BREAK

These components are **load-bearing** and must not be changed without careful consideration:

1. **Corpus isolation** (`corpus/` directory structure)
   - Must remain portable (no absolute paths)
   - Must be mountable as volume
   - Format must be backward compatible

2. **RBAC enforcement point** (`app/main.py:ask_question()`)
   - Must filter BEFORE LLM generation
   - Must check both similarity AND scope

3. **Deterministic generation** (`app/generation.py`)
   - `temperature` must remain 0.0
   - Prompt template must preserve guardrails

4. **API contracts** (`app/models.py`)
   - Changes must be backward compatible
   - Required fields cannot be removed

---

## 🔐 Security Maintenance

### Regular Security Checks

```bash
# 1. Audit dependencies
pip-audit  # Install: pip install pip-audit

# 2. Check for secrets in corpus
grep -r "password\|secret\|api_key" corpus/

# 3. Validate RBAC enforcement
python tests/test_security.py -v

# 4. Review privilege map
cat corpus/privilege_map.json
```

### Handling Security Issues

1. **Never expose internal tags to public scope**
2. **Always validate user input** (Pydantic does this)
3. **Log security events** (scope escalation attempts)
4. **Review corpus for PII** before sharing

---

## 📚 Documentation Maintenance

### When to Update Documentation

Update relevant docs when:

| Change                      | Update                                    |
|-----------------------------|-------------------------------------------|
| New API endpoint            | `README.md`, OpenAPI schema               |
| Architecture change         | `.ai/ARCHITECTURE.md`                     |
| New maintenance task        | `.ai/MAINTENANCE.md` (this file)          |
| Corpus format change        | `corpus/README.md`, `.ai/CORPUS_GUIDE.md` |
| Configuration option added  | `.env.example`, `README.md`               |

### Documentation Standards

- Use Markdown for all docs
- Include examples for all procedures
- Keep `.ai/` docs AI-agent friendly (structured, detailed)
- Keep `README.md` user-friendly (concise, practical)

---

## 🎯 For AI Agents

When maintaining this codebase:

1. **Always read existing code** before modifying
2. **Run tests** before and after changes
3. **Update documentation** to match code changes
4. **Preserve determinism** in all LLM-related changes
5. **Ask before breaking changes** to critical paths
6. **Validate corpus** after modifications
7. **Check backward compatibility** for API changes

### Checklist for Code Changes

```markdown
- [ ] Read relevant .ai/ documentation
- [ ] Understand impact on determinism
- [ ] Run existing tests
- [ ] Make changes with minimal scope
- [ ] Add/update tests for changes
- [ ] Update documentation if needed
- [ ] Validate corpus if modified
- [ ] Run full test suite
- [ ] Manual smoke test
- [ ] Update CHANGELOG if applicable
```

---

## 🆘 Getting Help

If you're an AI agent and encounter issues:

1. **Read architecture**: `.ai/ARCHITECTURE.md`
2. **Check corpus guide**: `.ai/CORPUS_GUIDE.md`
3. **Review error logs**: Look for Python tracebacks
4. **Validate config**: `python -c "from app.config import validate_config; validate_config()"`
5. **Test components**: Run individual test files
6. **Ask user**: If ambiguous, clarify requirements

**Common pitfall**: Changing `temperature` or prompt without understanding determinism impact. Always preserve deterministic behavior.
