# scripts/bootstrap-dev.ps1 — run once per clone. Safe to re-run.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)

# 1. Route git hooks to the committed directory
git config core.hooksPath .githooks
Write-Host "hooks -> .githooks"

# 2. Python dependencies (runtime + dev tools)
if (Get-Command python -ErrorAction SilentlyContinue) {
    python -m pip install -q -r requirements.txt -r requirements-dev.txt
    Write-Host "python deps: ready"
}

# 3. Secret-scanning framework (optional; the fallback hook works without it)
if (Get-Command pre-commit -ErrorAction SilentlyContinue) {
    pre-commit install --install-hooks | Out-Null
    Write-Host "pre-commit: ready"
} else {
    Write-Host "pre-commit not installed - using the inline fallback scan."
    Write-Host "  For the full scan: pip install pre-commit"
}

# 4. Knowledge graph: build once if missing (--code-only without an LLM key,
#    otherwise graphify exits "successfully" without writing graph.json)
$graphifyArgs = @('.')
if (-not ($env:GEMINI_API_KEY -or $env:GOOGLE_API_KEY -or $env:ANTHROPIC_API_KEY -or $env:OPENAI_API_KEY -or $env:MOONSHOT_API_KEY -or $env:DEEPSEEK_API_KEY)) {
    $graphifyArgs += '--code-only'
}
if (Get-Command graphify -ErrorAction SilentlyContinue) {
    if (-not (Test-Path 'graphify-out/graph.json')) {
        Write-Host "Building the knowledge graph (first run, may take a while)..."
        graphify @graphifyArgs
    } else {
        graphify @graphifyArgs --update
    }
    if (Test-Path 'graphify-out/graph.json') {
        Write-Host "graphify: ready"
    } else {
        Write-Host "graphify: extraction did not produce graphify-out/graph.json - check the output above"
    }
} else {
    Write-Host "graphify not installed - agents will fall back to plain search."
    Write-Host "  To enable: uv tool install graphifyy; graphify install"
}
