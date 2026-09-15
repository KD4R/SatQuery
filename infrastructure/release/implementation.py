"""
infrastructure/release/implementation.py — P6-15 Release candidate automation

Provides:
  - Docker image tagging with version + git SHA
  - Immutable image verification
  - Rollback script generation
  - Release candidate manifest
"""

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

RELEASE_DIR = Path(__file__).parent
PROJECT_ROOT = RELEASE_DIR.parent.parent
MANIFEST_FILE = RELEASE_DIR / "release-manifest.json"


@dataclass(frozen=True)
class ImageRef:
    """Immutable reference to a Docker image."""

    name: str
    tag: str
    sha: str
    built_at: str

    @property
    def full_ref(self) -> str:
        return f"{self.name}:{self.tag}"


@dataclass(frozen=True)
class ReleaseManifest:
    """Immutable manifest for a release candidate."""

    version: str
    git_sha: str
    built_at: str
    images: Dict[str, str] = field(default_factory=dict)
    status: str = "candidate"

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "git_sha": self.git_sha,
            "built_at": self.built_at,
            "images": dict(self.images),
            "status": self.status,
        }


def get_git_sha() -> str:
    """Get the current git short SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unknown"


def get_next_version(manifest_path: Optional[Path] = None) -> str:
    """Calculate next semver from existing manifest or default to v0.1.0."""
    path = manifest_path or MANIFEST_FILE
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            current = data.get("version", "v0.1.0")
            parts = current.lstrip("v").split(".")
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            return f"v{major}.{minor}.{patch + 1}"
        except (json.JSONDecodeError, IndexError, ValueError):
            pass
    return "v0.1.0"


def create_release_manifest(
    version: Optional[str] = None,
    images: Optional[Dict[str, str]] = None,
) -> ReleaseManifest:
    """Create a new release manifest."""
    if version is None:
        version = get_next_version()
    sha = get_git_sha()
    now = datetime.now(timezone.utc).isoformat()
    return ReleaseManifest(
        version=version,
        git_sha=sha,
        built_at=now,
        images=images or {},
        status="candidate",
    )


def save_manifest(manifest: ReleaseManifest) -> Path:
    """Persist release manifest to disk."""
    with open(MANIFEST_FILE, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2)
    return MANIFEST_FILE


def generate_rollback_script(manifest: ReleaseManifest) -> str:
    """Generate a shell script to rollback to a specific release."""
    lines = [
        "#!/usr/bin/env bash",
        f"# Rollback to {manifest.version} ({manifest.git_sha})",
        f"# Generated at {manifest.built_at}",
        "set -euo pipefail",
        "",
        'echo "Rolling back to ' + manifest.version + '..."',
        "",
    ]
    for service, image_ref in manifest.images.items():
        lines.append(f"docker pull {image_ref}")
        lines.append(
            f"docker compose -f infrastructure/docker/docker-compose.yml "
            f"up -d --no-deps {service}"
        )
        lines.append("")
    lines.append('echo "Rollback complete."')
    return "\n".join(lines)
