#!/bin/sh

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Parse command line arguments (pattern kenboard publish.sh)
QUALITY_ONLY=false
BUMP_TYPE="patch"
for arg in "$@"; do
    case $arg in
        --quality)
            QUALITY_ONLY=true
            shift
            ;;
        --major)
            BUMP_TYPE="major"
            shift
            ;;
        --minor)
            BUMP_TYPE="minor"
            shift
            ;;
        --patch)
            BUMP_TYPE="patch"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--quality] [--major|--minor|--patch] [--help]"
            echo ""
            echo "Options:"
            echo "  --quality       Run only quality checks without publishing"
            echo "  --major         Bump major version (x.0.0)"
            echo "  --minor         Bump minor version (0.x.0)"
            echo "  --patch         Bump patch version (0.0.x) [default]"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Set total steps based on mode (auto-incremented counter — the semacli
# script showed hand-numbered steps drift as the pipeline grows)
if [ "$QUALITY_ONLY" = true ]; then
    STEPS=15
else
    STEPS=24
fi
STEP=0

# Function to print step headers
print_step() {
    STEP=$((STEP + 1))
    echo ""
    echo "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo "${BLUE}${BOLD}  $STEP/$STEPS $1${NC}"
    echo "${BLUE}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Function to print success message
print_success() {
    echo "${GREEN}${BOLD}✓ $1${NC}"
}

# Function to print error message and exit
print_error() {
    echo "${RED}${BOLD}✗ $1${NC}"
    exit 1
}

# Function to run command with error handling
run_command() {
    local cmd="$1"
    local description="$2"

    echo "${YELLOW}→ Running: ${cmd}${NC}"

    if eval "$cmd"; then
        print_success "$description completed successfully"
    else
        print_error "$description failed"
    fi
}

# Non-fatal variant: warns on failure but does not exit. Used after the
# PyPI publish (wiki sync/build, release commit) so a hiccup there never
# invalidates a release that is already live — and for informational
# steps like the outdated-dependencies report.
run_command_soft() {
    local cmd="$1"
    local description="$2"

    echo "${YELLOW}→ Running: ${cmd}${NC}"

    if eval "$cmd"; then
        print_success "$description completed successfully"
    else
        echo "${YELLOW}${BOLD}⚠ $description failed (continuing)${NC}"
    fi
}

echo "${BOLD}${BLUE}"
echo "███╗   ██╗ █████╗  ██████╗ ██╗ ██████╗ ███████╗ ██████╗██╗     ██╗"
echo "████╗  ██║██╔══██╗██╔════╝ ██║██╔═══██╗██╔════╝██╔════╝██║     ██║"
echo "██╔██╗ ██║███████║██║  ███╗██║██║   ██║███████╗██║     ██║     ██║"
echo "██║╚██╗██║██╔══██║██║   ██║██║██║   ██║╚════██║██║     ██║     ██║"
echo "██║ ╚████║██║  ██║╚██████╔╝██║╚██████╔╝███████║╚██████╗███████╗██║"
echo "╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝ ╚═╝ ╚═════╝ ╚══════╝ ╚═════╝╚══════╝╚═╝"
echo "${NC}"
if [ "$QUALITY_ONLY" = true ]; then
    echo "${BOLD}Starting Quality Checks...${NC}"
else
    echo "${BOLD}Starting Package Publishing Process...${NC}"
fi

print_step "Cleaning Previous Build (pdm run clean)"
run_command "pdm run clean" "Clean"

print_step "Syncing Lockfile (pdm lock -G :all)"
run_command "pdm lock -G :all" "Lockfile sync"

print_step "Installing Dependencies (pdm install)"
run_command "pdm run install" "Dependencies installation"

print_step "Installing Development Dependencies (pdm install-dev)"
run_command "pdm run install-dev" "Development dependencies installation"

# Informational only: lists what could be upgraded. Deliberately soft and
# without an auto `pdm update` (kenboard runs one) — a publish should not
# silently change locked dependency versions.
print_step "Checking for Outdated Dependencies (pdm outdated)"
run_command_soft "pdm outdated" "Outdated dependencies report"

print_step "Code Formatting (ruff format)"
run_command "pdm run format" "Code formatting"

print_step "Format Check (black --check)"
run_command "pdm run format-check" "Format check"

print_step "Code Linting (ruff)"
run_command "pdm run lint" "Linting"

print_step "Architecture Check (import-linter)"
run_command "pdm run arch" "Architecture check"

print_step "Type Checking (mypy)"
run_command "pdm run typecheck" "Type checking"

print_step "Docstring Coverage (interrogate)"
run_command "pdm run interrogate" "Docstring coverage"

print_step "Dead Code Check (vulture)"
run_command "pdm run vulture" "Dead code check"

print_step "Code Quality Check (refurb)"
run_command "pdm run refurb" "Code quality check"

# Full suite with coverage: the metrics gate below reads the .coverage
# file this run leaves behind.
print_step "Running Tests (full suite, coverage)"
run_command "pdm run test" "Tests (full suite, coverage)"

# Blocking quality-metrics gate (pattern semacli ken #828): absolute
# ceilings + best-ever ratchet against doc/quality-history.csv — see
# doc/code-quality.md.
print_step "Quality Metrics Gate (ratchet)"
run_command "pdm run metrics-gate" "Quality metrics gate"

# Exit here if --quality flag is set
if [ "$QUALITY_ONLY" = true ]; then
    echo ""
    echo "${GREEN}${BOLD}🎉 QUALITY CHECKS COMPLETED SUCCESSFULLY! 🎉${NC}"
    echo "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
    echo "${GREEN}All quality checks have passed.${NC}"
    echo ""
    exit 0
fi

# Push the (already committed) work so the GitHub CI runs the SonarCloud
# analysis of HEAD, then block on the live quality gate (pattern kenboard
# ken #835/#995 — soft timeout, extended while CI / Sonar compute-engine
# queue shows life, hard cap --max-wait 3600s).
print_step "Pushing Code for SonarCloud Analysis"
run_command "git push" "Push for analysis"

print_step "SonarCloud Quality Gate"
run_command "pdm run sonar-gate" "SonarCloud quality gate"

print_step "Bumping Version (pdm run version-${BUMP_TYPE})"
run_command "pdm run version-${BUMP_TYPE}" "Version bump"

print_step "Building Package (pdm build)"
run_command "pdm build" "Package build"

print_step "Publishing Package to PyPI (pdm publish)"
run_command "pdm publish" "Package publishing"

# ── Kenboard wiki sync / build ───────────────────────────────────────────
# Run AFTER PyPI publish so a wiki hiccup never invalidates a release that
# is already live. Non-fatal (run_command_soft): a missing `ken` or board
# API warns but does not abort the script.

print_step "Wiki Sync (ken wiki sync)"
run_command_soft "ken wiki sync" "Wiki sync"

print_step "Wiki Build (ken wiki build)"
run_command_soft "ken wiki build" "Wiki build"

# ── Git commit + tag + push ──────────────────────────────────────────────
# Captures the version bump, the regenerated wiki, and any other tracked
# changes still in the working tree, then tags the release (v<version>,
# same scheme as the existing tags). No `gh release create` here: the
# python-publish.yml workflow uploads to PyPI on GitHub release publication
# and would double-publish. Non-fatal: PyPI is already updated, so a git
# hiccup must not abort the script — the operator pushes manually.
VERSION=$(grep '^__version__' nagioscli/__init__.py | cut -d'"' -f2)
print_step "Git Commit + Tag + Push (release artifacts)"
COMMIT_MSG="release: v${VERSION} — auto by publish.sh"
echo "${YELLOW}→ Running: git add -A && git commit -m \"${COMMIT_MSG}\" && git tag v${VERSION} && git push && git push --tags${NC}"
if git add -A && git diff --cached --quiet; then
    echo "${YELLOW}${BOLD}⚠ Nothing to commit (working tree already clean)${NC}"
elif git commit -m "$COMMIT_MSG"; then
    print_success "Git commit completed (${COMMIT_MSG})"
    if git tag "v${VERSION}"; then
        print_success "Git tag v${VERSION} created"
    else
        echo "${YELLOW}${BOLD}⚠ Git tag failed — tag v${VERSION} manually${NC}"
    fi
    if git push && git push --tags; then
        print_success "Git push completed"
    else
        echo "${YELLOW}${BOLD}⚠ Git push failed — PyPI is live, push v${VERSION} manually${NC}"
    fi
else
    echo "${YELLOW}${BOLD}⚠ Git commit failed — fix and push v${VERSION} manually${NC}"
fi

print_step "Cleaning Build Artifacts (pdm run clean)"
run_command_soft "pdm run clean" "Clean"

echo ""
echo "${GREEN}${BOLD}🎉 PUBLISHING COMPLETED SUCCESSFULLY! 🎉${NC}"
echo "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo "${GREEN}nagioscli v${VERSION} has been published to PyPI and tagged.${NC}"
echo "${GREEN}Wiki sync + build + git push ran in non-fatal mode after.${NC}"
echo ""
