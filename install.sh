#!/usr/bin/env bash
# ==============================================================================
# elSandoo2 el a5dar - Linux / macOS Setup & Prerequisite Engine
# Developed & Customized by Recode Developments (Osama Kamel)
# ==============================================================================

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "========================================================"
echo "         elSandoo2 el a5dar - Installer"
echo "             by Recode Developments"
echo "========================================================"
echo ""

# 1. Check & Sync with GitHub
if command -v git &> /dev/null; then
    if [ -d ".git" ]; then
        echo "--> [1/4] Checking for updates from GitHub..."
        git fetch origin main --quiet 2>/dev/null || true
        LOCAL_HASH=$(git rev-parse HEAD 2>/dev/null || true)
        REMOTE_HASH=$(git rev-parse origin/main 2>/dev/null || true)
        if [ -n "$LOCAL_HASH" ] && [ -n "$REMOTE_HASH" ] && [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
            echo "--> Pulling latest version from GitHub..."
            git pull origin main --quiet || true
        else
            echo "--> System is up to date."
        fi
    fi
fi

# 2. Check Python
echo "--> [2/4] Verifying Python runtime..."
PYTHON_BIN=""
for py in python3.11 python3.10 python3.12 python3; do
    if command -v "$py" &> /dev/null; then
        PY_VER=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -ge 10 ]; then
            PYTHON_BIN="$py"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "[ERROR] Python 3.10 or higher is required. Please install it first:"
    echo "  Ubuntu/Debian: sudo apt update && sudo apt install python3 python3-venv python3-pip"
    echo "  macOS: brew install python@3.11"
    exit 1
fi
echo "    Found: $PYTHON_BIN ($($PYTHON_BIN --version))"

# 3. Check FFmpeg
echo "--> [3/4] Checking FFmpeg..."
if ! command -v ffmpeg &> /dev/null; then
    echo "    [WARNING] FFmpeg is not installed."
    echo "    Please install FFmpeg:"
    echo "      Ubuntu/Debian: sudo apt install ffmpeg"
    echo "      macOS: brew install ffmpeg"
else
    echo "    FFmpeg found: $(which ffmpeg)"
fi

# 4. Virtual Environment & Dependencies
echo "--> [4/4] Setting up virtual environment..."
if [ ! -f "venv/bin/python" ]; then
    "$PYTHON_BIN" -m venv venv
fi

venv/bin/python -m pip install --upgrade pip setuptools wheel --quiet
if [ -f "requirements.txt" ]; then
    echo "    Installing dependencies from requirements.txt..."
    venv/bin/pip install -r requirements.txt
fi

# Configuration & Directories
mkdir -p storage/cache storage/tasks models logs resource .streamlit
if [ ! -f "config.toml" ] && [ -f "config.example.toml" ]; then
    cp config.example.toml config.toml
fi
if [ ! -f ".streamlit/credentials.toml" ]; then
    printf "[general]\nemail = \"\"\n" > .streamlit/credentials.toml
fi

echo ""
echo "========================================================"
echo "  Setup Complete! Start the app using: ./run.sh or"
echo "  venv/bin/streamlit run webui/Main.py"
echo "========================================================"
