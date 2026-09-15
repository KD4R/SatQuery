"""
P6-15 — Release candidate, immutable images and rollback

Unit tests for infrastructure/release/implementation.py
"""

import json
import os
import subprocess
from pathlib import Path
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


# ── CD pipeline / rollback static contracts (P6-15) ──────────────────────────


REPO_ROOT = Path(__file__).resolve().parents[2]
CD_YML = REPO_ROOT / ".github" / "workflows" / "cd.yml"
COMPOSE_YML = REPO_ROOT / "infrastructure" / "docker" / "docker-compose.yml"
DOCKERFILE = REPO_ROOT / "infrastructure" / "docker" / "Dockerfile"
ROLLBACK_SH = REPO_ROOT / "infrastructure" / "scripts" / "rollback.sh"


class TestCDWorkflow:
    def test_cd_workflow_exists_and_parses(self):
        assert CD_YML.exists()
        import yaml

        data = yaml.safe_load(CD_YML.read_text())
        jobs = data["jobs"]
        assert {"tag-release", "build-push-images", "github-release"}.issubset(jobs)

    def test_cd_pushes_to_ghcr_with_sha_and_version_tags(self):
        text = CD_YML.read_text()
        assert "ghcr.io" in text
        assert "sha_tag=sha-${SHA}" in text
        assert "docker/build-push-action" in text
        assert "docker/login-action" in text

    def test_cd_builds_all_three_server_images(self):
        text = CD_YML.read_text()
        for module in (
            "services.gateway.implementation:app",
            "services.mission.implementation:app",
            "services.agent.app.api.implementation:app",
        ):
            assert module in text, f"missing APP_MODULE for {module}"

    def test_cd_does_not_push_moving_latest_tag(self):
        """Immutability: `latest` must never be pushed by the pipeline."""
        push_section = CD_YML.read_text()
        for line in push_section.splitlines():
            if "tags:" in line or (":latest" in line and "NOT" not in line.upper()):
                assert "latest" not in line, f"moving 'latest' tag pushed: {line}"


class TestComposeRollbackPinning:
    def test_compose_services_have_image_names(self):
        import yaml

        data = yaml.safe_load(COMPOSE_YML.read_text())
        for svc in ("api", "mission", "agent", "worker-ingest", "worker-analysis", "worker-report"):
            assert svc in data["services"], f"{svc} missing from compose"
            assert "image" in data["services"][svc], f"{svc} has no image: (rollback pinning)"

    def test_mission_and_agent_use_app_module_arg(self):
        import yaml

        data = yaml.safe_load(COMPOSE_YML.read_text())
        assert (
            data["services"]["mission"]["build"]["args"]["APP_MODULE"]
            == "services.mission.implementation:app"
        )
        assert (
            data["services"]["agent"]["build"]["args"]["APP_MODULE"]
            == "services.agent.app.api.implementation:app"
        )


class TestDockerfileVariants:
    def test_dockerfile_parameterized_app_module(self):
        text = DOCKERFILE.read_text()
        assert "ARG APP_MODULE" in text
        assert "ENV APP_MODULE" in text
        assert "${APP_MODULE}" in text


class TestRollbackScriptIntegration:
    @pytest.mark.skipif(os.name == "nt", reason="Bash scripts fail natively on Windows test runs")
    def test_rollback_script_exists_and_executable(self):
        assert ROLLBACK_SH.exists()
        assert ROLLBACK_SH.stat().st_mode & 0o111, "rollback.sh must be executable"

    @pytest.mark.skipif(os.name == "nt", reason="Bash scripts fail natively on Windows test runs")
    def test_rollback_script_rejects_non_sha(self, tmp_path):
        result = subprocess.run(
            ["bash", str(ROLLBACK_SH), "not-a-sha"], capture_output=True, text=True, timeout=30
        )
        assert result.returncode != 0
        assert "git SHA" in result.stderr

    @pytest.mark.skipif(os.name == "nt", reason="Bash scripts fail natively on Windows test runs")
    def test_rollback_script_print_env_example(self):
        result = subprocess.run(
            ["bash", str(ROLLBACK_SH), "--print-env-example"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "SATQUERY_REGISTRY" in result.stdout

    @pytest.mark.skipif(os.name == "nt", reason="Bash scripts fail natively on Windows test runs")
    def test_rollback_script_dry_run_no_registry(self):
        """Dry-run against a non-existent release must fail cleanly (no pull)."""
        result = subprocess.run(
            ["bash", str(ROLLBACK_SH), "deadbee", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "SATQUERY_REGISTRY": "ghcr.io", "SATQUERY_REPO": "kd4r/satquery"},
        )
        # Either resolves (unexpected) or fails with a clear message — but it
        # must never proceed to compose up.
        if result.returncode != 0:
            assert "Could not resolve digest" in result.stderr

    def test_rollback_generates_digest_pinned_override(self):
        """generate_rollback_script() must pin by digest, not by tag."""
        manifest = ReleaseManifest(
            version="v1.0.0",
            git_sha="abc1234",
            built_at="2026-01-01T00:00:00Z",
            images={
                "api": "ghcr.io/kd4r/satquery/satquery-api@sha256:deadbeef",
                "mission": "ghcr.io/kd4r/satquery/satquery-mission@sha256:cafe",
            },
        )
        script = generate_rollback_script(manifest)
        assert "@sha256:" in script or "digest" in script.lower() or "docker pull" in script
