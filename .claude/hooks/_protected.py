"""Shared protected-path rules for hooks. Mirrors docs/architecture/protected-paths.md."""
import datetime, fnmatch, glob, os

ROOT = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

# Always protected: any edit or creation requires an approval file.
PROTECTED = [
    "AGENTS.md", "CLAUDE.md", "Makefile",
    ".claude/*", ".claude/**/*",
    ".github/*", ".github/**/*",
    "infra/*", "infra/**/*",
    "work/approvals/*",
    "docs/architecture/permission-matrix.yaml",
    "docs/architecture/protected-paths.md",
    "docs/architecture/dependency-allowlist.yaml",
    "docs/product/glossary.md",
    "backend/pyproject.toml", "backend/uv.lock",
    "apps/web/package.json", "pnpm-lock.yaml", "package.json",
    "backend/quality/*",
    "backend/src/modules/identity/authz/*", "backend/src/modules/identity/authz/**/*",
    "backend/src/platform/db/*", "backend/src/platform/db/**/*",
    "backend/src/platform/uow/*", "backend/src/platform/uow/**/*",
    "backend/src/platform/crypto/*", "backend/src/platform/crypto/**/*",
    "backend/src/modules/audit_trail/*", "backend/src/modules/audit_trail/**/*",
]
# Protected only once they exist: new files allowed, edits to existing files need approval.
PROTECTED_IF_EXISTS = ["docs/adr/ADR-*.md", "backend/migrations/versions/*"]

def rel(path: str) -> str:
    p = os.path.abspath(path if os.path.isabs(path) else os.path.join(ROOT, path))
    return os.path.relpath(p, ROOT).replace(os.sep, "/")

def _match(r: str, patterns) -> bool:
    """Glob match where '**/' may match zero or more directories."""
    for pat in patterns:
        variants = {pat, pat.replace("/**/", "/"), pat.replace("**/", "")}
        if any(fnmatch.fnmatch(r, v) for v in variants):
            return True
    return False

def approved(r: str) -> bool:
    """An approval file in work/approvals/*.yaml written by the founder:
       task: TASK-012
       approved_by: founder
       expires: 2026-12-31
       paths:
         - backend/src/platform/uow/**/*
    """
    today = datetime.date.today().isoformat()
    for f in glob.glob(os.path.join(ROOT, "work/approvals/*.yaml")):
        try:
            text = open(f).read()
        except OSError:
            continue
        lines = [l.rstrip() for l in text.splitlines()]
        expires = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("expires:")), "")
        by = next((l.split(":", 1)[1].strip() for l in lines if l.startswith("approved_by:")), "")
        if not by or not expires or expires < today:
            continue
        paths = [l.strip()[2:].strip() for l in lines if l.strip().startswith("- ")]
        if _match(r, paths):
            return True
    return False

def violation(path: str) -> str | None:
    r = rel(path)
    if r.startswith(".."):
        return f"{path} is outside the project."
    if r.startswith("work/approvals/"):
        return "Approval files can only be created by the founder, by hand."
    if _match(r, PROTECTED) and not approved(r):
        return f"{r} is a protected path. Ask the founder for an approval file in work/approvals/."
    if _match(r, PROTECTED_IF_EXISTS) and os.path.exists(os.path.join(ROOT, r)) and not approved(r):
        return f"{r} already exists and is immutable (accepted ADR or applied migration). Create a new file instead, or ask for approval."
    return None
