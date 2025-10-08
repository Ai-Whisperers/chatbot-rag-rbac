# 📚 Corpus Management Guide

**For AI Agents**: This guide explains how to safely update, validate, and maintain the FAQ corpus.

---

## 🎯 What is the Corpus?

The corpus is the **isolated knowledge base** (`corpus/` directory) that the chatbot uses to answer questions. It is:

- **Shareable**: Can be versioned separately, mounted as volume, or used across multiple bots
- **Portable**: No code dependencies, pure data
- **Auditable**: Version-tracked with metadata.json
- **Source of truth**: The only thing the bot "knows"

---

## 📁 Corpus Structure

```
corpus/
├── README.md              # Human-readable documentation
├── privilege_map.json     # RBAC policy definitions
├── metadata.json          # Version tracking & corpus state
└── docs/                  # Actual FAQ content
    ├── *.md               # Markdown FAQ files
    └── examples/          # Example documents
```

### File Purposes

| File                  | Purpose                                       | Required |
|-----------------------|-----------------------------------------------|----------|
| `privilege_map.json`  | Defines who can see what (RBAC)               | ✅ Yes   |
| `metadata.json`       | Tracks version, hash, document count          | ✅ Yes   |
| `docs/*.md`           | FAQ content in markdown format                | ✅ Yes   |
| `README.md`           | Documentation for humans                      | ⚠️ Recommended |

---

## 📝 Adding New Content

### Step-by-Step Process

#### 1. Create Markdown File

Create a new file in `corpus/docs/`:

```bash
# Create file
touch corpus/docs/faq_shipping.md
```

**Format**:
```markdown
# Shipping FAQ

Tags: faq, shipping

## How long does shipping take?

Standard shipping takes 5-7 business days.
Express shipping takes 2-3 business days.

## Do you ship internationally?

Yes, we ship to over 50 countries worldwide.
International shipping takes 10-14 business days.
```

**Formatting rules**:
- Use H1 (`#`) for section title
- Include `Tags:` line with relevant tags
- Use H2 (`##`) for questions
- Provide concise, factual answers
- No marketing fluff or speculation

#### 2. Choose Appropriate Tags

Tags control **who can see** this content via RBAC.

**Available tags** (check `privilege_map.json`):
- `faq` - General public FAQs
- `pricing` - Pricing information
- `features` - Product features
- `support` - Support team only
- `internal` - Internal documentation (admin only)

**Never use**:
- `pii` - Blocks all access (for safety)

**Tag guidelines**:
- Use lowercase
- Comma-separated: `Tags: faq, pricing`
- At least one tag required
- Tags must match allowed tags in `privilege_map.json`

#### 3. Update Metadata

Edit `corpus/metadata.json`:

```json
{
  "version": "1.1.0",  // ← Increment version
  "last_updated": "2025-10-08T12:00:00Z",  // ← Update timestamp
  "document_count": 4,  // ← Update count
  "content_hash": "",   // ← Will be regenerated
  "tags": ["faq", "pricing", "features", "shipping"],  // ← Add new tags
  "description": "FAQ corpus with shipping information",
  "maintainer": "AI Whisperers"
}
```

**Version increment rules**:
- **Major** (1.0.0 → 2.0.0): Breaking changes, RBAC policy changes
- **Minor** (1.0.0 → 1.1.0): New content added
- **Patch** (1.0.0 → 1.0.1): Typo fixes, minor edits

#### 4. Validate Corpus

```bash
python scripts/validate_corpus.py
```

This checks:
- All required files exist
- JSON files are valid
- Tags are consistent
- No duplicate document IDs

#### 5. Load into Vector Store

```bash
python scripts/seed_corpus.py
```

This:
- Reads all `.md` files from `corpus/docs/`
- Extracts tags from each file
- Embeds content
- Stores in ChromaDB

#### 6. Test New Content

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How long does shipping take?",
    "scope": "public"
  }'
```

Expected output:
```json
{
  "answer": "Standard shipping takes 5-7 business days...",
  "grounding": ["internal documentation"],
  "policy": "public",
  "retrieved_count": 1,
  "filtered_count": 1
}
```

---

## ✏️ Modifying Existing Content

### Step-by-Step Process

#### 1. Locate File

```bash
# Find file containing specific content
grep -r "search term" corpus/docs/
```

#### 2. Edit Content

Open file and make changes:
```bash
# Edit file
nano corpus/docs/faq_shipping.md
```

**Editing guidelines**:
- Keep answers concise (<100 words per question)
- Be factual, no speculation
- Update, don't delete (unless retiring content)
- Preserve markdown formatting

#### 3. Update Metadata

```json
{
  "version": "1.0.1",  // ← Increment patch version
  "last_updated": "2025-10-08T14:30:00Z",  // ← Update timestamp
  // ... rest unchanged unless adding/removing tags
}
```

#### 4. Reload Vector Store

```bash
# Re-seed will update existing documents
python scripts/seed_corpus.py
```

---

## 🗑️ Removing Content

### When to Remove

- Information is outdated and no longer accurate
- Duplicate content exists
- Content violates policy (e.g., PII discovered)

### Step-by-Step Process

#### 1. Remove File or Section

```bash
# Option 1: Delete entire file
rm corpus/docs/old_faq.md

# Option 2: Remove specific Q&A from file
nano corpus/docs/faq_general.md  # Remove section
```

#### 2. Update Metadata

```json
{
  "version": "1.1.0",  // ← Minor version bump
  "last_updated": "2025-10-08T15:00:00Z",
  "document_count": 3,  // ← Decrease count
  "tags": ["faq", "pricing"],  // ← Remove unused tags
  // ...
}
```

#### 3. Clean Vector Store

```bash
# Option 1: Full reload (safest)
python scripts/seed_corpus.py --clean

# Option 2: Delete specific document by ID
curl -X DELETE http://localhost:8000/document/old-doc-id
```

---

## 🔐 Managing Access Control (RBAC)

### Understanding privilege_map.json

```json
{
  "public": {
    "description": "Anonymous users",
    "allowed_tags": ["faq", "pricing"],
    "deny": ["internal", "pii"]
  },
  "support": {
    "description": "Support team",
    "allowed_tags": ["faq", "pricing", "support"],
    "deny": ["internal", "pii"]
  }
}
```

**Access rules**:
1. Document must have at least ONE tag in `allowed_tags`
2. Document must have ZERO tags in `deny`

**Example**:
- Doc with tags `["faq", "pricing"]` → ✅ `public` can access
- Doc with tags `["faq", "internal"]` → ❌ `public` cannot access (has `internal`)
- Doc with tags `["support"]` → ❌ `public` cannot access (no allowed tag)

### Adding New Scope

```json
{
  "premium": {
    "description": "Premium customers",
    "allowed_tags": ["faq", "pricing", "features", "premium"],
    "deny": ["internal", "pii"]
  }
}
```

**Steps**:
1. Edit `corpus/privilege_map.json`
2. Add new scope with `allowed_tags` and `deny`
3. Reload policies: `curl -X POST http://localhost:8000/security/reload`
4. Test: `curl -X POST http://localhost:8000/ask -d '{"scope": "premium", ...}'`

### Modifying Existing Scope

**Example**: Allow support team to see internal docs

```json
{
  "support": {
    "allowed_tags": ["faq", "pricing", "support", "internal"],  // ← Added "internal"
    "deny": ["pii"]
  }
}
```

**⚠️ Warning**: Broadening access = **major version bump** (security change)

```json
{
  "version": "2.0.0",  // ← Major version
  // ...
}
```

---

## 📊 Corpus Health Checks

### Regular Maintenance Tasks

#### 1. Validate Integrity

```bash
# Check for issues
python scripts/validate_corpus.py

# Expected output:
# ✓ All required files exist
# ✓ JSON files are valid
# ✓ No duplicate document IDs
# ✓ All tags are used in privilege_map
```

#### 2. Check Statistics

```bash
curl http://localhost:8000/corpus/stats
```

Output:
```json
{
  "total_documents": 5,
  "available_tags": ["faq", "pricing", "support"]
}
```

#### 3. Audit Content

```bash
# List all documents
find corpus/docs -name "*.md"

# Check for PII (basic regex)
grep -rE "ssn|credit.card|password" corpus/docs/

# Find unused tags
# Compare tags in docs vs. privilege_map.json
```

---

## 🧪 Testing Content Changes

### Before Deployment

```bash
# 1. Validate corpus structure
python scripts/validate_corpus.py

# 2. Seed into test environment
python scripts/seed_corpus.py

# 3. Test sample questions
python scripts/test_qa.py  # If available

# 4. Check access control
curl -X POST http://localhost:8000/ask \
  -d '{"question": "Test?", "scope": "public"}'
```

### QA Checklist

- [ ] All tags exist in `privilege_map.json`
- [ ] No PII in public-accessible docs
- [ ] Answers are accurate and factual
- [ ] Markdown formatting is correct
- [ ] Version incremented in `metadata.json`
- [ ] Timestamp updated
- [ ] Content hash regenerated (if using)

---

## 🚨 Common Issues & Solutions

### Issue: "I don't have that information" for new content

**Diagnosis**:
```bash
# Check if document was loaded
curl http://localhost:8000/corpus/stats
```

**Solutions**:
1. Verify file is in `corpus/docs/` directory
2. Check file extension is `.md`
3. Ensure tags are present
4. Re-run `python scripts/seed_corpus.py`
5. Check similarity threshold isn't too high

---

### Issue: Content visible to wrong scope

**Diagnosis**:
```bash
# Test with different scopes
curl -X POST http://localhost:8000/ask \
  -d '{"question": "Test?", "scope": "public"}'

curl -X POST http://localhost:8000/ask \
  -d '{"question": "Test?", "scope": "support"}'
```

**Solutions**:
1. Check document tags match scope's `allowed_tags`
2. Ensure document has no tags in scope's `deny` list
3. Reload policies: `POST /security/reload`

---

### Issue: Duplicate or conflicting information

**Diagnosis**:
```bash
# Search for duplicate content
grep -r "specific fact" corpus/docs/
```

**Solutions**:
1. Consolidate into single document
2. Remove outdated version
3. Add "Updated: YYYY-MM-DD" to newer version
4. Re-seed corpus

---

## 🔄 Versioning Strategy

### Semantic Versioning

`MAJOR.MINOR.PATCH`

| Version Component | When to Increment                          | Example         |
|-------------------|--------------------------------------------|-----------------|
| MAJOR             | RBAC policy changes, breaking changes      | 1.0.0 → 2.0.0   |
| MINOR             | New content added, new tags introduced     | 1.0.0 → 1.1.0   |
| PATCH             | Typo fixes, minor edits to existing content| 1.0.0 → 1.0.1   |

### Version History

Track changes in `metadata.json` or separate `CHANGELOG.md`:

```markdown
# Corpus Changelog

## [1.1.0] - 2025-10-08
### Added
- Shipping FAQ (faq_shipping.md)
- New tag: "shipping"

## [1.0.1] - 2025-10-07
### Fixed
- Corrected support hours in faq_general.md

## [1.0.0] - 2025-10-01
### Initial
- General FAQ
- Pricing FAQ
- Support knowledge base
```

---

## 📦 Sharing Corpus

### As Git Repository

```bash
# Initialize separate repo for corpus
cd corpus/
git init
git add .
git commit -m "Initial corpus version 1.0.0"
git remote add origin https://github.com/org/faq-corpus.git
git push -u origin main
```

### As Docker Volume

```yaml
# docker-compose.yml
volumes:
  - ./corpus:/app/corpus:ro  # Read-only
```

### As Submodule

```bash
# In another bot instance
git submodule add https://github.com/org/faq-corpus.git corpus
git submodule update --init --recursive
```

---

## 🤖 For AI Agents: Corpus Modification Protocol

When modifying corpus as an AI agent:

### 1. Pre-Modification Checks

```python
# Read current state
with open("corpus/metadata.json") as f:
    metadata = json.load(f)
    current_version = metadata["version"]
    print(f"Current version: {current_version}")

# Validate corpus
subprocess.run(["python", "scripts/validate_corpus.py"], check=True)
```

### 2. Make Changes

- Edit/add/remove files in `corpus/docs/`
- Follow markdown formatting standards
- Use appropriate tags

### 3. Update Metadata

```python
from datetime import datetime

# Increment version
major, minor, patch = map(int, current_version.split("."))

# Determine version bump
if rbac_changed:
    major += 1
    minor, patch = 0, 0
elif new_content:
    minor += 1
    patch = 0
else:
    patch += 1

new_version = f"{major}.{minor}.{patch}"

# Update metadata
metadata["version"] = new_version
metadata["last_updated"] = datetime.utcnow().isoformat() + "Z"
metadata["document_count"] = len(list(Path("corpus/docs").rglob("*.md")))

with open("corpus/metadata.json", "w") as f:
    json.dump(metadata, f, indent=2)
```

### 4. Validate & Reload

```bash
# Validate
python scripts/validate_corpus.py

# Reload into vector store
python scripts/seed_corpus.py

# Test
curl -X POST http://localhost:8000/ask \
  -d '{"question": "Test modified content", "scope": "public"}'
```

### 5. Document Changes

Update relevant documentation:
- `corpus/README.md` if structure changed
- `CHANGELOG.md` if maintaining change log
- `metadata.json` always

---

## ✅ Best Practices Summary

1. **Always validate** before and after changes
2. **Increment version** on every change
3. **Use semantic versioning** correctly
4. **Test with real questions** after updates
5. **Keep tags consistent** with privilege_map
6. **No PII** in corpus (ever)
7. **Backup before major changes**
8. **Document your changes** in CHANGELOG
9. **Reload policies** after RBAC changes
10. **Keep answers concise** (<100 words)

---

## 🆘 Emergency Procedures

### Corpus Corrupted

```bash
# Restore from last known good version
git checkout HEAD~1 corpus/

# Or restore from backup
cp -r corpus_backup/* corpus/

# Re-seed
python scripts/seed_corpus.py
```

### PII Discovered in Corpus

```bash
# 1. Immediately remove file
rm corpus/docs/file_with_pii.md

# 2. Clean vector store
python scripts/seed_corpus.py --clean

# 3. Bump major version (security incident)
# Edit metadata.json: version "X.0.0"

# 4. Document incident
# Add note to CHANGELOG.md
```

### RBAC Breach

```bash
# 1. Review privilege_map.json
cat corpus/privilege_map.json

# 2. Fix incorrect policy
# Edit privilege_map.json

# 3. Reload policies
curl -X POST http://localhost:8000/security/reload

# 4. Bump major version
# Edit metadata.json

# 5. Audit all documents for proper tagging
grep -r "Tags:" corpus/docs/
```

---

**Remember**: The corpus is the single source of truth. Treat it with the same care you'd treat a production database.
