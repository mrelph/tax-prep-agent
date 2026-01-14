#!/bin/bash
# Tax Prep Agent - Easy Installation Script
# Usage: curl -sSL https://raw.githubusercontent.com/mrelph/tax-prep-agent/main/install.sh | bash

set -e

REPO="mrelph/tax-prep-agent"
INSTALL_DIR="$HOME/.local/bin"
VENV_DIR="$HOME/.tax-agent-venv"

echo "╭─────────────────────────────────────────╮"
echo "│  Tax Prep Agent - Installation          │"
echo "╰─────────────────────────────────────────╯"
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "   Install Python 3.11+ from https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "❌ Python 3.11+ is required (found $PYTHON_VERSION)"
    exit 1
fi

echo "✓ Python $PYTHON_VERSION detected"

# Check for pipx (preferred) or use venv
if command -v pipx &> /dev/null; then
    echo "✓ Installing with pipx (recommended)..."
    pipx install "git+https://github.com/$REPO.git"
    echo ""
    echo "✅ Installation complete!"
    echo ""
    echo "Run 'tax-agent' to start."
else
    echo "→ pipx not found, using virtual environment..."

    # Create virtual environment
    if [ -d "$VENV_DIR" ]; then
        echo "  Removing existing installation..."
        rm -rf "$VENV_DIR"
    fi

    echo "  Creating virtual environment..."
    python3 -m venv "$VENV_DIR"

    echo "  Installing tax-agent..."
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet "git+https://github.com/$REPO.git"

    # Create wrapper script
    mkdir -p "$INSTALL_DIR"
    cat > "$INSTALL_DIR/tax-agent" << 'WRAPPER'
#!/bin/bash
exec "$HOME/.tax-agent-venv/bin/tax-agent" "$@"
WRAPPER
    chmod +x "$INSTALL_DIR/tax-agent"

    echo ""
    echo "✅ Installation complete!"
    echo ""

    # Check if INSTALL_DIR is in PATH
    if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
        echo "⚠️  Add this to your shell config (~/.bashrc or ~/.zshrc):"
        echo ""
        echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
        echo "Then restart your terminal or run: source ~/.bashrc"
        echo ""
    fi

    echo "Run 'tax-agent' to start."
fi

echo ""
echo "Quick start:"
echo "  tax-agent init    # First-time setup"
echo "  tax-agent         # Start interactive mode"
echo ""
