"""
Unit tests for the Dynamic Model Router.
"""

from backend.agents.model_router import MODEL_REGISTRY, ModelRouter


def test_model_registry_specs() -> None:
    """Verify built-in models exist in registry."""
    assert "gpt-4o" in MODEL_REGISTRY
    assert "claude-sonnet-4-20250514" in MODEL_REGISTRY
    assert "gemini-1.5-pro" in MODEL_REGISTRY


def test_model_selection_fallback() -> None:
    """Test model router selection logic under defaults."""
    router = ModelRouter()
    # When keys are dummy, selection falls back to available models or raises ModelRoutingError gracefully
    try:
        spec = router.select_model(tier="small")
        assert spec is not None
    except Exception as e:
        assert "No models available" in str(e) or "ModelRoutingError" in str(type(e))
