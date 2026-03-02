# Source Directory Feature Design

## Summary

Add the ability to configure a per-tax-year source directory so that `tax-agent collect` (with no arguments) automatically scans and ingests all supported files recursively, skipping already-collected documents via existing SHA-256 dedup.

## Design

### Config Storage

Add a `source_directories` dict to `config.json`, keyed by tax year (as string):

```json
{
  "source_directories": {
    "2024": "/home/user/Documents/Taxes/2024",
    "2023": "/home/user/Documents/Taxes/2023"
  }
}
```

New methods on `Config`:
- `get_source_directory(year: int) -> Path | None`
- `set_source_directory(year: int, path: Path) -> None`
- `clear_source_directory(year: int) -> None`
- `get_all_source_directories() -> dict[int, Path]`

### CLI Commands

New `source` command group:

| Command | Description |
|---------|-------------|
| `tax-agent source set <path> [--year]` | Set source directory for a tax year (defaults to active year) |
| `tax-agent source show` | Display all configured source directories |
| `tax-agent source clear [--year]` | Remove source directory for a year |

### Modified `collect` Behavior

When `tax-agent collect` is called with no file argument:
1. Look up the source directory for the active tax year
2. If configured, recursively scan for supported files (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`)
3. Skip already-collected files (existing SHA-256 hash dedup in `process_file()`)
4. If no source directory configured, show an error pointing to `tax-agent source set`

### Recursive Directory Scan

Modify `DocumentCollector.process_directory()` to accept a `recursive: bool = False` parameter. When true, use `Path.rglob()` instead of `Path.iterdir()`. The source directory flow always passes `recursive=True`.

### Interactive `/collect` Command

Update the `/collect` slash command to also support no-arg invocation using the configured source directory.

## Out of Scope

- Watch folder / background monitoring
- Database-tracked directories or scan metadata
- Auto-detection of source directories
