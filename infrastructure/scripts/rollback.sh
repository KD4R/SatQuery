#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# infrastructure/scripts/rollback.sh — P6-15 deterministic rollback
#
# Rolls the compose stack back to an exact previous release by pinning every
# service image to the sha-<sha> tag built and pushed by cd.yml.
#
# Usage:
#   ./rollback.sh <sha>              # roll back to the release built at <sha>
#   ./rollback.sh <sha> --dry-run    # show what would be pinned, change nothing
#   ./rollback.sh --print-env-example
#
# How it works:
#   1. Resolves every sha-tagged image to its immutable registry digest.
#   2. Writes a docker-compose override file pinning image: to those digests
#      (digest-pinned references cannot be mutated by a later push of the tag).
#   3. `compose up -d` recreates only services whose image actually changed.
#   4. Polls each service's /api/v1/health before declaring success; on
#      failure the previous image refs are printed so recovery is one paste.
#
# Optional: SATQUERY_MANIFEST=<path to release-manifest.json> ./rollback.sh <sha> --verify
#   cross-checks that the registry digests match the digests recorded in the
#   release manifest attached to the GitHub Release.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/infrastructure/docker/docker-compose.yml"

REGISTRY="${SATQUERY_REGISTRY:-ghcr.io}"
REPO="${SATQUERY_REPO:-kd4r/satquery}"          # lowercase org/name
SHA_TAG_PREFIX="sha-"
MANIFEST="${SATQUERY_MANIFEST:-}"

SERVICES=(api mission agent)
HEALTH_PATH="/api/v1/health"
HEALTH_TIMEOUT_S=60
OVERRIDE_FILE="$(mktemp -t satquery-rollback-override-XXXXXX.yaml)"
trap 'rm -f "$OVERRIDE_FILE"' EXIT

log() { printf '[rollback] %s\n' "$*"; }
die() { printf '[rollback] ERROR: %s\n' "$*" >&2; exit 1; }

usage() {
  sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
  exit 1
}

# ── Parse args ───────────────────────────────────────────────────────────────
TARGET_SHA=""
DRY_RUN=false
VERIFY=false

case "${1:-}" in
  --print-env-example)
    cat <<EOF
# Source before running if your release lives in another org/repo:
# export SATQUERY_REGISTRY=ghcr.io
# export SATQUERY_REPO=<org>/<repo>          # lowercase
# export SATQUERY_MANIFEST=/path/to/release-manifest.json  # enables --verify
EOF
    exit 0
    ;;
  "") usage ;;
  *) TARGET_SHA="$1" ;;
esac
shift || true
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --verify) VERIFY=true ;;
    *) usage ;;
  esac
  shift
done

[[ "$TARGET_SHA" =~ ^[0-9a-fA-F]{7,40}$ ]] || die "First argument must be a git SHA (7-40 hex chars), got: '$TARGET_SHA'"
TARGET_SHA="$(echo "$TARGET_SHA" | tr '[:upper:]' '[:lower:]')"
command -v docker >/dev/null || die "docker CLI not found"
docker compose version >/dev/null 2>&1 || die "docker compose plugin not available"

# ── Resolve immutable digests ────────────────────────────────────────────────
log "Target release: sha-${TARGET_SHA}"
log "Registry: ${REGISTRY}/${REPO}"

# bash-3.2-safe per-service digest vars (no associative arrays).
DIGEST_API=""
DIGEST_MISSION=""
DIGEST_AGENT=""
for svc in "${SERVICES[@]}"; do
  ref="${REGISTRY}/${REPO}/satquery-${svc}:${SHA_TAG_PREFIX}${TARGET_SHA}"
  log "Inspecting ${ref}"
  digest="$(docker buildx imagetools inspect "$ref" --format '{{json .Manifest.Digest}}' 2>/dev/null \
    | tr -d '"' )" || true
  if [ -z "$digest" ]; then
    die "Could not resolve digest for ${ref}. Was this release built and pushed by cd.yml?"
  fi
  case "$svc" in
    api) DIGEST_API="$digest" ;;
    mission) DIGEST_MISSION="$digest" ;;
    agent) DIGEST_AGENT="$digest" ;;
  esac
  log "  digest: ${digest}"
done

digest_for() {
  case "$1" in
    api) printf '%s' "$DIGEST_API" ;;
    mission) printf '%s' "$DIGEST_MISSION" ;;
    agent) printf '%s' "$DIGEST_AGENT" ;;
  esac
}

# ── Optional manifest cross-check ────────────────────────────────────────────
if $VERIFY; then
  [ -n "$MANIFEST" ] && [ -f "$MANIFEST" ] || die "--verify requires SATQUERY_MANIFEST to point at a release-manifest.json"
  for svc in "${SERVICES[@]}"; do
    manifest_digest="$(python3 -c "
import json,sys
m=json.load(open('$MANIFEST'))
img=m['images'].get('$svc') or {}
d=img.get('digest','')
print(d.split('@',1)[1] if '@' in d else '')
")"
    [ -n "$manifest_digest" ] || die "manifest has no digest for ${svc}"
    [ "$manifest_digest" = "$(digest_for "$svc")" ] || die "digest mismatch for ${svc}: registry=$(digest_for "$svc") manifest=${manifest_digest}"
    log "verified ${svc} digest matches manifest"
  done
fi

# ── Build the override file ──────────────────────────────────────────────────
if $DRY_RUN; then
  log "dry-run: would pin the following images (no changes made):"
  for svc in "${SERVICES[@]}"; do
    log "  ${svc} -> ${REGISTRY}/${REPO}/satquery-${svc}@$(digest_for "$svc")"
  done
  exit 0
fi

{
  echo "services:"
  for svc in "${SERVICES[@]}"; do
    echo "  ${svc}:"
    echo "    image: ${REGISTRY}/${REPO}/satquery-${svc}@$(digest_for "$svc")"
  done
} > "$OVERRIDE_FILE"

log "Override file:"
cat "$OVERRIDE_FILE"

# ── Snapshot current image refs for emergency recovery ───────────────────────
PREVIOUS_REFS="$PROJECT_ROOT/.rollback-previous.env"
: > "$PREVIOUS_REFS"
for svc in "${SERVICES[@]}"; do
  cur="$(docker compose -f "$COMPOSE_FILE" ps --format json "$svc" 2>/dev/null \
    | python3 -c "import json,sys; lines=[l for l in sys.stdin if l.strip()]; print(json.loads(lines[0]).get('Image','') if lines else '')" 2>/dev/null || true)"
  echo "${svc}=${cur}" >> "$PREVIOUS_REFS"
done
log "Previous image refs saved to ${PREVIOUS_REFS}"

# ── Redeploy ─────────────────────────────────────────────────────────────────
log "Recreating services with pinned images..."
docker compose -f "$COMPOSE_FILE" -f "$OVERRIDE_FILE" up -d --no-deps --remove-orphans "${SERVICES[@]}"

# ── Health gate ──────────────────────────────────────────────────────────────
log "Waiting up to ${HEALTH_TIMEOUT_S}s for health endpoints..."
FAILED=()
for svc in "${SERVICES[@]}"; do
  case "$svc" in
    api) port="${API_PORT:-8000}" ;;
    mission) port="${MISSION_PORT:-8001}" ;;
    agent) port="${AGENT_PORT:-8002}" ;;
  esac
  deadline=$((SECONDS + HEALTH_TIMEOUT_S))
  healthy=false
  while [ $SECONDS -lt $deadline ]; do
    if curl -fsS "http://localhost:${port}${HEALTH_PATH}" >/dev/null 2>&1; then
      healthy=true
      break
    fi
    sleep 2
  done
  if $healthy; then
    log "  ${svc}: healthy on :${port}"
  else
    FAILED+=("$svc")
    log "  ${svc}: FAILED health check on :${port}"
  fi
done

if [ ${#FAILED[@]} -gt 0 ]; then
  log "ROLLBACK FAILED health gate for: ${FAILED[*]}"
  log "Recover by re-pinning the previous images:"
  cat "$PREVIOUS_REFS"
  exit 1
fi

log "Rollback to sha-${TARGET_SHA} complete. All services healthy."
