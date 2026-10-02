"""Release invariants of the VS Code extension (ken #1132).

publish.sh syncs vscode/package.json to the bumped nagioscli version so the
.vsix attached to the GitHub release carries the release it was built
with. These tests keep the manifest and its packaging honest between
releases, without needing node.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from nagioscli import __version__

VSCODE = Path(__file__).resolve().parents[2] / "vscode"

# The sdist ships tests/ but not vscode/: nothing to check there.
pytestmark = pytest.mark.skipif(not VSCODE.is_dir(), reason="vscode/ not in this tree")


def _manifest() -> dict[str, Any]:
    manifest: dict[str, Any] = json.loads((VSCODE / "package.json").read_text(encoding="utf-8"))
    return manifest


class TestVscodeManifest:
    """vscode/package.json and .vscodeignore, as publish.sh relies on them."""

    def test_version_matches_nagioscli(self) -> None:
        """The manifest carries the nagioscli version (publish.sh syncs it)."""
        assert _manifest()["version"] == __version__

    def test_single_version_key_for_the_publish_sed(self) -> None:
        """publish.sh rewrites every `"version": "..."` line: only one may exist."""
        text = (VSCODE / "package.json").read_text(encoding="utf-8")
        assert text.count('"version":') == 1

    def test_every_contributed_command_is_registered(self) -> None:
        """Each command of the manifest is registered by src/extension.js."""
        manifest = _manifest()
        declared = {c["command"] for c in manifest["contributes"]["commands"]}
        source = (VSCODE / "src" / "extension.js").read_text(encoding="utf-8")
        assert declared
        for command in declared:
            assert f"'{command}'" in source, command

    def test_menus_only_reference_contributed_commands(self) -> None:
        """No menu entry points at a command the manifest does not declare."""
        manifest = _manifest()
        declared = {c["command"] for c in manifest["contributes"]["commands"]}
        for entries in manifest["contributes"]["menus"].values():
            for entry in entries:
                assert entry["command"] in declared, entry

    def test_no_runtime_dependencies(self) -> None:
        """vsce runs with --no-dependencies: a runtime dep would be missing at install."""
        assert "dependencies" not in _manifest()

    def test_icon_is_shipped(self) -> None:
        """The gallery icon referenced by the manifest exists."""
        assert (VSCODE / _manifest()["icon"]).is_file()

    def test_vsix_ships_sources_only(self) -> None:
        """Tests, toolchain and coverage output stay out of the .vsix."""
        ignored = (VSCODE / ".vscodeignore").read_text(encoding="utf-8").splitlines()
        for pattern in ("node_modules/**", "test/**", "lcov.info", "test-report.txt"):
            assert pattern in ignored
