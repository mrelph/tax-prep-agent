"""Tests for source directory configuration."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tax_agent.cli import app
from tax_agent.config import Config

runner = CliRunner()


@pytest.fixture
def config(tmp_path):
    """Create a Config with a temp directory."""
    return Config(config_dir=tmp_path / ".tax-agent")


class TestSourceDirectory:
    def test_get_source_directory_returns_none_when_not_set(self, config):
        assert config.get_source_directory(2024) is None

    def test_set_and_get_source_directory(self, config, tmp_path):
        source = tmp_path / "taxes" / "2024"
        source.mkdir(parents=True)
        config.set_source_directory(2024, source)
        assert config.get_source_directory(2024) == source

    def test_set_source_directory_rejects_nonexistent_path(self, config, tmp_path):
        fake = tmp_path / "nonexistent"
        with pytest.raises(ValueError, match="does not exist"):
            config.set_source_directory(2024, fake)

    def test_set_source_directory_rejects_file_path(self, config, tmp_path):
        file = tmp_path / "file.txt"
        file.touch()
        with pytest.raises(ValueError, match="not a directory"):
            config.set_source_directory(2024, file)

    def test_clear_source_directory(self, config, tmp_path):
        source = tmp_path / "taxes"
        source.mkdir()
        config.set_source_directory(2024, source)
        config.clear_source_directory(2024)
        assert config.get_source_directory(2024) is None

    def test_clear_source_directory_noop_when_not_set(self, config):
        config.clear_source_directory(2024)  # should not raise

    def test_get_all_source_directories(self, config, tmp_path):
        d2024 = tmp_path / "2024"
        d2023 = tmp_path / "2023"
        d2024.mkdir()
        d2023.mkdir()
        config.set_source_directory(2024, d2024)
        config.set_source_directory(2023, d2023)
        result = config.get_all_source_directories()
        assert result == {2024: d2024, 2023: d2023}

    def test_get_all_source_directories_empty(self, config):
        assert config.get_all_source_directories() == {}

    def test_source_directory_persists_across_reload(self, config, tmp_path):
        source = tmp_path / "taxes"
        source.mkdir()
        config.set_source_directory(2024, source)
        config2 = Config(config_dir=config.config_dir)
        assert config2.get_source_directory(2024) == source


class TestRecursiveDirectoryScan:
    def test_process_directory_flat_by_default(self, tmp_path):
        """Flat scan should NOT find files in subdirectories."""
        (tmp_path / "w2.pdf").touch()
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (subdir / "1099.pdf").touch()

        with patch(
            "tax_agent.collectors.document_classifier.DocumentCollector.process_file"
        ) as mock_process:
            mock_process.return_value = MagicMock()
            from tax_agent.collectors.document_classifier import DocumentCollector
            collector = DocumentCollector.__new__(DocumentCollector)
            collector.config = MagicMock()
            collector._agent = MagicMock()
            results = collector.process_directory(tmp_path)

        processed_paths = [call.args[0] for call in mock_process.call_args_list]
        assert len(processed_paths) == 1
        assert processed_paths[0].name == "w2.pdf"

    def test_process_directory_recursive(self, tmp_path):
        """Recursive scan should find files in subdirectories."""
        (tmp_path / "w2.pdf").touch()
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (subdir / "1099.pdf").touch()

        with patch(
            "tax_agent.collectors.document_classifier.DocumentCollector.process_file"
        ) as mock_process:
            mock_process.return_value = MagicMock()
            from tax_agent.collectors.document_classifier import DocumentCollector
            collector = DocumentCollector.__new__(DocumentCollector)
            collector.config = MagicMock()
            collector._agent = MagicMock()
            results = collector.process_directory(tmp_path, recursive=True)

        processed_names = {call.args[0].name for call in mock_process.call_args_list}
        assert processed_names == {"w2.pdf", "1099.pdf"}

    def test_process_directory_recursive_skips_unsupported(self, tmp_path):
        """Recursive scan should skip non-document files."""
        (tmp_path / "w2.pdf").touch()
        (tmp_path / "notes.txt").touch()
        (tmp_path / "photo.png").touch()

        with patch(
            "tax_agent.collectors.document_classifier.DocumentCollector.process_file"
        ) as mock_process:
            mock_process.return_value = MagicMock()
            from tax_agent.collectors.document_classifier import DocumentCollector
            collector = DocumentCollector.__new__(DocumentCollector)
            collector.config = MagicMock()
            collector._agent = MagicMock()
            results = collector.process_directory(tmp_path, recursive=True)

        processed_names = {call.args[0].name for call in mock_process.call_args_list}
        assert "notes.txt" not in processed_names
        assert "w2.pdf" in processed_names
        assert "photo.png" in processed_names


class TestSourceCLI:
    def test_source_set(self, tmp_path, monkeypatch):
        source = tmp_path / "taxes"
        source.mkdir()
        config_dir = tmp_path / ".tax-agent"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"initialized": true, "tax_year": 2024}')
        monkeypatch.setattr("tax_agent.cli.get_config", lambda: Config(config_dir=config_dir))
        result = runner.invoke(app, ["source", "set", str(source)])
        assert result.exit_code == 0
        assert "2024" in result.stdout

    def test_source_set_custom_year(self, tmp_path, monkeypatch):
        source = tmp_path / "taxes"
        source.mkdir()
        config_dir = tmp_path / ".tax-agent"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"initialized": true, "tax_year": 2024}')
        monkeypatch.setattr("tax_agent.cli.get_config", lambda: Config(config_dir=config_dir))
        result = runner.invoke(app, ["source", "set", str(source), "--year", "2023"])
        assert result.exit_code == 0
        assert "2023" in result.stdout

    def test_source_set_nonexistent_dir(self, tmp_path, monkeypatch):
        config_dir = tmp_path / ".tax-agent"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"initialized": true, "tax_year": 2024}')
        monkeypatch.setattr("tax_agent.cli.get_config", lambda: Config(config_dir=config_dir))
        result = runner.invoke(app, ["source", "set", "/nonexistent/path"])
        assert result.exit_code == 1

    def test_source_show_empty(self, tmp_path, monkeypatch):
        config_dir = tmp_path / ".tax-agent"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"initialized": true, "tax_year": 2024}')
        monkeypatch.setattr("tax_agent.cli.get_config", lambda: Config(config_dir=config_dir))
        result = runner.invoke(app, ["source", "show"])
        assert result.exit_code == 0
        assert "No source directories" in result.stdout

    def test_source_show_with_dirs(self, tmp_path, monkeypatch):
        source = tmp_path / "taxes"
        source.mkdir()
        config_dir = tmp_path / ".tax-agent"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"initialized": true, "tax_year": 2024}')
        monkeypatch.setattr("tax_agent.cli.get_config", lambda: Config(config_dir=config_dir))
        runner.invoke(app, ["source", "set", str(source)])
        result = runner.invoke(app, ["source", "show"])
        assert result.exit_code == 0
        assert "2024" in result.stdout

    def test_source_clear(self, tmp_path, monkeypatch):
        source = tmp_path / "taxes"
        source.mkdir()
        config_dir = tmp_path / ".tax-agent"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"initialized": true, "tax_year": 2024}')
        monkeypatch.setattr("tax_agent.cli.get_config", lambda: Config(config_dir=config_dir))
        runner.invoke(app, ["source", "set", str(source)])
        result = runner.invoke(app, ["source", "clear"])
        assert result.exit_code == 0
        assert "Cleared" in result.stdout
