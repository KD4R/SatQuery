# Contributing to SatQuery AI

Welcome! This guide explains the branching strategy, commit conventions, and workflow for all team members (P1–P6).

---

## Branch Strategy (GitFlow-lite)

```
main          ← production-ready, tagged releases only
  └── develop ← integration branch; all feature branches target this
        └── feat/P1-01-...  ← individual feature branches
        └── fix/P2-03-...
        └── chore/...
```

**Rules:**
- Never commit directly to `main` or `develop`.
- Always branch from `develop`.
- Open a PR from your feature branch → `develop`.
- `develop` → `main` is done by P1 (Tech Lead) as a release PR.

---

## Branch Naming

| Type | Format | Example |
|------|--------|---------|
| Feature | `feat/<issue-id>-short-desc` | `feat/P1-03-jwt-auth` |
| Bug Fix | `fix/<issue-id>-short-desc` | `fix/P2-07-agent-timeout` |
| Chore | `chore/<desc>` | `chore/update-deps` |
| Docs | `docs/<desc>` | `docs/adr-mission-db` |
| Hotfix | `hotfix/<desc>` | `hotfix/auth-null-ptr` |

---

## Commit Message Convention (Conventional Commits)

```
<type>(<scope>): <short summary>

[optional body]

[optional footer: Closes #issue]
```

**Types:** `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `ci`, `perf`, `style`, `revert`

**Examples:**
```
feat(mission): add POST /api/v1/missions endpoint
fix(auth): handle expired JWT gracefully
test(contracts): add event envelope serialization test
chore(deps): bump fastapi to 0.141
```

---

## Local Setup

```bash
git clone <repo-url>
cd SatQuery-1

# Create virtual environment
python -m venv venv
source venv/bin/activate       # Linux/macOS
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt

# Run all tests
PYTHONPATH=. pytest

# Run only unit tests
PYTHONPATH=. pytest -m unit

# Run linting
flake8 services packages tests
black --check .
```

---

## Ownership Map

| Scope | Owner | Directories |
|-------|-------|-------------|
| Platform / Gateway / Mission | P1 | `services/gateway/`, `services/mission/`, `packages/` |
| Agent Service | P2 | `services/agent/`, `evals/` |
| ML / Inference | P3 | `services/inference/`, `ml/` |
| EO Data / Geo | P4 | `services/eo-data/`, `services/geo/`, `data/` |
| Frontend | P5 | `apps/web/` |
| CI / DevOps | P6 | `infrastructure/` |

Each owner is responsible for writing tests for their own service. Contract tests in `tests/contracts/` are owned by P1.

---

## PR Checklist

Before opening a PR, ensure:
- [ ] Branch name follows convention
- [ ] PR title follows Conventional Commits
- [ ] All tests pass locally
- [ ] No secrets committed
- [ ] Docs/ADRs updated if architecture changed
