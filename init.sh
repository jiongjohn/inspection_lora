#!/usr/bin/env bash
# init.sh — Environment setup and validation for the inspection_lora project.
# Run this at the start of every agent session.
# Usage: source init.sh   (or: bash init.sh)

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "  inspection_lora — Environment Init"
echo "=========================================="
echo "Project root: $PROJECT_ROOT"
echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# ------------------------------------------
# 1. Python version check
# ------------------------------------------
echo "--- [1/6] Python version check ---"
PYTHON=""
if [ -f "$PROJECT_ROOT/.venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    echo "FAIL: No python found. Create venv first: python3 -m venv .venv"
    exit 1
fi

PY_VERSION=$($PYTHON -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$($PYTHON -c "import sys; print(sys.version_info.major)")
PY_MINOR=$($PYTHON -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
    echo "FAIL: Python >= 3.11 required, got $PY_VERSION"
    exit 1
fi
echo "OK: Python $PY_VERSION ($PYTHON)"

# ------------------------------------------
# 2. Virtual environment check
# ------------------------------------------
echo ""
echo "--- [2/6] Virtual environment check ---"
if [ -d "$PROJECT_ROOT/.venv" ]; then
    echo "OK: .venv directory exists"
    # Activate if running via source
    if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate" 2>/dev/null || true
        echo "OK: venv activated"
    fi
else
    echo "WARN: .venv not found. Creating..."
    $PYTHON -m venv .venv
    source "$PROJECT_ROOT/.venv/bin/activate"
    echo "OK: venv created and activated"
fi

# Use venv python from here
PYTHON="$PROJECT_ROOT/.venv/bin/python"

# ------------------------------------------
# 3. Core dependencies check
# ------------------------------------------
echo ""
echo "--- [3/6] Core dependencies check ---"
DEPS_OK=true

check_dep() {
    local pkg="$1"
    if $PYTHON -c "import $pkg" 2>/dev/null; then
        local ver=$($PYTHON -c "import $pkg; print(getattr($pkg, '__version__', 'unknown'))" 2>/dev/null)
        echo "  OK: $pkg ($ver)"
    else
        echo "  MISSING: $pkg"
        DEPS_OK=false
    fi
}

check_dep mlx
check_dep mlx_lm
check_dep transformers
check_dep datasets
check_dep yaml
check_dep jsonlines
check_dep numpy

if [ "$DEPS_OK" = false ]; then
    echo ""
    echo "Some dependencies missing. Installing..."
    $PYTHON -m pip install -r requirements.txt -q
    $PYTHON -m pip install -e ".[dev]" -q
    echo "Dependencies installed. Re-checking..."
    check_dep mlx
    check_dep mlx_lm
fi

# ------------------------------------------
# 4. Project structure check
# ------------------------------------------
echo ""
echo "--- [4/6] Project structure check ---"
STRUCT_OK=true

check_dir() {
    if [ -d "$1" ]; then
        echo "  OK: $1/"
    else
        echo "  MISSING: $1/"
        STRUCT_OK=false
    fi
}

check_file() {
    if [ -f "$1" ]; then
        echo "  OK: $1"
    else
        echo "  MISSING: $1"
        STRUCT_OK=false
    fi
}

check_dir "src/inspection_lora"
check_dir "configs"
check_dir "data/templates"
check_dir "data/generated"
check_dir "data/processed"
check_dir "scripts"
check_dir "openspec"
check_file "pyproject.toml"
check_file "requirements.txt"
check_file "configs/lora_config.yaml"
check_file "feature_list.json"
check_file "agent-progress.md"

if [ "$STRUCT_OK" = false ]; then
    echo "WARN: Some directories/files missing. Create them before proceeding."
fi

# ------------------------------------------
# 5. Source code syntax check
# ------------------------------------------
echo ""
echo "--- [5/6] Source code syntax check ---"
SYNTAX_OK=true

check_syntax() {
    local f="$1"
    if [ -f "$f" ]; then
        if $PYTHON -c "import py_compile; py_compile.compile('$f', doraise=True)" 2>/dev/null; then
            echo "  OK: $f"
        else
            echo "  SYNTAX ERROR: $f"
            SYNTAX_OK=false
        fi
    fi
}

# Check core source files
for f in src/inspection_lora/*.py; do
    [ -f "$f" ] && check_syntax "$f"
done

# Check template files
for f in data/templates/*.py; do
    [ -f "$f" ] && check_syntax "$f"
done

# Check scripts
for f in scripts/*.py; do
    [ -f "$f" ] && check_syntax "$f"
done

if [ "$SYNTAX_OK" = false ]; then
    echo "WARN: Syntax errors found. Fix before running pipelines."
fi

# ------------------------------------------
# 6. Feature progress summary
# ------------------------------------------
echo ""
echo "--- [6/6] Feature progress summary ---"
if [ -f "feature_list.json" ]; then
    TOTAL=$($PYTHON -c "
import json
with open('feature_list.json') as f:
    features = json.load(f)
total = len(features)
passed = sum(1 for f in features if f.get('passes'))
failed = total - passed
print(f'Total: {total}  Passed: {passed}  Remaining: {failed}')
for phase in sorted(set(f['phase'] for f in features)):
    phase_features = [f for f in features if f['phase'] == phase]
    phase_passed = sum(1 for f in phase_features if f.get('passes'))
    print(f'  Phase {phase}: {phase_passed}/{len(phase_features)} passed')
")
    echo "$TOTAL"
else
    echo "WARN: feature_list.json not found"
fi

# ------------------------------------------
# Summary
# ------------------------------------------
echo ""
echo "=========================================="
echo "  Init complete."
if [ "$SYNTAX_OK" = true ] && [ "$STRUCT_OK" = true ] && [ "$DEPS_OK" = true ]; then
    echo "  Status: ALL CHECKS PASSED"
else
    echo "  Status: ISSUES FOUND (see above)"
fi
echo "=========================================="
echo ""
echo "Next steps for agent:"
echo "  1. Read agent-progress.md for session history"
echo "  2. Read feature_list.json for current feature status"
echo "  3. Check git log --oneline -20 for recent changes"
echo "  4. Pick the highest-priority incomplete feature"
echo "  5. Implement ONE feature, test it, mark it passed"
echo "  6. Git commit + update agent-progress.md"
