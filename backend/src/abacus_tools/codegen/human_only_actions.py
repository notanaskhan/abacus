"""Generate `abacus.kernel._human_only_actions` from the human-only register (Q-02-T17).

Run: python -m abacus_tools.codegen.human_only_actions [--check]

`docs/architecture/human-only-actions.yaml` lists the audit actions an agent or a policy may never
write (I-AGENT-NEVER at the data layer). Each entry names its I-AGENT-NEVER verb; an action must
look like an audit action and appear once. `--check` reports a stale module without writing.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import cast

import yaml

BACKEND = Path(__file__).resolve().parents[3]
SOURCE = BACKEND.parent / "docs" / "architecture" / "human-only-actions.yaml"
TARGET = BACKEND / "src" / "abacus" / "kernel" / "_human_only_actions.py"
VERBS = frozenset(
    {"approve", "sign off", "release", "send", "post", "decide", "accept", "reject", "waive"}
    | {"confirm"}
)
_ACTION = re.compile(r"[a-z][a-z_]*\.[a-z][a-z_]*")
_HEADER = '''"""GENERATED from docs/architecture/human-only-actions.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.human_only_actions
"""

'''


class RegisterInvalid(ValueError):
    pass


def load(path: Path = SOURCE) -> tuple[str, ...]:
    data = cast(dict[str, object], yaml.safe_load(path.read_text()))
    entries = cast(list[dict[str, object]], data.get("actions") or [])
    actions: list[str] = []
    for entry in entries:
        action, verb = entry.get("action"), entry.get("verb")
        if not isinstance(action, str) or not _ACTION.fullmatch(action):
            raise RegisterInvalid(f"{action!r} is not an audit action")
        if verb not in VERBS:
            raise RegisterInvalid(f"{action}: {verb!r} is not an I-AGENT-NEVER verb")
        if action in actions:
            raise RegisterInvalid(f"{action} is listed twice")
        actions.append(action)
    return tuple(sorted(actions))


def render(actions: tuple[str, ...]) -> str:
    rows = "".join(f'        "{a}",\n' for a in actions)
    return (
        _HEADER
        + "from typing import Final\n\n"
        + "# Audit actions an agent or a policy may never write (I-AGENT-NEVER).\n"
        + "HUMAN_ONLY_ACTIONS: Final[frozenset[str]] = frozenset(\n"
        + f"    {{\n{rows}    }}\n)\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the module is out of date")
    args = parser.parse_args(argv)
    body = render(load())
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != body:
            print(f"{TARGET.name} is out of date: run python -m {__spec__.name}")
            return 1
        return 0
    TARGET.write_text(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
