#!/usr/bin/env python
"""
Seed corpus documents into vector store.
Reads markdown files from corpus/docs/ and loads them into ChromaDB.
"""

import re
import hashlib
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Add parent directory to path to import app modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.retrieval import get_vector_store
from app.config import CORPUS_DOCS_DIR, METADATA_PATH
import json


def extract_tags_from_content(content: str) -> List[str]:
    """
    Extract tags from markdown content.
    Looks for lines like: Tags: faq, pricing
    """
    pattern = r'^Tags:\s*(.+)$'
    match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)

    if match:
        tags_str = match.group(1)
        tags = [tag.strip().lower() for tag in tags_str.split(',')]
        return [t for t in tags if t]  # Filter empty strings

    return ["faq"]  # Default tag if none found


def parse_markdown_file(file_path: Path) -> List[Tuple[str, str, List[str]]]:
    """
    Parse markdown file into chunks.
    Each H2 section becomes a separate document.

    Returns:
        List of (doc_id, text, tags) tuples
    """
    content = file_path.read_text(encoding='utf-8')

    # Extract tags from content
    tags = extract_tags_from_content(content)

    # Remove the Tags: line from content
    content = re.sub(r'^Tags:\s*.+$', '', content, flags=re.MULTILINE | re.IGNORECASE)

    # Split by H2 headers (##)
    sections = re.split(r'\n##\s+', content)

    documents = []

    for i, section in enumerate(sections):
        section = section.strip()
        if not section:
            continue

        # First section might include H1 and metadata, skip if too short
        if i == 0 and len(section) < 50:
            continue

        # Generate doc ID from filename and section number
        doc_id = f"{file_path.stem}-{i}"

        # Clean up section
        section = re.sub(r'\s+', ' ', section).strip()

        if len(section) > 20:  # Minimum length threshold
            documents.append((doc_id, section, tags))

    return documents


def load_all_documents() -> List[Tuple[str, str, List[str], Dict[str, Any]]]:
    """
    Load all markdown files from corpus/docs/.

    Returns:
        List of (doc_id, text, tags, metadata) tuples
    """
    if not CORPUS_DOCS_DIR.exists():
        print(f"❌ Corpus directory not found: {CORPUS_DOCS_DIR}")
        return []

    all_documents = []

    # Find all markdown files
    md_files = list(CORPUS_DOCS_DIR.rglob("*.md"))

    print(f"📚 Found {len(md_files)} markdown files")

    for md_file in md_files:
        print(f"   Processing: {md_file.relative_to(CORPUS_DOCS_DIR)}")

        try:
            docs = parse_markdown_file(md_file)

            for doc_id, text, tags in docs:
                metadata = {
                    "source_file": str(md_file.relative_to(CORPUS_DOCS_DIR)),
                    "document_type": "faq"
                }
                all_documents.append((doc_id, text, tags, metadata))

            print(f"      ✓ Extracted {len(docs)} sections")

        except Exception as e:
            print(f"      ✗ Error processing {md_file.name}: {e}")

    return all_documents


def update_metadata(document_count: int, tags: List[str]) -> None:
    """Update corpus metadata.json with new statistics."""
    if not METADATA_PATH.exists():
        print("⚠️  metadata.json not found, skipping update")
        return

    try:
        with open(METADATA_PATH, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        # Update fields
        metadata["document_count"] = document_count
        metadata["tags"] = sorted(list(set(tags)))

        # Update timestamp
        from datetime import datetime
        metadata["last_updated"] = datetime.utcnow().isoformat() + "Z"

        with open(METADATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        print(f"✓ Updated metadata.json")

    except Exception as e:
        print(f"⚠️  Failed to update metadata: {e}")


def main():
    """Main seeding function."""
    print("🌱 Seeding corpus into vector store...\n")

    # Load all documents
    documents = load_all_documents()

    if not documents:
        print("\n❌ No documents found to seed")
        return

    print(f"\n📊 Total sections to load: {len(documents)}")

    # Get vector store
    store = get_vector_store()

    # Batch upsert
    print("\n💾 Loading into vector store...")

    try:
        store.batch_upsert(documents)
        print(f"✓ Successfully loaded {len(documents)} documents")

        # Collect all unique tags
        all_tags = []
        for _, _, tags, _ in documents:
            all_tags.extend(tags)

        # Update metadata
        update_metadata(len(documents), all_tags)

        # Print statistics
        print(f"\n📈 Corpus Statistics:")
        print(f"   Total documents: {store.count()}")
        print(f"   Unique tags: {len(set(all_tags))}")
        print(f"   Tags: {', '.join(sorted(set(all_tags)))}")

    except Exception as e:
        print(f"\n❌ Error loading documents: {e}")
        return

    print("\n✅ Corpus seeding complete!")


if __name__ == "__main__":
    main()
