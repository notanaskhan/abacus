"""GENERATED from the agent specs and evals/*/suite.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.eval_suites
"""

# fmt: off
EVAL_SUITES: dict[str, tuple[str, int]] = {   'briefing.today': ('briefing.today@v1', 1),
    'decisions.recommender': ('decisions.recommend@v1', 1),
    'evidence.matcher': ('evidence.inbox_match@v3', 1),
    'evidence.screener': ('evidence.screen@v0', 2),
    'evidence.upload_reviewer': ('evidence.upload_review@v3', 3),
    'fieldwork.entry_assessor': ('fieldwork.entry_assess@v2', 2),
    'issues.fix_runner': ('issues.fix_runner.tax@v1', 1),
    'methodology.importer': ('methodology.import_parse@v1', 1),
    'notices.responder': ('notices.analyze@v1', 1),
    'requests.guidance_drafter': ('requests.guidance_draft@v1', 1),
    'runtime.conformance': ('runtime.conformance@v1', 1),
    'tax.account_mapper': ('tax.map_accounts@v1', 1),
    'tax.agreement_reader': ('tax.agreement_reader@v1', 1),
    'tax.assistant': ('tax.assistant@v1', 1),
    'tax.memo_drafter': ('tax.preparer_memo@v1', 1),
    'tax.return_analyst': ('tax.return_analyst.explain@v1', 1),
    'tax.return_drafter': ('tax.return_drafter@v1', 1),
    'workbench.assistant': ('workbench.assistant@v1', 1),
    'workpapers.section_drafter': ('workpapers.section_draft.gap@v1', 1)}
EVAL_SUITE_MODES: dict[str, dict[str, int]] = {   'decisions.recommender': {   'decisions.recommend.convention_706d@v1': 1,
                                 'decisions.recommend.section_754@v1': 1},
    'evidence.matcher': {'evidence.inbox_match@v2': 1},
    'notices.responder': {'notices.extract@v1': 1},
    'workpapers.section_drafter': {   'workpapers.section_draft.ebp_attribute@v1': 1,
                                      'workpapers.section_draft.ebp_form5500@v1': 1,
                                      'workpapers.section_draft.ebp_reconcile@v1': 1,
                                      'workpapers.section_draft.ebp_trust@v1': 1,
                                      'workpapers.section_draft.ic@v1': 1,
                                      'workpapers.section_draft.related_parties@v1': 1,
                                      'workpapers.section_draft.risk@v2': 1,
                                      'workpapers.section_draft.risk_narrative@v1': 1,
                                      'workpapers.section_draft.soc1@v1': 1,
                                      'workpapers.section_draft_ebp_provisions@v1': 1}}
# fmt: on
