"""
infrastructure/docker/implementation.py — P6-01 Docker Compose local integration environment

Provides:
  - Docker Compose configuration for local development
  - Service health verification
  - Environment configuration management
  - Integration environment bootstrap and teardown

This module defines the P6-01 infrastructure boundary. It does NOT contain
service logic — it orchestrates the containerized environment that services
run inside.
"""

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


# ── Configuration ─────────────────────────────────────────────────────────────

COMPOSE_DIR = Path(__file__).parent
PROJECT_ROOT = COMPOSE_DIR.parent.parent
COMPOSE_FILE = COMPOSE_DIR / "docker-compose.yml"
ENV_EXAMPLE = COMPOSE_DIR / ".env.example"
ENV_FILE = COMPOSE_DIR / ".env"


@dataclass(frozen=True)
class ServiceConfig:
    """Configuration for a single Docker Compose service."""

    name: str
    port: int
    health_endpoint: str = "/api/v1/health"
    protocol: str = "http"
    depends_on: tuple = ()

    @property
    def url(self) -> str:
        return f"{self.protocol}://localhost:{self.port}"


@dataclass(frozen=True)
class EnvironmentConfig:
    """Complete configuration for the local integration environment."""

    services: Dict[str, ServiceConfig] = field(
        default_factory=lambda: {
            "api": ServiceConfig(name="api", port=8000, depends_on=("postgres", "redis", "minio")),
            "mission": ServiceConfig(name="mission", port=8001, depends_on=("postgres", "redis", "minio")),
            "agent": ServiceConfig(name="agent", port=8002, depends_on=("postgres", "redis", "minio")),
            "web": ServiceConfig(name="web", port=3000, depends_on=("api",)),
            "postgres": ServiceConfig(name="postgres", port=5432, health_endpoint="/"),
            "redis": ServiceConfig(name="redis", port=6379, health_endpoint="/"),
            "minio": ServiceConfig(name="minio", port=9000, health_endpoint="/minio/health/live"),
            "titiler": ServiceConfig(name="titiler", port=8081, health_endpoint="/healthz"),
            "prometheus": ServiceConfig(name="prometheus", port=9090, health_endpoint="/-/healthy"),
            "grafana": ServiceConfig(name="grafana", port=3001, health_endpoint="/api/health"),
            "otel-collector": ServiceConfig(name="otel-collector", port=4317, health_endpoint="/"),
            "worker-ingest": ServiceConfig(name="worker-ingest", port=0),
            "worker-analysis": ServiceConfig(name="worker-analysis", port=0),
            "worker-report": ServiceConfig(name="worker-report", port=0),
        }
    )


# ── Bootstrap ─────────────────────────────────────────────────────────────────


def ensure_env_file() -> Path:
    """Create .env from .env.example if it doesn't exist."""
    if not ENV_FILE.exists():
        if ENV_EXAMPLE.exists():
            import shutil

            shutil.copy2(ENV_EXAMPLE, ENV_FILE)
            return ENV_FILE
    return ENV_FILE


def check_docker_available() -> bool:
    """Check if Docker and Docker Compose are available."""
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_compose_services() -> List[str]:
    """List services defined in docker-compose.yml."""
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--services"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        if result.returncode == 0:
            return [s.strip() for s in result.stdout.strip().split("\n") if s.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []


def start_environment(
    services: Optional[List[str]] = None,
    detach: bool = True,
    build: bool = False,
) -> subprocess.CompletedProcess:
    """Start the Docker Compose environment.

    Args:
        services: Specific services to start. None = all services.
        detach: Run in background (default True).
        build: Force rebuild images before starting.

    Returns:
        CompletedProcess with the command result.
    """
    ensure_env_file()

    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "up"]
    if detach:
        cmd.append("-d")
    if build:
        cmd.append("--build")
    if services:
        cmd.extend(services)

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(PROJECT_ROOT),
    )


def stop_environment(remove_volumes: bool = False) -> subprocess.CompletedProcess:
    """Stop the Docker Compose environment."""
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "down"]
    if remove_volumes:
        cmd.append("-v")

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(PROJECT_ROOT),
    )


def get_service_status() -> Dict[str, str]:
    """Get the status of all services."""
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "ps", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=15,
        cwd=str(PROJECT_ROOT),
    )

    statuses: Dict[str, str] = {}
    if result.returncode == 0:
        for line in result.stdout.strip().split("\n"):
            if line.strip():
                try:
                    svc = json.loads(line)
                    name = svc.get("Service", svc.get("name", "unknown"))
                    state = svc.get("State", svc.get("state", "unknown"))
                    statuses[name] = state
                except json.JSONDecodeError:
                    continue
    return statuses


# ── Health Checks ─────────────────────────────────────────────────────────────


def check_service_health(service_name: str, timeout: float = 5.0) -> bool:
    """Check if a specific service is healthy via HTTP.

    Args:
        service_name: Name of the service to check.
        timeout: HTTP timeout in seconds.

    Returns:
        True if the service responds with 200.
    """
    import urllib.request
    import urllib.error

    config = EnvironmentConfig()
    svc = config.services.get(service_name)
    if not svc or svc.port == 0:
        return False

    url = f"{svc.url}{svc.health_endpoint}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, TimeoutError):
        return False


def check_all_services_healthy() -> Dict[str, bool]:
    """Check health of all HTTP-exposed services."""
    results: Dict[str, bool] = {}
    for name in ["api", "mission", "agent", "postgres", "redis", "minio", "titiler", "prometheus", "grafana"]:
        results[name] = check_service_health(name)
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────


def main() -> int:
    """CLI entrypoint for P6-01 environment management."""
    if len(sys.argv) < 2:
        print("Usage: python -m infrastructure.docker.implementation <command>")
        print("Commands: up, down, status, health, check")
        return 1

    command = sys.argv[1]

    if command == "up":
        build = "--build" in sys.argv
        print("Starting SatQuery local environment...")
        result = start_environment(build=build)
        print(result.stdout)
        if result.returncode != 0:
            print(f"Error: {result.stderr}", file=sys.stderr)
        return result.returncode

    elif command == "down":
        remove = "--volumes" in sys.argv
        print("Stopping SatQuery local environment...")
        result = stop_environment(remove_volumes=remove)
        print(result.stdout)
        return result.returncode

    elif command == "status":
        statuses = get_service_status()
        for name, state in sorted(statuses.items()):
            icon = "✓" if state == "running" else "✗"
            print(f"  {icon} {name}: {state}")
        return 0

    elif command == "health":
        print("Checking service health...")
        results = check_all_services_healthy()
        all_healthy = all(results.values())
        for name, healthy in sorted(results.items()):
            icon = "✓" if healthy else "✗"
            print(f"  {icon} {name}")
        return 0 if all_healthy else 1

    elif command == "check":
        if not check_docker_available():
            print("Docker is not available or Docker Compose is not installed.")
            return 1
        print("Docker is available.")
        env_file = ensure_env_file()
        print(f"Environment file: {env_file}")
        services = get_compose_services()
        print(f"Defined services ({len(services)}): {', '.join(services)}")
        return 0

    else:
        print(f"Unknown command: {command}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
