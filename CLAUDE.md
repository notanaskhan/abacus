# CLAUDE.md

This project's instructions live in AGENTS.md so that Claude Code and Codex share one source of truth. The plan of record is `docs/plan/`.

@AGENTS.md

## Working agreements

1. **Batch merges; do not deploy per fix.** Merge finished work in one sitting and deploy staging once at sprint close. Every deploy costs build time and a cold cache. Say "holding this until the batch" when you defer. Exceptions ship now: production broken, a security fix, or when asked.
2. **Content belongs in the database, not in a commit.** Firm content goes in through an admin screen or import endpoint, not a seed file or constant. Code is for templates, routes and components.
3. **No local production build while a hosted build is running.** Both hit the same database and exhaust its connections; the failure looks like a code bug and is not. Check for a deploy in flight first.
