#!/bin/sh
# scripts/bootstrap-dev.sh — run once per clone. Safe to re-run.
set -e
cd "$(dirname "$0")/.."

# 1. Route git hooks to the committed directory
git config core.hooksPath .githooks
chmod +x .githooks/* 2>/dev/null || true
echo "hooks -> .githooks"

# 2. Python dependencies (runtime + dev tools)
if command -v python >/dev/null 2>&1; then
  python -m pip install -q -r requirements.txt -r requirements-dev.txt
  echo "python deps: ready"
fi

# 3. Secret-scanning framework (optional; the fallback hook works without it)
if command -v pre-commit >/dev/null 2>&1; then
  pre-commit install --install-hooks >/dev/null
  echo "pre-commit: ready"
else
  echo "pre-commit not installed - using the inline fallback scan."
  echo "  For the full scan: pip install pre-commit"
fi

# 4. Knowledge graph: build once if missing (--code-only without an LLM key)
GRAPHIFY_ARGS="."
if [ -z "$GEMINI_API_KEY$GOOGLE_API_KEY$ANTHROPIC_API_KEY$OPENAI_API_KEY$MOONSHOT_API_KEY$DEEPSEEK_API_KEY" ]; then
  GRAPHIFY_ARGS=". --code-only"
fi
if command -v graphify >/dev/null 2>&1; then
  if [ ! -f graphify-out/graph.json ]; then
    echo "Building the knowledge graph (first run, may take a while)..."
    graphify $GRAPHIFY_ARGS || true
  else
    graphify $GRAPHIFY_ARGS --update || true
  fi
  if [ -f graphify-out/graph.json ]; then
    echo "graphify: ready"
  else
    echo "graphify: extraction did not produce graphify-out/graph.json - check the output above"
  fi
else
  echo "graphify not installed - agents will fall back to plain search."
  echo "  To enable: uv tool install graphifyy; graphify install"
fi
