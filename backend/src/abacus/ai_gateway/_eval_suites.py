"""GENERATED from the agent specs and evals/*/suite.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.eval_suites
"""

# fmt: off
EVAL_SUITES: dict[str, tuple[str, int]] = {   'decisions.recommender': ('decisions.recommend@v1', 1),
    'evidence.matcher': ('evidence.inbox_match@v3', 1),
    'evidence.screener': ('evidence.screen@v0', 2),
    'evidence.upload_reviewer': ('evidence.upload_review@v3', 3),
    'fieldwork.entry_assessor': ('fieldwork.entry_assess@v2', 2),
    'requests.guidance_drafter': ('requests.guidance_draft@v1', 1)}
EVAL_SUITE_MODES: dict[str, dict[str, int]] = {'evidence.matcher': {'evidence.inbox_match@v2': 1}}
# fmt: on
