#!/bin/bash
# Tax Prep Agent - Installation Script (clone-based with self-update support)
# Usage: curl -sSL https://raw.githubusercontent.com/mrelph/tax-prep-agent/main/install.sh | bash
#
# Re-run this script at any time to update, or use: tax-agent update

set -e

REPO_URL="https://github.com/mrelph/tax-prep-agent.git"
CLONE_DIR="$HOME/.tax-agent-source"
VENV_DIR="$HOME/.tax-agent-venv"
INSTALL_DIR="$HOME/.local/bin"

echo "╭─────────────────────────────────────────╮"
echo "│  Tax Prep Agent - Installation          │"
echo "╰─────────────────────────────────────────╯"
echo ""

# ── Prerequisites ──────────────────────────────────────────────

if ! command -v git &> /dev/null; then
    echo "❌ git is required but not installed."
    echo "   macOS:  xcode-select --install"
    echo "   Ubuntu: sudo apt install git"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    echo "   Install Python 3.11+ from https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo "❌ Python 3.11+ is required (found $PYTHON_VERSION)"
    exit 1
fi

echo "✓ git $(git --version | cut -d' ' -f3) detected"
echo "✓ Python $PYTHON_VERSION detected"

# ── Clone or update source ─────────────────────────────────────

if [ -d "$CLONE_DIR/.git" ]; then
    echo "→ Updating existing source in $CLONE_DIR..."
    cd "$CLONE_DIR"
    git fetch origin
    git pull --ff-only origin main || git pull --ff-only origin master
    cd - > /dev/null
else
    if [ -d "$CLONE_DIR" ]; then
        echo "→ Removing stale directory at $CLONE_DIR..."
        rm -rf "$CLONE_DIR"
    fi
    echo "→ Cloning repository to $CLONE_DIR..."
    git clone "$REPO_URL" "$CLONE_DIR"
fi

echo "✓ Source ready"

# ── Virtual environment ────────────────────────────────────────

if [ -d "$VENV_DIR" ]; then
    echo "→ Reusing virtual environment at $VENV_DIR"
else
    echo "→ Creating virtual environment at $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
fi

echo "→ Installing tax-agent (editable)..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -e "$CLONE_DIR"

echo "✓ Package installed"

# ── Wrapper script ─────────────────────────────────────────────

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

echo "Quick start:"
echo "  tax-agent init       # First-time setup"
echo "  tax-agent            # Start interactive mode"
echo "  tax-agent update     # Check for & install updates"
echo ""
