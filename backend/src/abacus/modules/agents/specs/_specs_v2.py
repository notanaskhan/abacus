"""GENERATED from abacus/modules/agents/specs/v2/*.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.agent_specs_v2
"""

# fmt: off
SPECS_V2: dict[str, dict[str, object]] = {   'tax.return_drafter': {   'autonomy': 'propose',
                              'cheaper_tiers': [],
                              'client_data': 'none',
                              'data_classes': ['tri'],
                              'escalation_tier': 'medium',
                              'essential': False,
                              'evaluation_suite': 'evals/tax_return',
                              'id': 'tax.return_drafter',
                              'input_schema': 'ReturnDraftInput',
                              'limits': {   'max_cost_usd': '0.75',
                                            'max_output_tokens': 1200,
                                            'max_seconds': 300,
                                            'max_steps': 30,
                                            'max_tool_calls': 30},
                              'output_schema': 'ReturnDraftJudgment',
                              'plan': 'required_when_writes',
                              'prompt': 'tax.return_drafter@v1',
                              'purpose': "Propose an individual return's initial draft from its "
                                         "documents' boxes, mapped by code, with each worksheet's "
                                         'TSJ and new-this-year notes, for the preparer to '
                                         'approve.',
                              'routes': ['bedrock', 'direct'],
                              'shape': 'workflow',
                              'task_scope': [   'tax_return.read',
                                                'return_worksheet.read',
                                                'proposal.create',
                                                'issue.create',
                                                'checkpoint.propose',
                                                'evidence.read'],
                              'tier': 'medium',
                              'tools': {   'propose': ['tax.propose_field_changes'],
                                           'read': [   'tax.read_return',
                                                       'tax.list_documents',
                                                       'tax.read_worksheet']},
                              'untrusted_inputs': ['document_text'],
                              'version': 1,
                              'work_class': 'background'}}
# fmt: on
