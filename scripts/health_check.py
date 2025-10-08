#!/usr/bin/env python
"""
Health check script for FAQ bot.
Verifies all components are working correctly.
"""

import sys
import httpx
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import API_HOST, API_PORT, MODEL_ENDPOINT


def check_api_health() -> bool:
    """Check if API is responding."""
    print("🏥 Checking API health...")

    try:
        url = f"http://{API_HOST}:{API_PORT}/health"
        response = httpx.get(url, timeout=5.0)

        if response.status_code == 200:
            data = response.json()
            print(f"   ✓ API is healthy")
            print(f"      Version: {data.get('version', 'unknown')}")
            print(f"      Corpus loaded: {data.get('corpus_loaded', False)}")
            print(f"      Documents: {data.get('collection_count', 0)}")
            print(f"      Model available: {data.get('model_available', False)}")
            return True
        else:
            print(f"   ✗ API returned status {response.status_code}")
            return False

    except httpx.ConnectError:
        print(f"   ✗ Cannot connect to API at {API_HOST}:{API_PORT}")
        print(f"      Is the server running?")
        return False

    except Exception as e:
        print(f"   ✗ Error checking API: {e}")
        return False


def check_ollama() -> bool:
    """Check if Ollama is accessible."""
    print("\n🤖 Checking Ollama...")

    try:
        response = httpx.get(f"{MODEL_ENDPOINT}/api/tags", timeout=5.0)

        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])

            print(f"   ✓ Ollama is accessible")
            print(f"      Available models: {len(models)}")

            if models:
                for model in models[:5]:  # Show first 5
                    print(f"         - {model.get('name', 'unknown')}")

            return True
        else:
            print(f"   ✗ Ollama returned status {response.status_code}")
            return False

    except httpx.ConnectError:
        print(f"   ✗ Cannot connect to Ollama at {MODEL_ENDPOINT}")
        print(f"      Is Ollama running? (ollama serve)")
        return False

    except Exception as e:
        print(f"   ✗ Error checking Ollama: {e}")
        return False


def test_question() -> bool:
    """Test asking a sample question."""
    print("\n💬 Testing question answering...")

    try:
        url = f"http://{API_HOST}:{API_PORT}/ask"
        payload = {
            "question": "What are your support hours?",
            "scope": "public"
        }

        response = httpx.post(url, json=payload, timeout=30.0)

        if response.status_code == 200:
            data = response.json()
            answer = data.get("answer", "")

            print(f"   ✓ Question answered successfully")
            print(f"      Q: {payload['question']}")
            print(f"      A: {answer[:100]}{'...' if len(answer) > 100 else ''}")
            print(f"      Retrieved: {data.get('retrieved_count', 0)} docs")
            print(f"      Filtered: {data.get('filtered_count', 0)} docs")

            return True
        else:
            print(f"   ✗ Question failed with status {response.status_code}")
            return False

    except Exception as e:
        print(f"   ✗ Error testing question: {e}")
        return False


def main():
    """Run all health checks."""
    print("🔍 Running health checks...\n")

    checks = [
        ("API", check_api_health),
        ("Ollama", check_ollama),
        ("Q&A", test_question),
    ]

    results = {}

    for name, check_fn in checks:
        try:
            results[name] = check_fn()
        except Exception as e:
            print(f"\n❌ Unexpected error in {name} check: {e}")
            results[name] = False

    # Summary
    print("\n" + "="*50)
    print("📊 Health Check Summary")
    print("="*50)

    all_passed = True

    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("="*50)

    if all_passed:
        print("✅ All checks passed!")
        return 0
    else:
        print("❌ Some checks failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
