"""Tests for the centralized ServiceRegistry."""

import threading
from unittest.mock import MagicMock

import pytest

from tax_agent.registry import ServiceRegistry, get_registry


class TestServiceRegistry:
    """Tests for ServiceRegistry lazy init, reset, and override."""

    def test_get_registry_returns_singleton(self):
        assert get_registry() is get_registry()

    def test_lazy_init_config(self):
        registry = ServiceRegistry()
        cfg = registry.config
        assert cfg is not None
        # Second access returns the same instance.
        assert registry.config is cfg

    def test_lazy_init_database(self):
        registry = ServiceRegistry()
        # TaxDatabase requires a configured password, so test via override.
        fake_db = MagicMock()
        registry.override("database", fake_db)
        assert registry.database is fake_db

    def test_lazy_init_tax_context(self):
        registry = ServiceRegistry()
        ctx = registry.tax_context
        assert ctx is not None
        assert registry.tax_context is ctx

    def test_reset_all_clears_cached_instances(self):
        registry = ServiceRegistry()
        cfg1 = registry.config
        registry.reset()
        cfg2 = registry.config
        assert cfg1 is not cfg2

    def test_reset_selective(self):
        registry = ServiceRegistry()
        cfg1 = registry.config
        ctx1 = registry.tax_context
        registry.reset("config")
        cfg2 = registry.config
        ctx2 = registry.tax_context
        assert cfg1 is not cfg2
        assert ctx1 is ctx2

    def test_reset_unknown_service_raises(self):
        registry = ServiceRegistry()
        with pytest.raises(ValueError, match="Unknown service"):
            registry.reset("nonexistent")

    def test_override(self):
        registry = ServiceRegistry()
        fake_config = MagicMock()
        registry.override("config", fake_config)
        assert registry.config is fake_config

    def test_override_takes_priority_over_cached(self):
        registry = ServiceRegistry()
        _ = registry.config  # cache real instance
        fake = MagicMock()
        registry.override("config", fake)
        assert registry.config is fake

    def test_override_unknown_service_raises(self):
        registry = ServiceRegistry()
        with pytest.raises(ValueError, match="Unknown service"):
            registry.override("nope", MagicMock())

    def test_reset_clears_override(self):
        registry = ServiceRegistry()
        fake = MagicMock()
        registry.override("config", fake)
        registry.reset("config")
        cfg = registry.config
        assert cfg is not fake

    def test_thread_safety(self):
        """Multiple threads requesting the same service get the same instance."""
        registry = ServiceRegistry()
        results = []
        barrier = threading.Barrier(4)

        def worker():
            barrier.wait()
            results.append(id(registry.config))

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(results)) == 1, "All threads should get the same instance"
