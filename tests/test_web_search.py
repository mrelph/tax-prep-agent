"""Tests for Brave Search web search client."""

import json
from unittest.mock import MagicMock, patch

import pytest

from tax_agent.research.web_search import (
    BRAVE_SEARCH_URL,
    BraveSearchClient,
    BraveSearchError,
)
from tax_agent.research.tax_researcher import TaxResearcher


@pytest.fixture
def mock_config():
    """Mock config to avoid keyring access."""
    with patch("tax_agent.config.get_config") as mock:
        config = MagicMock()
        config.get_brave_api_key.return_value = None
        mock.return_value = config
        yield config


@pytest.fixture
def client():
    """Create a BraveSearchClient with a test API key."""
    return BraveSearchClient(api_key="test_brave_key")


@pytest.fixture
def mock_response():
    """Create a mock Brave Search API response."""
    return {
        "web": {
            "results": [
                {
                    "title": "IRS Revenue Procedure 2023-34",
                    "url": "https://www.irs.gov/rev-proc-2023-34",
                    "description": "Provides inflation-adjusted items for 2024 tax year.",
                },
                {
                    "title": "2024 Tax Brackets and Rates",
                    "url": "https://www.irs.gov/newsroom/tax-brackets-2024",
                    "description": "The IRS announced the annual inflation adjustments.",
                },
                {
                    "title": "401k Limits for 2024",
                    "url": "https://www.irs.gov/retirement/401k-limit",
                    "description": "The 401(k) contribution limit increases to $23,000.",
                },
            ]
        }
    }


class TestBraveSearchClient:
    """Tests for BraveSearchClient."""

    def test_requires_api_key(self, mock_config):
        """Client raises error when no API key is available."""
        with pytest.raises(BraveSearchError, match="not configured"):
            BraveSearchClient()

    def test_accepts_explicit_api_key(self):
        """Client accepts an explicit API key."""
        client = BraveSearchClient(api_key="test_key_123")
        assert client._api_key == "test_key_123"

    def test_env_var_api_key(self, mock_config):
        """Client reads API key from environment variable."""
        with patch.dict("os.environ", {"BRAVE_API_KEY": "env_key_456"}):
            client = BraveSearchClient()
            assert client._api_key == "env_key_456"

    def test_keyring_api_key(self, mock_config):
        """Client reads API key from keyring via config."""
        mock_config.get_brave_api_key.return_value = "keyring_key_789"
        client = BraveSearchClient()
        assert client._api_key == "keyring_key_789"

    def test_is_available_false(self, mock_config):
        """is_available returns False when no key configured."""
        with patch.dict("os.environ", {}, clear=True):
            assert not BraveSearchClient.is_available()

    def test_is_available_env(self, mock_config):
        """is_available returns True with env var set."""
        with patch.dict("os.environ", {"BRAVE_API_KEY": "test"}):
            assert BraveSearchClient.is_available()

    def test_is_available_keyring(self, mock_config):
        """is_available returns True with keyring key."""
        mock_config.get_brave_api_key.return_value = "kr_key"
        assert BraveSearchClient.is_available()


class TestSearch:
    """Tests for search method."""

    def test_successful_search(self, client, mock_response):
        """Test a successful web search."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        with patch("httpx.get", return_value=mock_http_response) as mock_get:
            results = client.search("IRS 2024 limits")

            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args
            assert call_kwargs.kwargs["headers"]["X-Subscription-Token"] == "test_brave_key"
            assert call_kwargs.kwargs["params"]["q"] == "IRS 2024 limits"

            assert len(results) == 3
            assert results[0]["title"] == "IRS Revenue Procedure 2023-34"
            assert results[0]["url"] == "https://www.irs.gov/rev-proc-2023-34"
            assert "inflation-adjusted" in results[0]["description"]

    def test_rate_limit_error(self, client):
        """Test handling of 429 rate limit response."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 429

        with patch("httpx.get", return_value=mock_http_response):
            with pytest.raises(BraveSearchError, match="Rate limit"):
                client.search("test query")

    def test_auth_error(self, client):
        """Test handling of 401 authentication error."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 401

        with patch("httpx.get", return_value=mock_http_response):
            with pytest.raises(BraveSearchError, match="Invalid"):
                client.search("test query")

    def test_server_error(self, client):
        """Test handling of server error."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 500
        mock_http_response.text = "Internal Server Error"

        with patch("httpx.get", return_value=mock_http_response):
            with pytest.raises(BraveSearchError, match="500"):
                client.search("test query")

    def test_timeout_error(self, client):
        """Test handling of timeout."""
        import httpx
        with patch("httpx.get", side_effect=httpx.TimeoutException("timeout")):
            with pytest.raises(BraveSearchError, match="timed out"):
                client.search("test query")

    def test_network_error(self, client):
        """Test handling of network error."""
        import httpx
        with patch("httpx.get", side_effect=httpx.RequestError("connection failed")):
            with pytest.raises(BraveSearchError, match="Network error"):
                client.search("test query")

    def test_count_capped_at_20(self, client, mock_response):
        """Test that count parameter is capped at 20."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        with patch("httpx.get", return_value=mock_http_response) as mock_get:
            client.search("test", count=50)
            assert mock_get.call_args.kwargs["params"]["count"] == 20

    def test_empty_results(self, client):
        """Test handling of empty results."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = {"web": {"results": []}}

        with patch("httpx.get", return_value=mock_http_response):
            results = client.search("obscure query")
            assert results == []


class TestTaxSearchHelpers:
    """Tests for tax-specific search helpers."""

    def test_search_irs(self, client, mock_response):
        """Test IRS-specific search."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        with patch("httpx.get", return_value=mock_http_response) as mock_get:
            client.search_irs("standard deduction", 2024)
            query = mock_get.call_args.kwargs["params"]["q"]
            assert "site:irs.gov" in query
            assert "standard deduction" in query
            assert "2024" in query

    def test_search_irs_no_year(self, client, mock_response):
        """Test IRS search without tax year."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        with patch("httpx.get", return_value=mock_http_response) as mock_get:
            client.search_irs("401k limits")
            query = mock_get.call_args.kwargs["params"]["q"]
            assert "site:irs.gov" in query
            assert "401k limits" in query

    def test_search_tax_topic(self, client, mock_response):
        """Test tax topic search."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        with patch("httpx.get", return_value=mock_http_response) as mock_get:
            client.search_tax_topic("wash sale rules", 2024)
            query = mock_get.call_args.kwargs["params"]["q"]
            assert "wash sale rules" in query
            assert "IRS tax rules" in query

    def test_search_state_tax(self, client, mock_response):
        """Test state tax search."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        with patch("httpx.get", return_value=mock_http_response) as mock_get:
            client.search_state_tax("CA", "income tax brackets", 2024)
            query = mock_get.call_args.kwargs["params"]["q"]
            assert "CA" in query
            assert "state tax" in query
            assert "income tax brackets" in query

    def test_search_tax_law_changes(self, client, mock_response):
        """Test law changes search."""
        mock_http_response = MagicMock()
        mock_http_response.status_code = 200
        mock_http_response.json.return_value = mock_response

        with patch("httpx.get", return_value=mock_http_response) as mock_get:
            client.search_tax_law_changes(2024)
            query = mock_get.call_args.kwargs["params"]["q"]
            assert "tax law changes" in query
            assert "2024" in query


class TestFormatResults:
    """Tests for result formatting."""

    def test_format_results(self, client):
        """Test formatting search results for AI context."""
        results = [
            {
                "title": "IRS Publication 550",
                "url": "https://www.irs.gov/pub550",
                "description": "Investment income and expenses guide.",
            },
            {
                "title": "Capital Gains Tax Rates",
                "url": "https://example.com/caps",
                "description": "Current capital gains rates explained.",
            },
        ]

        formatted = client.format_results_for_context(results)

        assert "## Web Search Results" in formatted
        assert "IRS Publication 550" in formatted
        assert "https://www.irs.gov/pub550" in formatted
        assert "Investment income" in formatted
        assert "Result 1:" in formatted
        assert "Result 2:" in formatted

    def test_format_empty_results(self, client):
        """Test formatting with no results."""
        formatted = client.format_results_for_context([])
        assert "No web search results found" in formatted

    def test_format_respects_max_results(self, client):
        """Test that max_results limits output."""
        results = [
            {"title": f"Result {i}", "url": f"https://example.com/{i}", "description": f"Desc {i}"}
            for i in range(10)
        ]

        formatted = client.format_results_for_context(results, max_results=3)
        assert "Result 3:" in formatted
        assert "Result 4:" not in formatted


class TestTaxResearcherIntegration:
    """Tests for TaxResearcher with web search."""

    def test_researcher_without_brave(self):
        """TaxResearcher works without Brave Search configured."""
        with patch("tax_agent.research.tax_researcher.get_config") as mock_config, \
             patch("tax_agent.research.tax_researcher.get_agent") as mock_agent, \
             patch("tax_agent.research.tax_researcher._get_search_client", return_value=None):
            mock_config.return_value.tax_year = 2024
            researcher = TaxResearcher(2024)
            assert not researcher.has_web_search

    def test_researcher_with_brave(self):
        """TaxResearcher detects Brave Search when available."""
        mock_search = MagicMock()
        with patch("tax_agent.research.tax_researcher.get_config") as mock_config, \
             patch("tax_agent.research.tax_researcher.get_agent") as mock_agent, \
             patch("tax_agent.research.tax_researcher._get_search_client", return_value=mock_search):
            mock_config.return_value.tax_year = 2024
            researcher = TaxResearcher(2024)
            assert researcher.has_web_search

    def test_research_topic_with_search(self):
        """TaxResearcher uses web results in research_topic."""
        mock_search = MagicMock()
        mock_search.search_tax_topic.return_value = [
            {"title": "Test", "url": "https://test.com", "description": "test desc"}
        ]
        mock_search.search_irs.return_value = []
        mock_search.format_results_for_context.return_value = "## Web Results\nTest content"

        mock_agent = MagicMock()
        mock_agent._call.return_value = "Research summary about wash sales."

        with patch("tax_agent.research.tax_researcher.get_config") as mock_config, \
             patch("tax_agent.research.tax_researcher.get_agent", return_value=mock_agent), \
             patch("tax_agent.research.tax_researcher._get_search_client", return_value=mock_search):
            mock_config.return_value.tax_year = 2024
            researcher = TaxResearcher(2024)
            result = researcher.research_topic("wash sale rules")

            assert result == "Research summary about wash sales."
            mock_search.search_tax_topic.assert_called_once_with("wash sale rules", 2024)
            # Verify web context was passed to Claude
            call_args = mock_agent._call.call_args
            assert "Web Results" in call_args[0][0] or "web search results" in call_args[0][0].lower()

    def test_research_topic_fallback(self):
        """TaxResearcher falls back to Claude-only when no search."""
        mock_agent = MagicMock()
        mock_agent._call.return_value = "Research from training data."

        with patch("tax_agent.research.tax_researcher.get_config") as mock_config, \
             patch("tax_agent.research.tax_researcher.get_agent", return_value=mock_agent), \
             patch("tax_agent.research.tax_researcher._get_search_client", return_value=None):
            mock_config.return_value.tax_year = 2024
            researcher = TaxResearcher(2024)
            result = researcher.research_topic("RSU taxation")

            assert result == "Research from training data."
            mock_agent._call.assert_called_once()


class TestConfigIntegration:
    """Tests for Brave API key config integration."""

    def test_brave_key_methods_exist(self):
        """Config class has Brave API key methods."""
        from tax_agent.config import Config
        config = Config.__new__(Config)
        assert hasattr(config, "get_brave_api_key")
        assert hasattr(config, "set_brave_api_key")
        assert hasattr(config, "clear_brave_api_key")
        assert hasattr(config, "brave_search_enabled")
