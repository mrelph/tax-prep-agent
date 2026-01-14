"""Tax context steering document management.

This module manages a TAX_CONTEXT.md file that provides persistent context
about the taxpayer's situation, similar to how CLAUDE.md works for coding projects.
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from tax_agent.config import get_config

# Default template for new context files
DEFAULT_TEMPLATE = '''# Tax Context

*This file provides context about your tax situation to guide AI analysis.*
*Edit this file to customize how the tax agent understands your situation.*

## Taxpayer Profile

- **Filing Status:** [Single / Married Filing Jointly / Married Filing Separately / Head of Household]
- **State:** {state}
- **Dependents:** [Number and ages]
- **Occupation:** [Your profession]

## Income Sources

- [ ] W-2 Employment (primary job)
- [ ] W-2 Employment (secondary/spouse)
- [ ] Self-employment / 1099-NEC
- [ ] Investment income (dividends, interest, capital gains)
- [ ] Rental property income
- [ ] Retirement distributions
- [ ] Other: ___

## Stock Compensation

*If you have equity compensation, describe it here:*

- **RSUs:** [Yes/No - Company, approximate value]
- **ISOs:** [Yes/No - Exercise dates, AMT concerns]
- **NSOs:** [Yes/No]
- **ESPP:** [Yes/No - Qualifying/non-qualifying dispositions]

## Key Tax Considerations

*List specific things the AI should pay attention to:*

-
-
-

## Tax Goals for {year}

*What are you trying to optimize for?*

- [ ] Maximize refund
- [ ] Minimize tax owed
- [ ] Reduce AGI for specific purpose (ACA subsidies, student loans, etc.)
- [ ] Optimize retirement contributions
- [ ] Tax-loss harvesting
- [ ] Plan for major life event
- [ ] Other: ___

## Important Notes

*Anything else the AI should know about your tax situation:*

-
-

## History & Prior Years

*Relevant information from prior tax years:*

- **Carryforwards:** [Capital losses, NOLs, etc.]
- **Estimated payments made:** [Quarterly payments for {year}]
- **Prior year refund/owed:**

---
*Last updated: {date}*
'''


class TaxContext:
    """Manages the tax context steering document."""

    def __init__(self, context_path: Path | None = None):
        """Initialize the tax context manager.

        Args:
            context_path: Path to the context file. Defaults to ~/.tax-agent/TAX_CONTEXT.md
        """
        config = get_config()
        self.context_path = context_path or (config.config_dir / "TAX_CONTEXT.md")

    def exists(self) -> bool:
        """Check if the context file exists."""
        return self.context_path.exists()

    def load(self) -> str | None:
        """Load the context file content.

        Returns:
            The content of the context file, or None if it doesn't exist.
        """
        if not self.exists():
            return None

        return self.context_path.read_text(encoding="utf-8")

    def save(self, content: str) -> None:
        """Save content to the context file.

        Args:
            content: The content to save.
        """
        self.context_path.parent.mkdir(parents=True, exist_ok=True)
        self.context_path.write_text(content, encoding="utf-8")

    def create_from_template(self) -> str:
        """Create a new context file from the default template.

        Returns:
            The generated template content.
        """
        config = get_config()
        state = config.state or "[Your State]"
        year = config.tax_year

        content = DEFAULT_TEMPLATE.format(
            state=state,
            year=year,
            date=datetime.now().strftime("%Y-%m-%d"),
        )

        self.save(content)
        return content

    def open_in_editor(self) -> bool:
        """Open the context file in the system's default editor.

        Returns:
            True if the editor was opened successfully, False otherwise.
        """
        if not self.exists():
            self.create_from_template()

        # Try common editors in order of preference
        editors = []

        # Check for EDITOR environment variable first
        import os
        env_editor = os.environ.get("EDITOR")
        if env_editor:
            editors.append(env_editor)

        # Platform-specific defaults
        if sys.platform == "darwin":  # macOS
            editors.extend(["open", "code", "nano", "vim"])
        elif sys.platform == "win32":  # Windows
            editors.extend(["notepad", "code", "notepad++"])
        else:  # Linux and others
            editors.extend(["xdg-open", "code", "nano", "vim", "gedit"])

        for editor in editors:
            try:
                if editor in ("open", "xdg-open"):
                    # These open with default app
                    subprocess.Popen([editor, str(self.context_path)])
                else:
                    subprocess.Popen([editor, str(self.context_path)])
                return True
            except FileNotFoundError:
                continue
            except Exception:
                continue

        return False

    def get_summary(self) -> dict:
        """Get a summary of the context file.

        Returns:
            Dictionary with context metadata.
        """
        if not self.exists():
            return {
                "exists": False,
                "path": str(self.context_path),
                "size": 0,
                "modified": None,
            }

        stat = self.context_path.stat()
        content = self.load() or ""

        # Count sections (## headers)
        sections = len([line for line in content.split("\n") if line.startswith("## ")])

        # Check for filled-in content (not just template)
        has_content = (
            "[Your" not in content
            and "[ ]" not in content[:500]  # First section has checkboxes filled
        )

        return {
            "exists": True,
            "path": str(self.context_path),
            "size": stat.st_size,
            "modified": datetime.fromtimestamp(stat.st_mtime),
            "sections": sections,
            "has_content": has_content,
        }

    def extract_key_info(self) -> dict:
        """Extract key information from the context file for AI prompts.

        Returns:
            Dictionary with extracted tax context information.
        """
        content = self.load()
        if not content:
            return {}

        info = {}

        # Extract filing status
        for line in content.split("\n"):
            line_lower = line.lower()

            if "filing status:" in line_lower:
                # Extract value after colon
                parts = line.split(":", 1)
                if len(parts) > 1:
                    status = parts[1].strip().strip("*[]")
                    if status and "single" not in status.lower() or len(status) < 50:
                        info["filing_status"] = status

            elif "state:" in line_lower and "filing" not in line_lower:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    state = parts[1].strip().strip("*[]")
                    if len(state) <= 20:  # Reasonable state length
                        info["state"] = state

            elif "dependents:" in line_lower:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    deps = parts[1].strip().strip("*[]")
                    if deps and "[" not in deps:
                        info["dependents"] = deps

            elif "occupation:" in line_lower:
                parts = line.split(":", 1)
                if len(parts) > 1:
                    occ = parts[1].strip().strip("*[]")
                    if occ and "[" not in occ:
                        info["occupation"] = occ

        # Extract checked items (income sources, goals)
        checked_items = []
        for line in content.split("\n"):
            if line.strip().startswith("- [x]") or line.strip().startswith("- [X]"):
                item = line.strip()[5:].strip()
                if item:
                    checked_items.append(item)

        if checked_items:
            info["selected_items"] = checked_items

        # Check for stock compensation
        has_stock_comp = any(
            keyword in content.lower()
            for keyword in ["rsu", "iso", "nso", "espp", "stock option", "equity"]
            if "yes" in content.lower()[max(0, content.lower().find(keyword) - 50):content.lower().find(keyword) + 100]
        )
        if has_stock_comp:
            info["has_stock_compensation"] = True

        return info


# Global instance
_context: TaxContext | None = None


def get_tax_context() -> TaxContext:
    """Get the global tax context instance."""
    global _context
    if _context is None:
        _context = TaxContext()
    return _context


def get_context_for_prompt() -> str:
    """Get the tax context formatted for inclusion in AI prompts.

    Returns:
        Formatted context string, or empty string if no context exists.
    """
    ctx = get_tax_context()
    content = ctx.load()

    if not content:
        return ""

    # Return the full content wrapped in a section marker
    return f"""
## Taxpayer Context (from TAX_CONTEXT.md)

{content}

---
"""
