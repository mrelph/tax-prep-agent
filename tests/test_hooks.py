"""Tests for hooks.py (async hooks, mocked config)."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from tax_agent.hooks import (
    _tool_counters,
    audit_log_hook,
    ein_redaction_hook,
    get_minimal_hooks,
    get_tax_hooks,
    rate_limit_hook,
    reset_rate_limits,
    sensitive_data_guard,
    ssn_redaction_hook,
    web_access_guard,
)


@pytest.fixture(autouse=True)
def clean_counters():
    """Reset rate limit counters before each test."""
    reset_rate_limits()
    yield
    reset_rate_limits()


@pytest.fixture
def mock_config():
    """Mock get_config for hooks."""
    with patch("tax_agent.hooks.get_config") as mock:
        config = MagicMock()
        config.data_dir = "/tmp/tax-data"
        config.config_dir = "/tmp/tax-config"
        config.agent_sdk_allow_web = True
        config.get.return_value = {}
        mock.return_value = config
        yield config


class TestSSNRedactionHook:
    """Tests for ssn_redaction_hook()."""

    @pytest.mark.asyncio
    async def test_redacts_ssn_from_tool_result(self):
        input_data = {
            "tool_name": "Read",
            "tool_result": "Employee SSN: 123-45-6789",
        }
        result = await ssn_redaction_hook(input_data, "id1", None)
        assert "updatedResult" in result.get("hookSpecificOutput", {})
        assert "123-45-6789" not in result["hookSpecificOutput"]["updatedResult"]
        assert "[SSN REDACTED]" in result["hookSpecificOutput"]["updatedResult"]

    @pytest.mark.asyncio
    async def test_redacts_spaced_ssn(self):
        input_data = {
            "tool_name": "Read",
            "tool_result": "SSN: 123 45 6789",
        }
        result = await ssn_redaction_hook(input_data, "id1", None)
        assert "[SSN REDACTED]" in result["hookSpecificOutput"]["updatedResult"]

    @pytest.mark.asyncio
    async def test_no_ssn_returns_empty(self):
        input_data = {
            "tool_name": "Read",
            "tool_result": "No sensitive data here",
        }
        result = await ssn_redaction_hook(input_data, "id1", None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_skips_pre_tool_use(self):
        """Should only run on PostToolUse (when tool_result present)."""
        input_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test"},
        }
        result = await ssn_redaction_hook(input_data, "id1", None)
        assert result == {}


class TestEINRedactionHook:
    """Tests for ein_redaction_hook()."""

    @pytest.mark.asyncio
    async def test_redacts_when_configured(self, mock_config):
        mock_config.get.return_value = True  # redact_ein = True
        input_data = {
            "tool_name": "Read",
            "tool_result": "EIN: 12-3456789",
        }
        result = await ein_redaction_hook(input_data, "id1", None)
        assert "[EIN REDACTED]" in result["hookSpecificOutput"]["updatedResult"]

    @pytest.mark.asyncio
    async def test_skips_when_not_configured(self, mock_config):
        mock_config.get.return_value = False  # redact_ein = False
        input_data = {
            "tool_name": "Read",
            "tool_result": "EIN: 12-3456789",
        }
        result = await ein_redaction_hook(input_data, "id1", None)
        assert result == {}


class TestRateLimitHook:
    """Tests for rate_limit_hook()."""

    @pytest.mark.asyncio
    async def test_increments_counters(self, mock_config):
        input_data = {"tool_name": "Read"}
        await rate_limit_hook(input_data, "id1", None)
        assert _tool_counters["Read"] == 1
        assert _tool_counters["_total"] == 1

    @pytest.mark.asyncio
    async def test_allows_under_limit(self, mock_config):
        input_data = {"tool_name": "WebSearch"}
        result = await rate_limit_hook(input_data, "id1", None)
        assert result == {} or "permissionDecision" not in result.get("hookSpecificOutput", {})

    @pytest.mark.asyncio
    async def test_denies_over_tool_limit(self, mock_config):
        # Exhaust WebSearch limit (default 10)
        for i in range(10):
            await rate_limit_hook({"tool_name": "WebSearch"}, f"id{i}", None)

        # 11th call should be denied
        result = await rate_limit_hook({"tool_name": "WebSearch"}, "id11", None)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    @pytest.mark.asyncio
    async def test_denies_over_total_limit(self, mock_config):
        # Exhaust total limit (default 100)
        for i in range(100):
            await rate_limit_hook({"tool_name": "Read"}, f"id{i}", None)

        result = await rate_limit_hook({"tool_name": "Read"}, "id101", None)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    @pytest.mark.asyncio
    async def test_skips_post_tool_use(self, mock_config):
        input_data = {"tool_name": "Read", "tool_result": "some output"}
        result = await rate_limit_hook(input_data, "id1", None)
        assert result == {}

    def test_reset_clears_counters(self):
        _tool_counters["Read"] = 50
        _tool_counters["_total"] = 50
        reset_rate_limits()
        assert len(_tool_counters) == 0


class TestSensitiveDataGuard:
    """Tests for sensitive_data_guard()."""

    @pytest.mark.asyncio
    async def test_allows_tmp_directory(self, mock_config):
        input_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/tax-docs/w2.pdf"},
        }
        result = await sensitive_data_guard(input_data, "id1", None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_blocks_outside_allowed(self, mock_config):
        input_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/etc/passwd"},
        }
        result = await sensitive_data_guard(input_data, "id1", None)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    @pytest.mark.asyncio
    async def test_ignores_non_file_tools(self, mock_config):
        input_data = {
            "tool_name": "WebSearch",
            "tool_input": {"query": "IRS rules 2024"},
        }
        result = await sensitive_data_guard(input_data, "id1", None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_allows_data_dir(self, mock_config):
        mock_config.data_dir = "/home/user/.tax-agent/data"
        input_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/home/user/.tax-agent/data/docs/w2.pdf"},
        }
        result = await sensitive_data_guard(input_data, "id1", None)
        assert result == {}


class TestWebAccessGuard:
    """Tests for web_access_guard()."""

    @pytest.mark.asyncio
    async def test_allows_when_enabled(self, mock_config):
        mock_config.agent_sdk_allow_web = True
        input_data = {"tool_name": "WebSearch"}
        result = await web_access_guard(input_data, "id1", None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_blocks_when_disabled(self, mock_config):
        mock_config.agent_sdk_allow_web = False
        input_data = {"tool_name": "WebSearch"}
        result = await web_access_guard(input_data, "id1", None)
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    @pytest.mark.asyncio
    async def test_ignores_non_web_tools(self, mock_config):
        mock_config.agent_sdk_allow_web = False
        input_data = {"tool_name": "Read"}
        result = await web_access_guard(input_data, "id1", None)
        assert result == {}


class TestAuditLogHook:
    """Tests for audit_log_hook()."""

    @pytest.mark.asyncio
    async def test_pre_tool_use_returns_empty(self):
        input_data = {
            "tool_name": "Read",
            "tool_input": {"file_path": "/tmp/test.txt"},
        }
        result = await audit_log_hook(input_data, "id1", None)
        assert result == {}

    @pytest.mark.asyncio
    async def test_post_tool_use_returns_empty(self):
        input_data = {
            "tool_name": "Read",
            "tool_result": "file contents here",
        }
        result = await audit_log_hook(input_data, "id1", None)
        assert result == {}


class TestGetHooks:
    """Tests for get_tax_hooks() and get_minimal_hooks()."""

    def test_tax_hooks_structure(self):
        hooks = get_tax_hooks()
        assert "PreToolUse" in hooks
        assert "PostToolUse" in hooks
        assert len(hooks["PreToolUse"]) == 3
        assert len(hooks["PostToolUse"]) == 4

    def test_tax_hooks_contains_guards(self):
        hooks = get_tax_hooks()
        assert sensitive_data_guard in hooks["PreToolUse"]
        assert web_access_guard in hooks["PreToolUse"]

    def test_tax_hooks_contains_redaction(self):
        hooks = get_tax_hooks()
        assert ssn_redaction_hook in hooks["PostToolUse"]
        assert ein_redaction_hook in hooks["PostToolUse"]

    def test_minimal_hooks_structure(self):
        hooks = get_minimal_hooks()
        assert "PreToolUse" in hooks
        assert "PostToolUse" in hooks
        assert len(hooks["PreToolUse"]) == 1
        assert len(hooks["PostToolUse"]) == 1

    def test_minimal_hooks_has_essentials(self):
        hooks = get_minimal_hooks()
        assert sensitive_data_guard in hooks["PreToolUse"]
        assert ssn_redaction_hook in hooks["PostToolUse"]
