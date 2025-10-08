# 📚 FAQ Corpus

This directory contains the **isolated, shareable knowledge base** for the FAQ chatbot.

## 🎯 Purpose

The corpus is the **single source of truth** for what the chatbot knows. It is completely isolated from application code, making it:

- **Portable**: Can be mounted as a volume, symlinked, or versioned separately
- **Shareable**: Multiple bot instances can use the same corpus
- **Auditable**: Clear record of what knowledge is available
- **Maintainable**: Non-technical users can update FAQs without touching code

---

## 📁 Structure

```
corpus/
├── README.md              # This file
├── privilege_map.json     # RBAC scope definitions
├── metadata.json          # Corpus version and tracking info
└── docs/                  # Actual FAQ documents
    ├── faq_general.md     # General questions
    ├── faq_pricing.md     # Pricing questions
    └── examples/          # Example documents
```

---

## 🔐 Access Control (RBAC)

Access control is managed through **privilege_map.json**, which defines scopes and their allowed/denied tags.

### Scopes

| Scope     | Description                        | Allowed Tags                                  |
|-----------|------------------------------------|-----------------------------------------------|
| `public`  | Anonymous users                    | faq, pricing, features                        |
| `support` | Support team members               | faq, pricing, features, support               |
| `admin`   | Administrative users               | faq, pricing, features, support, internal     |

### Tags

Each document in `docs/` should have metadata tags that control access:

- `faq`: General frequently asked questions
- `pricing`: Pricing information
- `features`: Product features
- `support`: Support-specific knowledge
- `internal`: Internal documentation (admin only)
- `pii`: Contains personally identifiable information (blocked by default)

---

## 📝 Document Format

### Markdown Files

Place FAQ content in `docs/` as markdown files. Each file should:

1. Use clear, descriptive filenames (e.g., `faq_shipping.md`)
2. Include structured headings for questions
3. Provide concise, factual answers

**Example:**

```markdown
# Shipping FAQ

## How long does shipping take?

Standard shipping takes 5-7 business days within the continental US.
Express shipping takes 2-3 business days.

Tags: faq, shipping
```

### Loading into Vector Store

Use the provided scripts to load corpus into the vector store:

```bash
# Load all documents from corpus/docs
python scripts/seed_corpus.py

# Validate corpus integrity
python scripts/validate_corpus.py
```

---

## 🔄 Updating the Corpus

### Adding New Documents

1. Create a new `.md` file in `docs/`
2. Add appropriate tags in the document metadata or filename
3. Run `python scripts/seed_corpus.py` to reload
4. Update `metadata.json` version

### Modifying Existing Documents

1. Edit the `.md` file
2. Run `python scripts/seed_corpus.py` to update vector store
3. Increment `metadata.json` version

### Changing Access Control

1. Edit `privilege_map.json`
2. Use API endpoint `POST /security/reload` to reload policies (no restart needed)

---

## 📊 Corpus Metadata

`metadata.json` tracks corpus state:

- **version**: Semantic version (e.g., "1.0.0")
- **last_updated**: ISO 8601 timestamp
- **document_count**: Total documents in corpus
- **content_hash**: SHA256 hash of all content (for integrity checks)
- **tags**: List of all available tags

This file should be updated whenever corpus content changes.

---

## 🚀 Portability

### As Git Submodule

```bash
# Add corpus as submodule from another repo
git submodule add https://github.com/org/faq-corpus.git corpus
```

### As Docker Volume

```yaml
volumes:
  - ./corpus:/app/corpus:ro  # Read-only mount
```

### As Symlink

```bash
# Link to shared corpus location
ln -s /shared/faq-corpus ./corpus
```

---

## ✅ Best Practices

1. **Version everything**: Increment `metadata.json` version on every change
2. **Keep it simple**: Use plain markdown, avoid complex formatting
3. **Tag consistently**: Use standardized tags across all documents
4. **Document sources**: Note where information came from in comments
5. **Validate before deploy**: Always run `validate_corpus.py`

---

## 🤖 For AI Agents

If you are an AI agent (like Claude) maintaining this corpus:

- **Read** `metadata.json` to understand current state
- **Validate** with `scripts/validate_corpus.py` before changes
- **Increment version** in `metadata.json` after updates
- **Preserve formatting**: Keep consistent markdown structure
- **Respect RBAC**: Ensure tags align with `privilege_map.json`

See `.ai/CORPUS_GUIDE.md` for detailed AI agent instructions.
