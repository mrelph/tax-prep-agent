# Source Directory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add per-tax-year source directories so `tax-agent collect` (no args) auto-scans and ingests all supported files recursively, skipping duplicates.

**Architecture:** Config-based approach — store `source_directories` dict in `config.json` keyed by year string. Add `source` CLI subcommand group, make `collect` file argument optional, make `process_directory()` support recursion.

**Tech Stack:** Python 3.12, typer, rich, pathlib, pytest

---

### Task 1: Config — source directory methods

**Files:**
- Modify: `src/tax_agent/config.py:79-96` (add to `_default_config`) and after line 300 (new methods)
- Test: `tests/test_source_directory.py`

**Step 1: Write the failing tests**

Create `tests/test_source_directory.py`:

```python
"""Tests for source directory configuration."""

import tempfile
from pathlib import Path

import pytest

from tax_agent.config import Config


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
        # Reload config from disk
        config2 = Config(config_dir=config.config_dir)
        assert config2.get_source_directory(2024) == source
```

**Step 2: Run tests to verify they fail**

Run: `uv run --extra dev python -m pytest tests/test_source_directory.py -v`
Expected: FAIL — `Config` has no `get_source_directory` method

**Step 3: Implement the Config methods**

In `src/tax_agent/config.py`, add `"source_directories": {}` to `_default_config()` dict (line ~96, before the closing `}`).

Then add these methods to the `Config` class, after `agent_sdk_allow_web` setter (after line 300):

```python
    def get_source_directory(self, year: int) -> Path | None:
        """Get the source directory for a tax year."""
        dirs = self._config.get("source_directories", {})
        path_str = dirs.get(str(year))
        return Path(path_str) if path_str else None

    def set_source_directory(self, year: int, path: Path) -> None:
        """Set the source directory for a tax year."""
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"Path does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")
        dirs = self._config.setdefault("source_directories", {})
        dirs[str(year)] = str(path)
        self._save()

    def clear_source_directory(self, year: int) -> None:
        """Remove the source directory for a tax year."""
        dirs = self._config.get("source_directories", {})
        dirs.pop(str(year), None)
        self._save()

    def get_all_source_directories(self) -> dict[int, Path]:
        """Get all configured source directories."""
        dirs = self._config.get("source_directories", {})
        return {int(y): Path(p) for y, p in dirs.items()}
```

**Step 4: Run tests to verify they pass**

Run: `uv run --extra dev python -m pytest tests/test_source_directory.py -v`
Expected: All 9 tests PASS

**Step 5: Commit**

```bash
git add src/tax_agent/config.py tests/test_source_directory.py
git commit -m "feat(config): add source directory methods for per-year document folders"
```

---

### Task 2: Collector — recursive directory scan

**Files:**
- Modify: `src/tax_agent/collectors/document_classifier.py:337-367`
- Test: `tests/test_source_directory.py` (add new test class)

**Step 1: Write the failing test**

Append to `tests/test_source_directory.py`:

```python
from unittest.mock import MagicMock, patch


class TestRecursiveDirectoryScan:
    def test_process_directory_flat_by_default(self, tmp_path):
        """Flat scan should NOT find files in subdirectories."""
        # Create files at root and in a subfolder
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
            collector.agent = MagicMock()
            results = collector.process_directory(tmp_path)

        # Should only find root-level file
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
            collector.agent = MagicMock()
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
            collector.agent = MagicMock()
            results = collector.process_directory(tmp_path, recursive=True)

        processed_names = {call.args[0].name for call in mock_process.call_args_list}
        assert "notes.txt" not in processed_names
        assert "w2.pdf" in processed_names
        assert "photo.png" in processed_names  # .png is supported
```

**Step 2: Run tests to verify they fail**

Run: `uv run --extra dev python -m pytest tests/test_source_directory.py::TestRecursiveDirectoryScan -v`
Expected: FAIL — `process_directory()` got unexpected keyword argument `recursive`

**Step 3: Modify `process_directory`**

In `src/tax_agent/collectors/document_classifier.py`, change the `process_directory` method (line ~337):

```python
    def process_directory(
        self,
        directory: str | Path,
        tax_year: int | None = None,
        recursive: bool = False,
    ) -> list[tuple[Path, TaxDocument | Exception]]:
        """
        Process all supported files in a directory.

        Args:
            directory: Path to directory
            tax_year: Tax year (defaults to config)
            recursive: If True, scan subdirectories recursively

        Returns:
            List of (file_path, result) tuples where result is TaxDocument or Exception
        """
        directory = Path(directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        results: list[tuple[Path, TaxDocument | Exception]] = []
        supported_extensions = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}

        if recursive:
            files = (f for f in directory.rglob("*") if f.is_file())
        else:
            files = directory.iterdir()

        for file_path in sorted(files):
            if file_path.suffix.lower() in supported_extensions:
                try:
                    doc = self.process_file(file_path, tax_year)
                    results.append((file_path, doc))
                except Exception as e:
                    results.append((file_path, e))

        return results
```

**Step 4: Run tests to verify they pass**

Run: `uv run --extra dev python -m pytest tests/test_source_directory.py -v`
Expected: All 12 tests PASS

**Step 5: Commit**

```bash
git add src/tax_agent/collectors/document_classifier.py tests/test_source_directory.py
git commit -m "feat(collector): add recursive option to process_directory"
```

---

### Task 3: CLI — `source` subcommand group

**Files:**
- Modify: `src/tax_agent/cli.py` (add subcommand group after line ~580, add commands)
- Test: `tests/test_source_directory.py` (add CLI test class)

**Step 1: Write the failing tests**

Append to `tests/test_source_directory.py`:

```python
from typer.testing import CliRunner
from tax_agent.cli import app

runner = CliRunner()


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
        # Set then show
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run --extra dev python -m pytest tests/test_source_directory.py::TestSourceCLI -v`
Expected: FAIL — no `source` command group

**Step 3: Add the `source` subcommand group to `cli.py`**

In `src/tax_agent/cli.py`, after line 580 (the existing `app.add_typer` block), add:

```python
source_app = typer.Typer(help="Manage source directories for tax documents")
app.add_typer(source_app, name="source")


@source_app.command("set")
def source_set(
    path: Annotated[Path, typer.Argument(help="Path to source directory")],
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year (defaults to active year)")] = None,
) -> None:
    """Set the source directory for a tax year."""
    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year

    # Resolve path
    resolved = Path(str(path).replace("~", str(Path.home())))
    if not resolved.is_absolute():
        resolved = Path.cwd() / resolved
    resolved = resolved.resolve()

    try:
        config.set_source_directory(tax_year, resolved)
    except ValueError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1)

    rprint(f"[green]Source directory for {tax_year} set to: {resolved}[/green]")


@source_app.command("show")
def source_show() -> None:
    """Show all configured source directories."""
    config = get_config()
    dirs = config.get_all_source_directories()

    if not dirs:
        rprint("[dim]No source directories configured.[/dim]")
        rprint("[dim]Use 'tax-agent source set <path>' to configure one.[/dim]")
        return

    table = Table(title="Source Directories")
    table.add_column("Tax Year", style="cyan")
    table.add_column("Directory", style="green")
    table.add_column("Status")

    for yr in sorted(dirs.keys(), reverse=True):
        path = dirs[yr]
        exists = path.is_dir()
        status = "[green]OK[/green]" if exists else "[red]Missing[/red]"
        active = " [yellow](active)[/yellow]" if yr == config.tax_year else ""
        table.add_row(f"{yr}{active}", str(path), status)

    console.print(table)


@source_app.command("clear")
def source_clear(
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year (defaults to active year)")] = None,
) -> None:
    """Clear the source directory for a tax year."""
    config = get_config()
    tax_year = year or config.tax_year
    config.clear_source_directory(tax_year)
    rprint(f"[green]Cleared source directory for {tax_year}.[/green]")
```

**Step 4: Run tests to verify they pass**

Run: `uv run --extra dev python -m pytest tests/test_source_directory.py -v`
Expected: All 18 tests PASS

**Step 5: Commit**

```bash
git add src/tax_agent/cli.py tests/test_source_directory.py
git commit -m "feat(cli): add 'source' subcommand group (set/show/clear)"
```

---

### Task 4: CLI — make `collect` file argument optional

**Files:**
- Modify: `src/tax_agent/cli.py:939-944` (change `collect` signature)
- Test: `tests/test_source_directory.py` (add collect integration tests)

**Step 1: Write the failing tests**

Append to `tests/test_source_directory.py`:

```python
class TestCollectFromSourceDir:
    def test_collect_no_args_uses_source_dir(self, tmp_path, monkeypatch):
        """collect with no args should use the configured source directory."""
        source = tmp_path / "taxes"
        source.mkdir()
        (source / "w2.pdf").touch()
        config_dir = tmp_path / ".tax-agent"
        config_dir.mkdir(parents=True)
        (config_dir / "data").mkdir(parents=True)
        (config_dir / "config.json").write_text(
            '{"initialized": true, "tax_year": 2024, '
            '"source_directories": {"2024": "' + str(source).replace("\\", "\\\\") + '"}}'
        )
        monkeypatch.setattr("tax_agent.cli.get_config", lambda: Config(config_dir=config_dir))

        with patch("tax_agent.cli.DocumentCollector") as MockCollector:
            mock_instance = MockCollector.return_value
            mock_instance.process_directory.return_value = []
            result = runner.invoke(app, ["collect"])

        assert result.exit_code == 0
        mock_instance.process_directory.assert_called_once()
        call_args = mock_instance.process_directory.call_args
        assert call_args[0][0] == source
        assert call_args[1].get("recursive") is True

    def test_collect_no_args_no_source_dir_shows_error(self, tmp_path, monkeypatch):
        """collect with no args and no source dir should show helpful error."""
        config_dir = tmp_path / ".tax-agent"
        config_dir.mkdir(parents=True)
        (config_dir / "config.json").write_text('{"initialized": true, "tax_year": 2024}')
        monkeypatch.setattr("tax_agent.cli.get_config", lambda: Config(config_dir=config_dir))
        result = runner.invoke(app, ["collect"])
        assert result.exit_code == 1
        assert "source" in result.stdout.lower()
```

**Step 2: Run tests to verify they fail**

Run: `uv run --extra dev python -m pytest tests/test_source_directory.py::TestCollectFromSourceDir -v`
Expected: FAIL — `collect` requires `file` argument

**Step 3: Modify the `collect` command**

In `src/tax_agent/cli.py`, change the `collect` command signature (line ~939):

```python
@app.command()
def collect(
    file: Annotated[Optional[Path], typer.Argument(help="Path to tax document (PDF or image). Omit to use configured source directory.")] = None,
    year: Annotated[Optional[int], typer.Option("--year", "-y", help="Tax year")] = None,
    directory: Annotated[Optional[Path], typer.Option("--dir", "-d", help="Process all files in directory")] = None,
    replace: Annotated[bool, typer.Option("--replace", "-r", help="Replace existing document if duplicate")] = False,
) -> None:
    """Collect and process a tax document.

    If no file is specified, uses the configured source directory for the active tax year.
    Set a source directory with: tax-agent source set <path>
    """
    from tax_agent.collectors.document_classifier import DocumentCollector

    config = get_config()

    if not config.is_initialized:
        rprint("[red]Tax agent not initialized. Run 'tax-agent init' first.[/red]")
        raise typer.Exit(1)

    tax_year = year or config.tax_year
    collector = DocumentCollector()

    # No file argument — use configured source directory
    if file is None and directory is None:
        source_dir = config.get_source_directory(tax_year)
        if source_dir is None:
            rprint(f"[red]No source directory configured for {tax_year}.[/red]")
            rprint("[dim]Set one with: tax-agent source set <path>[/dim]")
            raise typer.Exit(1)

        if not source_dir.is_dir():
            rprint(f"[red]Source directory no longer exists: {source_dir}[/red]")
            rprint("[dim]Update with: tax-agent source set <new_path>[/dim]")
            raise typer.Exit(1)

        rprint(f"[cyan]Scanning source directory for {tax_year}: {source_dir}[/cyan]")
        rprint("[dim]Skipping already-collected documents...[/dim]")

        with console.status("[bold green]Processing files..."):
            results = collector.process_directory(source_dir, tax_year, recursive=True)

        if not results:
            rprint("[dim]No new documents found.[/dim]")
            return

        for file_path, result in results:
            if isinstance(result, Exception):
                if "duplicate" in str(result).lower() or "already" in str(result).lower():
                    rprint(f"[dim]  {file_path.name}: already collected[/dim]")
                else:
                    rprint(f"[red]  {file_path.name}: {result}[/red]")
            else:
                confidence = "high" if result.confidence_score >= 0.8 else "low"
                review_flag = " [yellow](needs review)[/yellow]" if result.needs_review else ""
                rprint(f"[green]  {file_path.name}: {get_enum_value(result.document_type)} from {result.issuer_name} ({confidence} confidence){review_flag}[/green]")

        success_count = sum(1 for _, r in results if not isinstance(r, Exception))
        rprint(f"\n[cyan]Processed {success_count}/{len(results)} files successfully.[/cyan]")
        return

    if directory:
        # ... rest of existing directory logic unchanged ...
```

The existing `if directory:` and `else:` blocks remain unchanged.

**Step 4: Run tests to verify they pass**

Run: `uv run --extra dev python -m pytest tests/test_source_directory.py -v`
Expected: All 20 tests PASS

**Step 5: Commit**

```bash
git add src/tax_agent/cli.py tests/test_source_directory.py
git commit -m "feat(cli): collect with no args uses configured source directory"
```

---

### Task 5: Slash command — `/collect` no-arg support

**Files:**
- Modify: `src/tax_agent/slash_commands.py:608-611`
- Test: `tests/test_source_directory.py` (add slash command test)

**Step 1: Write the failing test**

Append to `tests/test_source_directory.py`:

```python
class TestSlashCollect:
    def test_slash_collect_no_args_uses_source_dir(self, tmp_path, monkeypatch):
        source = tmp_path / "taxes"
        source.mkdir()
        (source / "w2.pdf").touch()

        config_dir = tmp_path / ".tax-agent"
        config_dir.mkdir(parents=True)
        config = Config(config_dir=config_dir)
        config._config["initialized"] = True
        config._config["source_directories"] = {"2024": str(source)}
        config._save()

        monkeypatch.setattr("tax_agent.slash_commands.get_config", lambda: config)

        with patch("tax_agent.slash_commands.get_document_collector") as mock_get:
            mock_collector = MagicMock()
            mock_get.return_value = mock_collector
            mock_collector.process_directory.return_value = []

            from tax_agent.slash_commands import cmd_collect
            result = cmd_collect([], {"tax_year": 2024})

        mock_collector.process_directory.assert_called_once()
        call_args = mock_collector.process_directory.call_args
        assert call_args[0][0] == source
        assert call_args[1].get("recursive") is True

    def test_slash_collect_no_args_no_source_dir(self, tmp_path, monkeypatch):
        config_dir = tmp_path / ".tax-agent"
        config_dir.mkdir(parents=True)
        config = Config(config_dir=config_dir)
        config._config["initialized"] = True
        config._save()
        monkeypatch.setattr("tax_agent.slash_commands.get_config", lambda: config)

        from tax_agent.slash_commands import cmd_collect
        result = cmd_collect([], {"tax_year": 2024})
        assert "source" in result.lower()
```

**Step 2: Run tests to verify they fail**

Run: `uv run --extra dev python -m pytest tests/test_source_directory.py::TestSlashCollect -v`
Expected: FAIL — `cmd_collect` returns usage error for no args

**Step 3: Modify `cmd_collect`**

In `src/tax_agent/slash_commands.py`, replace the no-args guard (line ~608):

```python
def cmd_collect(args: list[str], context: dict) -> str:
    """Collect a tax document."""
    from tax_agent.collectors.document_classifier import get_document_collector
    from tax_agent.config import get_config

    config = get_config()

    if not args:
        # No args — try configured source directory
        source_dir = config.get_source_directory(config.tax_year)
        if source_dir is None:
            return (
                "No file specified and no source directory configured.\n\n"
                "**Usage:** `/collect <file_path> [--year YEAR]`\n\n"
                "**Or set a source directory:** `tax-agent source set <path>`"
            )

        if not source_dir.is_dir():
            return f"Source directory no longer exists: {source_dir}\n\nUpdate with: `tax-agent source set <new_path>`"

        collector = get_document_collector()
        results = collector.process_directory(source_dir, config.tax_year, recursive=True)

        if not results:
            return f"No new documents found in {source_dir}"

        lines = [f"Scanned **{source_dir}** for {config.tax_year}:\n"]
        for file_path, result in results:
            if isinstance(result, Exception):
                lines.append(f"- {file_path.name}: {result}")
            else:
                lines.append(f"- {file_path.name}: {result.document_type.value} from {result.issuer_name}")

        success = sum(1 for _, r in results if not isinstance(r, Exception))
        lines.append(f"\n**{success}/{len(results)}** files processed successfully.")
        return "\n".join(lines)

    file_path = Path(args[0]).expanduser()
    # ... rest of existing logic unchanged ...
```

**Step 4: Run tests to verify they pass**

Run: `uv run --extra dev python -m pytest tests/test_source_directory.py -v`
Expected: All 22 tests PASS

**Step 5: Commit**

```bash
git add src/tax_agent/slash_commands.py tests/test_source_directory.py
git commit -m "feat(slash): /collect with no args uses configured source directory"
```

---

### Task 6: Status command — show source directory

**Files:**
- Modify: `src/tax_agent/cli.py:717-760` (status command)

**Step 1: Add source directory info to `status` command**

In `src/tax_agent/cli.py`, in the `status()` function, before `table.add_row("Data Directory", ...)` (line ~758), add:

```python
    # Source directory for active year
    source_dir = config.get_source_directory(config.tax_year)
    if source_dir:
        status_str = str(source_dir)
        if not source_dir.is_dir():
            status_str += " [red](missing)[/red]"
        table.add_row(f"Source Dir ({config.tax_year})", status_str)
    else:
        table.add_row(f"Source Dir ({config.tax_year})", "[dim]Not set[/dim]")
```

**Step 2: Verify manually**

Run: `uv run tax-agent status`
Expected: Table includes a "Source Dir (2024)" row

**Step 3: Run full test suite**

Run: `uv run --extra dev python -m pytest tests/test_source_directory.py tests/test_utils.py -v`
Expected: All pass

**Step 4: Commit**

```bash
git add src/tax_agent/cli.py
git commit -m "feat(cli): show source directory in status command"
```

---

### Task 7: Final verification and push

**Step 1: Run full test suite**

Run: `uv run --extra dev python -m pytest tests/ -v`
Expected: All pass (except pre-existing `test_hooks.py` failure)

**Step 2: Push**

```bash
git push
```
