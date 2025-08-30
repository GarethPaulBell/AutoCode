"""Test for ell installation and basic functionality."""

import pytest

def test_ell_import():
    """Test that ell can be imported."""
    try:
        import ell
        assert ell is not None
    except ImportError:
        pytest.fail("ell is not installed")

def test_ell_wrappers_import():
    """Test that ell_wrappers can be imported."""
    try:
        from src.autocode.ell_wrappers import generate_julia_function, write_test_case
        assert generate_julia_function is not None
        assert write_test_case is not None
    except ImportError as e:
        pytest.fail(f"ell_wrappers import failed: {e}")

def test_ell_decorators():
    """Test that ell decorators are available."""
    import ell
    # Check if ell has the expected attributes
    assert hasattr(ell, 'complex')
    assert hasattr(ell, 'simple')
