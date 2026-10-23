"""Q-01-T49 (D-OPS-13): opt-in PR previews, checked offline.

"A push without the label builds nothing": the job conditions of `.github/workflows/preview.yml`
are evaluated here against the pull_request events GitHub sends, with the expression operators the
workflow uses (`&&`, `||`, `!=`, `==`, `contains`). The 403-without-cookie and delete-on-close halves
are held statically: the gate function and the delete job; the live check is the builder's, after
the shared apply (infra/README.md).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "preview.yml"
MODULE = REPO / "infra" / "modules" / "previews"
THIS_REPO = "notanaskhan/abacus"


def workflow() -> dict[Any, Any]:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def evaluate(condition: str, event: dict[str, Any]) -> bool:
    """Evaluate a job `if` over a pull_request event; only the forms preview.yml uses."""
    values = {
        "github.event.action": event["action"],
        "github.event.label.name": event.get("label"),
        "github.event.pull_request.head.repo.full_name": event.get("head_repo", THIS_REPO),
        "github.repository": THIS_REPO,
    }
    labels = event.get("labels", [])
    text = " ".join(condition.split())
    text = text.replace(
        "contains(github.event.pull_request.labels.*.name, 'preview')", repr("preview" in labels)
    )
    for name in sorted(values, key=len, reverse=True):
        text = text.replace(name, repr(values[name]))
    text = text.replace("&&", " and ").replace("||", " or ")
    assert re.fullmatch(r"[\s()'\w/.=!-]*", text), f"unexpected expression form: {text}"
    return bool(eval(text, {"__builtins__": {}}, {}))  # noqa: S307 - our own workflow text, reduced to literals


def jobs_that_run(event: dict[str, Any]) -> set[str]:
    return {name for name, job in workflow()["jobs"].items() if evaluate(job["if"], event)}


def test_the_only_trigger_is_a_pull_request_event() -> None:
    triggers = workflow()[True]  # YAML 1.1 reads the `on:` key as true
    assert set(triggers) == {"pull_request"}


@pytest.mark.parametrize("action", ["opened", "synchronize", "reopened", "edited"])
def test_a_push_without_the_label_builds_nothing(action: str) -> None:
    assert jobs_that_run({"action": action, "labels": ["bug"]}) == set()


def test_closing_or_relabelling_an_unlabelled_pr_runs_nothing() -> None:
    assert jobs_that_run({"action": "closed", "labels": []}) == set()
    assert jobs_that_run({"action": "labeled", "label": "bug", "labels": ["bug"]}) == set()
    assert jobs_that_run({"action": "unlabeled", "label": "bug", "labels": []}) == set()


def test_adding_the_label_or_pushing_to_a_labelled_pr_builds() -> None:
    assert jobs_that_run({"action": "labeled", "label": "preview", "labels": ["preview"]}) == {
        "build"
    }
    assert jobs_that_run({"action": "synchronize", "labels": ["preview", "bug"]}) == {"build"}
    assert jobs_that_run({"action": "reopened", "labels": ["preview"]}) == {"build"}


def test_another_label_on_a_labelled_pr_does_not_rebuild() -> None:
    assert (
        jobs_that_run({"action": "labeled", "label": "bug", "labels": ["preview", "bug"]}) == set()
    )


def test_closing_or_removing_the_label_deletes_and_never_builds() -> None:
    assert jobs_that_run({"action": "closed", "labels": ["preview"]}) == {"delete"}
    assert jobs_that_run({"action": "unlabeled", "label": "preview", "labels": []}) == {"delete"}


def test_a_fork_pr_never_runs() -> None:
    fork = "someone/abacus"
    assert (
        jobs_that_run(
            {"action": "labeled", "label": "preview", "labels": ["preview"], "head_repo": fork}
        )
        == set()
    )
    assert jobs_that_run({"action": "closed", "labels": ["preview"], "head_repo": fork}) == set()


def test_the_build_is_the_fixture_build_into_the_pr_prefix() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "vite build --mode fixtures" in text
    assert "PREFIX: pr-${{ github.event.pull_request.number }}" in text
    assert "BUCKET: abacus-shared-previews" in text
    assert 'aws s3 rm "s3://$BUCKET/$PREFIX/" --recursive' in text


def test_no_long_lived_credentials_and_every_action_pinned() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text
    assert "role-to-assume: ${{ env.PREVIEW_ROLE }}" in text
    for ref in re.findall(r"uses:\s*(\S+)", text):
        assert re.search(r"@[0-9a-f]{40}$", ref), f"{ref} is not pinned to a commit SHA"


def test_the_host_refuses_every_request_without_the_gate_cookie() -> None:
    gate = (MODULE / "gate.js").read_text(encoding="utf-8")
    main = (MODULE / "main.tf").read_text(encoding="utf-8")
    assert 'event_type   = "viewer-request"' in main
    assert re.search(r'code\s*=\s*file\("\$\{path\.module\}/gate\.js"\)', main)
    assert 'kvs.get("gate-key")' in gate
    assert "statusCode: 403" in gate
    # The key lives only in the store: Terraform never writes a key value into it.
    assert "aws_cloudfront_key_value_store_key" not in main


def test_previews_expire_after_14_days() -> None:
    variables = (MODULE / "variables.tf").read_text(encoding="utf-8")
    main = (MODULE / "main.tf").read_text(encoding="utf-8")
    assert re.search(r'variable "expiry_days" \{[^}]*default\s*=\s*14\b', variables)
    assert re.search(r"expiration \{\s*days\s*=\s*var\.expiry_days", main)
