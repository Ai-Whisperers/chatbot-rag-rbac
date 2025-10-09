"""
Simple tests for Stage 0 critical bug fixes (no chromadb required).

Tests verify the fixes work without requiring full environment setup.
"""

import pytest
import os
from pydantic import ValidationError


class TestBug1ConfigIntegration:
    """Test that config values are properly exposed."""

    def test_similarity_threshold_exists_in_config(self):
        """Test that SIMILARITY_THRESHOLD is defined in config."""
        from app.config import SIMILARITY_THRESHOLD
        assert isinstance(SIMILARITY_THRESHOLD, float)
        assert 0.0 <= SIMILARITY_THRESHOLD <= 1.0

    def test_similarity_threshold_can_be_imported_in_main(self):
        """Test that main.py can import SIMILARITY_THRESHOLD."""
        # This import would fail if not in main.py imports
        import app.main as main_module

        # Check if SIMILARITY_THRESHOLD is in the module's imports
        import inspect
        source = inspect.getsource(main_module)
        assert "SIMILARITY_THRESHOLD" in source


class TestBug2DistanceFormula:
    """Test distance-to-similarity conversion without chromadb."""

    @staticmethod
    def distance_to_similarity_correct(distance: float) -> float:
        """Correct cosine distance to similarity formula."""
        return 1.0 - (distance / 2.0)

    @staticmethod
    def distance_to_similarity_wrong(distance: float) -> float:
        """Wrong L2 distance formula (the bug)."""
        return 1.0 / (1.0 + distance)

    def test_cosine_formula_at_zero(self):
        """Test that distance 0 gives similarity 1.0."""
        correct = self.distance_to_similarity_correct(0.0)
        assert correct == 1.0

    def test_cosine_formula_at_max(self):
        """Test that distance 2 gives similarity 0.0."""
        correct = self.distance_to_similarity_correct(2.0)
        assert correct == 0.0

    def test_cosine_formula_at_orthogonal(self):
        """Test that distance 1 gives similarity 0.5."""
        correct = self.distance_to_similarity_correct(1.0)
        assert correct == 0.5

    def test_formulas_differ(self):
        """Test that correct and wrong formulas give different results."""
        # At distance 0.5, the two formulas give different results
        correct = self.distance_to_similarity_correct(0.5)
        wrong = self.distance_to_similarity_wrong(0.5)

        # Cosine: 1 - (0.5/2) = 0.75
        # L2: 1 / (1 + 0.5) = 0.667
        assert abs(correct - 0.75) < 0.001
        assert abs(wrong - 0.667) < 0.001
        assert correct != wrong

    def test_retrieval_module_has_distance_to_similarity(self):
        """Test that retrieval module has distance_to_similarity method."""
        # Import only the module-level code, not VectorStore class
        import app.retrieval

        # Check that the source contains the correct formula
        import inspect
        source = inspect.getsource(app.retrieval)

        # Should contain the correct formula
        assert "1.0 - (distance / 2.0)" in source

        # Should NOT contain the old wrong formula
        assert source.count("1.0 / (1.0 + distance)") == 0, "Old L2 formula still present!"


class TestBug3CachedQueryImport:
    """Test that cached_query is imported in main.py."""

    def test_cached_query_exists_in_retrieval(self):
        """Test that cached_query function exists."""
        import app.retrieval
        assert hasattr(app.retrieval, 'cached_query')
        assert callable(app.retrieval.cached_query)

    def test_cached_query_imported_in_main(self):
        """Test that main.py imports cached_query."""
        import app.main as main_module
        import inspect

        # Check source code for import
        source = inspect.getsource(main_module)
        assert "cached_query" in source, "cached_query not found in main.py"

        # Check specifically that it's imported from retrieval
        assert "from app.retrieval import" in source and "cached_query" in source

    def test_cached_query_used_in_ask_endpoint(self):
        """Test that ask_question uses cached_query."""
        import app.main as main_module
        import inspect

        # Get ask_question function source
        ask_fn = getattr(main_module, 'ask_question', None)
        assert ask_fn is not None, "ask_question function not found"

        source = inspect.getsource(ask_fn)
        # Should call cached_query
        assert "cached_query" in source, "cached_query not used in ask_question"


class TestBug4InputLengthValidation:
    """Test input length validation in Pydantic models."""

    def test_max_question_length_config_exists(self):
        """Test that MAX_QUESTION_LENGTH config exists."""
        from app.config import MAX_QUESTION_LENGTH
        assert isinstance(MAX_QUESTION_LENGTH, int)
        assert MAX_QUESTION_LENGTH > 0

    def test_max_document_length_config_exists(self):
        """Test that MAX_DOCUMENT_LENGTH config exists."""
        from app.config import MAX_DOCUMENT_LENGTH
        assert isinstance(MAX_DOCUMENT_LENGTH, int)
        assert MAX_DOCUMENT_LENGTH > 0

    def test_question_model_enforces_max_length(self):
        """Test that AskQuestion model rejects too-long questions."""
        from app.models import AskQuestion
        from app.config import MAX_QUESTION_LENGTH

        # Create question that exceeds max length
        long_question = "A" * (MAX_QUESTION_LENGTH + 100)

        with pytest.raises(ValidationError) as exc_info:
            AskQuestion(question=long_question, scope="public")

        # Verify it's a validation error about length
        assert exc_info.value.errors()

    def test_question_model_accepts_valid_length(self):
        """Test that AskQuestion accepts questions within limit."""
        from app.models import AskQuestion
        from app.config import MAX_QUESTION_LENGTH

        # Create valid question
        valid_question = "A" * (MAX_QUESTION_LENGTH - 50)

        # Should not raise
        q = AskQuestion(question=valid_question, scope="public")
        assert q.question == valid_question

    def test_document_model_enforces_max_length(self):
        """Test that UpsertDocument model rejects too-long documents."""
        from app.models import UpsertDocument
        from app.config import MAX_DOCUMENT_LENGTH

        # Create document that exceeds max length
        long_text = "A" * (MAX_DOCUMENT_LENGTH + 100)

        with pytest.raises(ValidationError) as exc_info:
            UpsertDocument(id="test", text=long_text, tags=["faq"])

        # Verify it's a validation error
        assert exc_info.value.errors()

    def test_document_model_accepts_valid_length(self):
        """Test that UpsertDocument accepts documents within limit."""
        from app.models import UpsertDocument
        from app.config import MAX_DOCUMENT_LENGTH

        # Create valid document
        valid_text = "A" * (MAX_DOCUMENT_LENGTH - 100)

        # Should not raise
        doc = UpsertDocument(id="test", text=valid_text, tags=["faq"])
        assert doc.text == valid_text

    def test_empty_question_rejected(self):
        """Test that empty questions are rejected."""
        from app.models import AskQuestion

        with pytest.raises(ValidationError):
            AskQuestion(question="", scope="public")

    def test_empty_document_rejected(self):
        """Test that empty documents are rejected."""
        from app.models import UpsertDocument

        with pytest.raises(ValidationError):
            UpsertDocument(id="test", text="", tags=["faq"])

    def test_whitespace_only_question_rejected(self):
        """Test that whitespace-only questions are rejected."""
        from app.models import AskQuestion

        # The validator should strip whitespace, leaving empty string
        with pytest.raises(ValidationError):
            AskQuestion(question="   ", scope="public")


class TestStage0AllFixesIntegrated:
    """Integration tests confirming all fixes are in place."""

    def test_all_config_imports_present(self):
        """Test that all required config values are imported in main.py."""
        import app.main as main_module
        import inspect

        source = inspect.getsource(main_module)

        # All these should be imported
        required_imports = [
            "SIMILARITY_THRESHOLD",
            "cached_query"
        ]

        for imp in required_imports:
            assert imp in source, f"{imp} not found in main.py"

    def test_config_values_have_sensible_defaults(self):
        """Test that all config values have reasonable defaults."""
        from app.config import (
            SIMILARITY_THRESHOLD,
            MAX_QUESTION_LENGTH,
            MAX_DOCUMENT_LENGTH
        )

        # Test similarity threshold is reasonable
        assert 0.0 <= SIMILARITY_THRESHOLD <= 1.0
        assert SIMILARITY_THRESHOLD >= 0.5  # Not too low

        # Test length limits are reasonable
        assert 100 <= MAX_QUESTION_LENGTH <= 10000
        assert 1000 <= MAX_DOCUMENT_LENGTH <= 100000

    def test_models_use_config_not_hardcoded(self):
        """Test that models import config values instead of hardcoding."""
        from app import models
        import inspect

        source = inspect.getsource(models)

        # Should import from config
        assert "from app.config import" in source
        assert "MAX_QUESTION_LENGTH" in source
        assert "MAX_DOCUMENT_LENGTH" in source


def test_stage0_complete():
    """Meta-test: verify all Stage 0 fixes are implemented."""

    # Bug 1: SIMILARITY_THRESHOLD imported in main
    from app.main import SIMILARITY_THRESHOLD
    assert SIMILARITY_THRESHOLD is not None

    # Bug 2: Correct formula exists in retrieval
    import app.retrieval
    import inspect
    source = inspect.getsource(app.retrieval)
    assert "1.0 - (distance / 2.0)" in source

    # Bug 3: cached_query imported in main
    from app.main import cached_query
    assert cached_query is not None

    # Bug 4: MAX_QUESTION_LENGTH and MAX_DOCUMENT_LENGTH exist
    from app.config import MAX_QUESTION_LENGTH, MAX_DOCUMENT_LENGTH
    assert MAX_QUESTION_LENGTH > 0
    assert MAX_DOCUMENT_LENGTH > 0

    print("✅ All Stage 0 fixes are implemented!")


if __name__ == "__main__":
    # Run quick verification
    test_stage0_complete()
