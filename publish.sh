#!/bin/sh

# The whole script is one { ... } block: the shell parses it entirely before
# running the first line. Without it, sh reads the file as it executes, so
# editing publish.sh during a run (e.g. a commit while the SonarCloud gate
# waits) shifts the byte offsets and the run resumes mid-line (pattern
# semacli ken #1131, imported with the VS Code extension, ken #1132).
{

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

# Set total steps based on mode (one per print_step call — the semacli
# script showed hand-numbered steps drift as the pipeline grows):
#   18 = 15 Python gates + 3 VS Code extension gates (ken #1132)
#   +11 publish-only: push, sonar gate, bump, build, .vsix, PyPI, wiki sync,
#       wiki build, git commit + tag + push, GitHub release, clean
if [ "$QUALITY_ONLY" = true ]; then
    STEPS=18
else
    STEPS=29
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
run_command "pdm run test-publish" "Tests (full suite, coverage)"

# VS Code extension (ken #1132): own npm toolchain under vscode/. npm ci
# from the committed lockfile, then a blocking audit — a known vulnerability
# in the toolchain stops the release (bump the dependency, don't ignore it).
print_step "Installing VS Code Extension Dependencies (npm ci)"
run_command "pdm run vscode-install" "VS Code extension dependencies"

print_step "VS Code Extension Security Audit (npm audit)"
run_command "pdm run vscode-audit" "VS Code extension security audit"

print_step "VS Code Extension: lint + type check + tests (coverage gate)"
run_command "pdm run vscode-lint" "VS Code extension lint + format (biome)"
run_command "pdm run vscode-typecheck" "VS Code extension type check (tsc)"
run_command "pdm run vscode-test" "VS Code extension tests + coverage"

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
VERSION=$(grep '^__version__' nagioscli/__init__.py | cut -d'"' -f2)
# The .vsix carries the nagioscli release it was built with (ken #1132).
# `"version"` is the only such key in vscode/package.json (guarded by
# tests/unit/test_vscode_extension.py); portable sed (BSD + GNU).
sed -i.bak 's/"version": "[^"]*"/"version": "'"${VERSION}"'"/' vscode/package.json && rm vscode/package.json.bak
grep -q "\"version\": \"${VERSION}\"" vscode/package.json || print_error "vscode/package.json not synced to ${VERSION}"
print_success "Version ${VERSION} synced to vscode/package.json"

print_step "Building Package (pdm build)"
run_command "pdm build" "Package build"

# Packaged BEFORE the PyPI upload: a vsce failure aborts while nothing is
# live yet. vsce names the file after vscode/package.json's version, so the
# check below also proves the .vsix matches the release (kenboard ken #1130).
print_step "Packaging VS Code Extension (.vsix)"
VSIX="vscode/nagioscli-vscode-${VERSION}.vsix"
rm -f vscode/*.vsix
run_command "pdm run vscode-package" "VS Code extension package"
[ -f "${VSIX}" ] || print_error "vsce did not produce ${VSIX}"

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
# same scheme as the existing tags). Non-fatal: PyPI is already updated, so
# a git hiccup must not abort the script — the operator pushes manually.
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

# ── GitHub release with the VS Code extension (ken #1132) ────────────────
# PyPI is live by now: stop on error, but print the exact recovery command.
# The tag must point at the release commit — the git step above is soft, so
# check HEAD before tagging. Idempotent: an existing release (re-run) gets
# the asset re-uploaded with --clobber. Creating the release fires
# python-publish.yml, whose `twine upload --skip-existing` is then a no-op.
TAG="v${VERSION}"
print_step "GitHub Release ${TAG} (.vsix)"
RECOVER="git tag ${TAG} && git push origin ${TAG} && gh release create ${TAG} --verify-tag --title 'nagioscli ${VERSION}' --generate-notes ${VSIX}"
[ "$(git log -1 --format=%s)" = "${COMMIT_MSG}" ] \
    || print_error "HEAD is not the release commit — recover by hand: ${RECOVER}"
command -v gh > /dev/null 2>&1 || print_error "gh CLI not found — recover: ${RECOVER}"
git rev-parse -q --verify "refs/tags/${TAG}" > /dev/null || run_command "git tag ${TAG}" "Git tag ${TAG}"
run_command "git push origin ${TAG}" "Push tag ${TAG}"
if gh release view "${TAG}" > /dev/null 2>&1; then
    run_command "gh release upload ${TAG} ${VSIX} --clobber" "Attach $(basename "${VSIX}") to ${TAG}"
else
    run_command "gh release create ${TAG} --verify-tag --title 'nagioscli ${VERSION}' --generate-notes ${VSIX}" \
        "GitHub release ${TAG} with $(basename "${VSIX}")"
fi

print_step "Cleaning Build Artifacts (pdm run clean)"
run_command_soft "pdm run clean" "Clean"

echo ""
echo "${GREEN}${BOLD}🎉 PUBLISHING COMPLETED SUCCESSFULLY! 🎉${NC}"
echo "${GREEN}${BOLD}═══════════════════════════════════════════════════════════════${NC}"
echo "${GREEN}nagioscli v${VERSION} has been published to PyPI and tagged.${NC}"
echo "${GREEN}GitHub release v${VERSION} carries nagioscli-vscode-${VERSION}.vsix.${NC}"
echo "${GREEN}Wiki sync + build + git push ran in non-fatal mode after.${NC}"
echo ""

exit 0
}
