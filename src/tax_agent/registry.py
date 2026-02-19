"""Centralized service registry for lazy-initialized singletons.

Replaces scattered module-level globals with a single registry that supports
reset() for test isolation and override() for injecting test doubles.
"""

from __future__ import annotations

import threading
from typing import Any


class ServiceRegistry:
    """Thread-safe lazy-initialized service registry.

    Each service is created on first access and cached. Services can be
    reset (clearing the cached instance) or overridden (injecting a
    test double that takes priority over lazy initialization).
    """

    _SERVICES = frozenset({
        "config", "agent", "database", "tax_context", "sdk_agent", "compat_agent",
    })

    def __init__(self) -> None:
        self._instances: dict[str, Any] = {}
        self._overrides: dict[str, Any] = {}
        self._lock = threading.Lock()

    # -- lazy-init properties ------------------------------------------------

    @property
    def config(self):
        return self._get("config")

    @property
    def agent(self):
        return self._get("agent")

    @property
    def database(self):
        return self._get("database")

    @property
    def tax_context(self):
        return self._get("tax_context")

    @property
    def sdk_agent(self):
        return self._get("sdk_agent")

    @property
    def compat_agent(self):
        return self._get("compat_agent")

    # -- public API ----------------------------------------------------------

    def reset(self, *names: str) -> None:
        """Reset services, clearing cached instances and overrides.

        With no arguments, resets *all* services. Pass service names to
        selectively reset only those (e.g. ``registry.reset("config")``).
        """
        targets = set(names) if names else self._SERVICES
        unknown = targets - self._SERVICES
        if unknown:
            raise ValueError(f"Unknown service(s): {unknown}")
        with self._lock:
            for name in targets:
                self._instances.pop(name, None)
                self._overrides.pop(name, None)

    def override(self, name: str, instance: Any) -> None:
        """Inject a test double for *name*.

        The override takes priority over lazy initialization until
        ``reset()`` clears it.
        """
        if name not in self._SERVICES:
            raise ValueError(f"Unknown service: {name!r}")
        with self._lock:
            self._overrides[name] = instance
            self._instances.pop(name, None)

    # -- internal ------------------------------------------------------------

    def _get(self, name: str) -> Any:
        # Fast path: already cached (no lock needed for dict reads in CPython).
        if name in self._overrides:
            return self._overrides[name]
        if name in self._instances:
            return self._instances[name]

        with self._lock:
            # Double-check after acquiring lock.
            if name in self._overrides:
                return self._overrides[name]
            if name in self._instances:
                return self._instances[name]

            instance = self._create(name)
            self._instances[name] = instance
            return instance

    def _create(self, name: str) -> Any:
        """Lazily import and instantiate the service class.

        Imports are done inside this method to avoid circular imports
        at module load time.
        """
        if name == "config":
            from tax_agent.config import Config
            return Config()

        if name == "agent":
            from tax_agent.agent import TaxAgent
            return TaxAgent()

        if name == "database":
            from tax_agent.storage.database import TaxDatabase
            return TaxDatabase()

        if name == "tax_context":
            from tax_agent.context import TaxContext
            return TaxContext()

        if name == "sdk_agent":
            from tax_agent.agent_sdk import TaxAgentSDK
            return TaxAgentSDK()

        if name == "compat_agent":
            from tax_agent.agent_compat import CompatibleAgent
            return CompatibleAgent()

        raise ValueError(f"Unknown service: {name!r}")


# Module-level singleton registry
_registry = ServiceRegistry()


def get_registry() -> ServiceRegistry:
    """Return the global ServiceRegistry instance."""
    return _registry
