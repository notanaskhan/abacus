"""Load TAX-11's form faces through P-11's import endpoint (T-06-T43; DEC-5914).

    python -m abacus_tools.form_faces --dir <drafts dir> --base-url https://<host> [--apply]

Form faces are content: each is a `tax_form_face` template import body (`TemplateImportIn` with
its `field_manifest`) kept outside the repository (the drafts) and loaded into a firm through
`POST /v1/report-templates/import`, never committed as seed (AGENTS.md rule 16). The tool validates
every file locally first (the same `validate` the endpoint runs), then asks the endpoint for a dry
run and prints its `changes`; with `--apply` it imports the files whose dry run reports a change.
A second run reports no change for any file (the content hash is unchanged). The bearer token is
read from `ABACUS_API_TOKEN` and never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from abacus.modules.reporting.contract import TemplateImportIn
from abacus.modules.reporting.templates import FORM_FACE, validate

TOKEN_ENV = "ABACUS_API_TOKEN"  # noqa: S105 -- the variable name, not a secret


def local_problems(path: Path) -> list[str]:
    """A file's problems before anything is sent: schema, family, and C11's import rules."""
    try:
        body = TemplateImportIn.model_validate(json.loads(path.read_text(encoding="utf-8")))
    except ValueError as exc:
        return [f"schema: {str(exc).splitlines()[0]}"]
    if body.family != FORM_FACE:
        return ["family: not tax_form_face"]
    errors, _ = validate(body)
    return [f"{e.path}: {e.code}" for e in errors]


def _post(base_url: str, body: bytes, *, dry_run: bool) -> dict[str, object]:
    token = os.environ.get(TOKEN_ENV, "")
    request = urllib.request.Request(  # noqa: S310 -- an operator-named https base URL
        f"{base_url.rstrip('/')}/v1/report-templates/import?dry_run={str(dry_run).lower()}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
        return json.loads(response.read())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.form_faces")
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    files = sorted(Path(args.dir).glob("tax_form_face-*.json"))
    failed = False
    for path in files:
        problems = local_problems(path)
        print(f"{path.name}: {'ok' if not problems else '; '.join(problems)}")
        failed = failed or bool(problems)
    if failed or args.base_url is None:
        return 1 if failed else 0
    if not args.base_url.startswith("https://") and "localhost" not in args.base_url:
        print("base URL must be https (or localhost)")
        return 1
    for path in files:
        body = path.read_bytes()
        report = _post(args.base_url, body, dry_run=True)
        changes = cast("list[str]", report.get("changes") or [])
        print(f"{path.name}: dry run {changes or 'no change'}")
        if args.apply and changes:
            stored = _post(args.base_url, body, dry_run=False)
            print(f"{path.name}: imported draft {stored.get('draft_version_id')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
