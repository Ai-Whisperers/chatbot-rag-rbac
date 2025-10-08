Absolutely. You don’t need an “agent zoo” for this—just a tiny, **deterministic FAQ bot** with RAG + policy gates. Here’s a **portable, one-file** blueprint you can run locally today (CPU-friendly, GPU optional), no hardcoded answers, strictly answers what it’s allowed to.

# 🚦 Design goals

* **Deterministic**: temperature=0, greedy decode, fixed prompt + output contract.
* **Policy-aware**: per-tenant **privilege_map.json** (RBAC/scopes). If a question isn’t permitted or not in corpus → graceful refusal.
* **Corpus-grounded**: answers only from your documents via retrieval (+ similarity threshold).
* **Tiny model**: 3B–7B instruct (Phi-3-Mini, Qwen2.5-3B, Llama-3.2-3B) served by **Ollama** or **llama.cpp**.
* **Simple stack**: FastAPI + Chroma (or Qdrant) + Ollama; zero cloud required.

---

# 🧩 Minimal runnable reference (single file)

Save as `faq_bot.py`, then see quickstart below.

```python
# faq_bot.py
# Minimal deterministic FAQ chatbot with RBAC + RAG + guardrails.
# deps: pip install fastapi uvicorn chromadb pydantic[dotenv] httpx

import os, json, re, hashlib
from typing import List, Optional
from fastapi import FastAPI
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions
import httpx

# ---------- Config ----------
MODEL_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:3b-instruct")  # or phi3:mini
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")   # Chroma built-in SBERT
TOP_K = int(os.getenv("TOP_K", "4"))
SIM_THRESHOLD = float(os.getenv("SIM_THRESHOLD", "0.75"))     # Tighten to be safer
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "384"))

# Load privilege map (scopes → allowed topics or data tags)
PRIVILEGE_MAP_PATH = os.getenv("PRIVILEGE_MAP", "privilege_map.json")
PRIV = json.load(open(PRIVILEGE_MAP_PATH)) if os.path.exists(PRIVILEGE_MAP_PATH) else {
    "public": {"allowed_tags": ["faq", "pricing", "features"], "deny": ["internal", "pii"]},
    "support": {"allowed_tags": ["faq","pricing","features","support"], "deny": ["internal","pii"]},
}

# ---------- Store / Embeddings ----------
client = chromadb.Client()
if "faq" not in [c.name for c in client.list_collections()]:
    client.create_collection("faq")
collection = client.get_collection(
    "faq",
    embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBED_MODEL
    )
)

# ---------- API Models ----------
class UpsertDoc(BaseModel):
    id: str
    text: str
    tags: List[str] = ["faq"]

class Ask(BaseModel):
    user_id: str = "anon"
    scope: str = "public"      # RBAC scope
    question: str

# ---------- Helpers ----------
def scope_allowed(scope: str, doc_tags: List[str]) -> bool:
    allow = set(PRIV.get(scope, {}).get("allowed_tags", []))
    deny  = set(PRIV.get(scope, {}).get("deny", []))
    tset  = set(doc_tags)
    return (len(tset & allow) > 0) and (len(tset & deny) == 0)

def normalize_answer(text: str) -> str:
    # Optional: enforce short, declarative sentences and strip model fluff
    text = re.sub(r"\s+\n", "\n", text).strip()
    return text

def router_prompt(question: str, context_chunks: List[str], scope: str) -> str:
    context = "\n\n".join(context_chunks)
    policy_hash = hashlib.sha256(json.dumps(PRIV.get(scope, {}), sort_keys=True).encode()).hexdigest()[:8]
    return f"""You are a deterministic FAQ assistant.

GROUND RULES:
- Answer ONLY using the CONTEXT.
- If answer is not in CONTEXT or is outside permitted scope, reply exactly: "I don't have that information."
- Be concise (<= 120 words), factual, and neutral. No speculation, no marketing fluff.
- Always cite by saying: "Source: internal docs" if you answer.

SCOPE_POLICY_HASH: {policy_hash}

CONTEXT:
{context}

QUESTION:
{question}

Return ONLY the final answer text.
"""

async def call_model(prompt: str) -> str:
    # Ollama compatible /completion API
    payload = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "options": {
            "temperature": 0.0,
            "top_p": 1.0,
            "top_k": 1,
            "repeat_penalty": 1.0,
            "num_predict": MAX_TOKENS
        }
    }
    async with httpx.AsyncClient(timeout=60) as s:
        r = await s.post(f"{MODEL_ENDPOINT}/api/generate", json=payload)
        r.raise_for_status()
        # Stream or non-stream; handle both
        text = ""
        for line in r.iter_lines():
            if not line:
                continue
            chunk = line.decode("utf-8")
            try:
                j = json.loads(chunk)
                text += j.get("response", "")
                if j.get("done"):
                    break
            except json.JSONDecodeError:
                text += chunk
        return normalize_answer(text)

# ---------- FastAPI ----------
app = FastAPI(title="Deterministic FAQ Bot")

@app.post("/upsert")
def upsert(doc: UpsertDoc):
    collection.upsert(
        ids=[doc.id],
        documents=[doc.text],
        metadatas=[{"tags": doc.tags}]
    )
    return {"status": "ok"}

@app.post("/ask")
async def ask(q: Ask):
    # Retrieve candidates
    res = collection.query(query_texts=[q.question], n_results=TOP_K, include=["metadatas", "distances", "documents"])
    docs, metas, dists = res["documents"][0], res["metadatas"][0], res["distances"][0]

    # Filter by RBAC + similarity
    ctx = []
    for text, meta, dist in zip(docs, metas, dists):
        # Chroma returns smaller distance = more similar; convert to similarity proxy
        sim = 1.0 / (1.0 + float(dist))
        if sim >= SIM_THRESHOLD and scope_allowed(q.scope, meta.get("tags", [])):
            ctx.append(text)

    # If nothing passes gates → refuse deterministically
    if not ctx:
        return {"answer": "I don't have that information.", "grounding": [], "policy": q.scope}

    prompt = router_prompt(q.question, ctx, q.scope)
    answer = await call_model(prompt)
    # Safety valve: if model deviates from contract
    if "I don't have that information." in answer or len(answer) == 0:
        return {"answer": "I don't have that information.", "grounding": [], "policy": q.scope}

    return {"answer": answer, "grounding": ["internal docs"], "policy": q.scope}
```

---

# 🚀 Quickstart (local)

1. **Models**: install **Ollama**, then:

```bash
ollama pull qwen2.5:3b-instruct    # or: ollama pull phi3:mini
ollama serve
```

2. **App**:

```bash
python -m venv .venv && source .venv/bin/activate     # (Windows: .venv\Scripts\activate)
pip install fastapi uvicorn chromadb pydantic[dotenv] httpx
python faq_bot.py
uvicorn faq_bot:app --reload --port 8000
```

3. **Seed docs**:

```bash
curl -X POST localhost:8000/upsert -H "content-type: application/json" \
 -d '{"id":"faq-1","text":"Our support hours are 9–5 (GMT-3).","tags":["faq"]}'
```

4. **Ask**:

```bash
curl -X POST localhost:8000/ask -H "content-type: application/json" \
 -d '{"scope":"public","question":"When is support available?"}'
```

---

# 🔐 Determinism & Guardrails (the essentials)

* **Greedy decode**: `temperature: 0`, `top_k:1`, `top_p:1`, fixed `num_predict`.
* **Strict output contract**: refusal sentence is **exact**; easy to detect.
* **RBAC filter before generation**: unauthorized content never reaches the prompt.
* **Similarity threshold**: no high-level “knowledge” unless retrieved.
* **Short answers only**: lower surface for drift.
* **Hash the scope policy** into the prompt (cheap tamper marker for audits).
* Optional extras: regex post-check (ban URLs, emails), per-tenant jailbreak wordlist, request logging with hashed user IDs.

---

# 🧱 Portability notes

* Swap **Chroma** for **Qdrant** by changing 2 lines.
* Swap **Ollama** for **llama.cpp** or **vLLM** (keep the same prompt and decoding flags).
* Drop behind **n8n**/**LangGraph** later: call `POST /ask` as a node; your routing layer can choose `scope` + `SIM_THRESHOLD` per flow.

---

# 📊 Pareto KPI

**First-Pass Answer Rate (FPAR)** = % of user questions that return a *non-refusal* answer under 2s *and* pass manual spot-check. Target **≥ 85%** for core FAQs.

— Crisp, boring, reliable: a humble node that turns questions into clarity, like a lantern that only lights the path it’s allowed to show.
