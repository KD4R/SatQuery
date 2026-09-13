"""
P6-15 — Release candidate, immutable images and rollback

Unit tests for infrastructure/release/implementation.py
"""

import json
from unittest.mock import patch

import pytest

from infrastructure.release.implementation import (
    ImageRef,
    ReleaseManifest,
    create_release_manifest,
    generate_rollback_script,
    get_git_sha,
    get_next_version,
    save_manifest,
)

pytestmark = pytest.mark.unit


class TestImageRef:
    def test_full_ref_construction(self):
        ref = ImageRef(
            name="satquery-api", tag="v1.0.0-abc1234", sha="abc1234", built_at="2026-01-01"
        )
        assert ref.full_ref == "satquery-api:v1.0.0-abc1234"

    def test_image_ref_frozen(self):
        ref = ImageRef(name="api", tag="v1", sha="a", built_at="t")
        with pytest.raises(AttributeError):
            ref.tag = "v2"  # type: ignore[misc]


class TestReleaseManifest:
    def test_manifest_to_dict(self):
        manifest = ReleaseManifest(
            version="v1.0.0",
            git_sha="abc1234",
            built_at="2026-01-01T00:00:00Z",
            images={"api": "satquery-api:v1.0.0-abc1234"},
            status="candidate",
        )
        d = manifest.to_dict()
        assert d["version"] == "v1.0.0"
        assert d["git_sha"] == "abc1234"
        assert d["status"] == "candidate"
        assert "api" in d["images"]

    def test_manifest_frozen(self):
        manifest = ReleaseManifest(version="v1", git_sha="a", built_at="t")
        with pytest.raises(AttributeError):
            manifest.version = "v2"  # type: ignore[misc]


class TestVersionCalculation:
    def test_first_version(self, tmp_path):
        manifest_path = tmp_path / "manifest.json"
        version = get_next_version(manifest_path)
        assert version == "v0.1.0"

    def test_increment_patch(self, tmp_path):
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"version": "v1.2.3"}))
        version = get_next_version(manifest_path)
        assert version == "v1.2.4"

    def test_increment_minor(self, tmp_path):
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps({"version": "v1.9.9"}))
        version = get_next_version(manifest_path)
        assert version == "v1.9.10"


class TestManifestCreation:
    def test_create_manifest(self):
        manifest = create_release_manifest(
            version="v1.0.0",
            images={"api": "satquery-api:v1.0.0-abc"},
        )
        assert manifest.version == "v1.0.0"
        assert manifest.status == "candidate"
        assert "api" in manifest.images

    def test_create_manifest_auto_version(self):
        manifest = create_release_manifest()
        assert manifest.version.startswith("v")
        assert manifest.git_sha != ""

    def test_save_and_reload_manifest(self, tmp_path):
        manifest_path = tmp_path / "manifest.json"
        manifest = create_release_manifest(version="v2.0.0")
        with patch("infrastructure.release.implementation.MANIFEST_FILE", manifest_path):
            save_manifest(manifest)
            assert manifest_path.exists()
            with open(manifest_path) as f:
                data = json.load(f)
            assert data["version"] == "v2.0.0"


class TestRollbackScript:
    def test_rollback_script_generated(self):
        manifest = ReleaseManifest(
            version="v1.0.0",
            git_sha="abc1234",
            built_at="2026-01-01T00:00:00Z",
            images={"api": "satquery-api:v1.0.0-abc1234"},
        )
        script = generate_rollback_script(manifest)
        assert "#!/usr/bin/env bash" in script
        assert "v1.0.0" in script
        assert "docker pull" in script

    def test_rollback_script_has_shebang(self):
        manifest = ReleaseManifest(version="v1.0.0", git_sha="a", built_at="t")
        script = generate_rollback_script(manifest)
        assert script.startswith("#!/usr/bin/env bash")


class TestGitSha:
    @patch("subprocess.run")
    def test_git_sha_returns_short_hash(self, mock_run):
        mock_run.return_value = type("R", (), {"returncode": 0, "stdout": "abc1234\n"})()
        sha = get_git_sha()
        assert sha == "abc1234"

    @patch("subprocess.run")
    def test_git_sha_handles_failure(self, mock_run):
        mock_run.return_value = type("R", (), {"returncode": 1, "stdout": ""})()
        sha = get_git_sha()
        assert sha == "unknown"
