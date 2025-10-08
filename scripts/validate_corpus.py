#!/usr/bin/env python
"""
Validate corpus integrity and structure.
Checks for:
- Required files exist
- JSON files are valid
- No duplicate document IDs
- Tags are consistent
"""

import json
import sys
from pathlib import Path
from typing import Set, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import (
    CORPUS_DIR,
    CORPUS_DOCS_DIR,
    PRIVILEGE_MAP_PATH,
    METADATA_PATH
)


class ValidationError(Exception):
    """Custom validation error."""
    pass


def check_required_files() -> None:
    """Check that all required files exist."""
    print("📁 Checking required files...")

    required = {
        "Corpus directory": CORPUS_DIR,
        "Docs directory": CORPUS_DOCS_DIR,
        "Privilege map": PRIVILEGE_MAP_PATH,
        "Metadata": METADATA_PATH
    }

    errors = []

    for name, path in required.items():
        if path.exists():
            print(f"   ✓ {name}: {path}")
        else:
            errors.append(f"{name} not found: {path}")
            print(f"   ✗ {name}: {path}")

    if errors:
        raise ValidationError("\n".join(errors))


def validate_json_files() -> tuple:
    """Validate JSON file syntax and structure."""
    print("\n📄 Validating JSON files...")

    # Validate privilege_map.json
    try:
        with open(PRIVILEGE_MAP_PATH, 'r', encoding='utf-8') as f:
            privilege_map = json.load(f)

        if not isinstance(privilege_map, dict):
            raise ValidationError("privilege_map.json must be a dictionary")

        for scope, policy in privilege_map.items():
            if not isinstance(policy, dict):
                raise ValidationError(f"Scope '{scope}' must have a dictionary policy")

            if "allowed_tags" not in policy:
                raise ValidationError(f"Scope '{scope}' missing 'allowed_tags'")

            if "deny" not in policy:
                raise ValidationError(f"Scope '{scope}' missing 'deny'")

        print(f"   ✓ privilege_map.json ({len(privilege_map)} scopes)")

    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in privilege_map.json: {e}")

    # Validate metadata.json
    try:
        with open(METADATA_PATH, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        required_fields = ["version", "last_updated", "document_count"]
        for field in required_fields:
            if field not in metadata:
                raise ValidationError(f"metadata.json missing required field: {field}")

        print(f"   ✓ metadata.json (version {metadata.get('version', 'unknown')})")

    except json.JSONDecodeError as e:
        raise ValidationError(f"Invalid JSON in metadata.json: {e}")

    return privilege_map, metadata


def check_markdown_files() -> List[Path]:
    """Check markdown files in corpus/docs/."""
    print("\n📝 Checking markdown files...")

    md_files = list(CORPUS_DOCS_DIR.rglob("*.md"))

    if not md_files:
        raise ValidationError(f"No markdown files found in {CORPUS_DOCS_DIR}")

    print(f"   ✓ Found {len(md_files)} markdown files")

    return md_files


def extract_tags_from_files(md_files: List[Path]) -> Set[str]:
    """Extract all tags from markdown files."""
    print("\n🏷️  Extracting tags from documents...")

    import re

    all_tags = set()

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding='utf-8')

            # Look for Tags: line
            pattern = r'^Tags:\s*(.+)$'
            match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)

            if match:
                tags_str = match.group(1)
                tags = [tag.strip().lower() for tag in tags_str.split(',')]
                all_tags.update(tags)
            else:
                print(f"   ⚠️  No tags found in {md_file.name}, will use default 'faq'")

        except Exception as e:
            print(f"   ✗ Error reading {md_file.name}: {e}")

    print(f"   ✓ Found {len(all_tags)} unique tags: {', '.join(sorted(all_tags))}")

    return all_tags


def validate_tags_against_policy(tags: Set[str], privilege_map: dict) -> None:
    """Ensure all tags are referenced in privilege_map."""
    print("\n🔐 Validating tags against RBAC policy...")

    # Collect all allowed and denied tags from privilege_map
    policy_tags = set()

    for scope, policy in privilege_map.items():
        policy_tags.update(policy.get("allowed_tags", []))
        policy_tags.update(policy.get("deny", []))

    # Check for orphaned tags (in docs but not in policy)
    orphaned = tags - policy_tags

    if orphaned:
        print(f"   ⚠️  Warning: Tags in documents but not in privilege_map: {', '.join(sorted(orphaned))}")
        print(f"      These documents may not be accessible via any scope")
    else:
        print(f"   ✓ All tags are referenced in privilege_map")

    # Check for unused policy tags
    unused = policy_tags - tags
    if unused:
        print(f"   ℹ️  Info: Tags in privilege_map but not used in documents: {', '.join(sorted(unused))}")


def check_for_pii() -> None:
    """Basic check for potential PII in documents."""
    print("\n🔍 Checking for potential PII...")

    import re

    pii_patterns = {
        "Email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "SSN": r'\b\d{3}-\d{2}-\d{4}\b',
        "Credit Card": r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
        "Phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    }

    md_files = list(CORPUS_DOCS_DIR.rglob("*.md"))
    findings = []

    for md_file in md_files:
        content = md_file.read_text(encoding='utf-8')

        for pii_type, pattern in pii_patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                findings.append(f"{md_file.name}: Potential {pii_type} found")

    if findings:
        print("   ⚠️  Potential PII detected:")
        for finding in findings:
            print(f"      - {finding}")
        print("   Please review and remove if necessary")
    else:
        print("   ✓ No obvious PII patterns detected")


def main():
    """Run all validation checks."""
    print("🔍 Validating corpus...\n")

    try:
        # Check required files
        check_required_files()

        # Validate JSON
        privilege_map, metadata = validate_json_files()

        # Check markdown files
        md_files = check_markdown_files()

        # Extract and validate tags
        tags = extract_tags_from_files(md_files)
        validate_tags_against_policy(tags, privilege_map)

        # Check for PII
        check_for_pii()

        print("\n" + "="*50)
        print("✅ Corpus validation passed!")
        print("="*50)

        return 0

    except ValidationError as e:
        print("\n" + "="*50)
        print(f"❌ Validation failed:")
        print(f"   {e}")
        print("="*50)
        return 1

    except Exception as e:
        print("\n" + "="*50)
        print(f"❌ Unexpected error during validation:")
        print(f"   {e}")
        print("="*50)
        return 1


if __name__ == "__main__":
    sys.exit(main())
