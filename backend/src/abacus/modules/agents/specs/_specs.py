"""GENERATED from abacus/modules/agents/specs/*.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.agent_specs
"""

# fmt: off
SPECS: dict[str, dict[str, object]] = {   'evidence.screener': {   'autonomy': 'propose',
                             'cheaper_tiers': [],
                             'confidence_routing': {'below': '0.5', 'route': 'needs_revision'},
                             'escalation_tier': 'medium',
                             'essential': True,
                             'evaluation_suite': 'evals/screening',
                             'id': 'evidence.screener',
                             'input_schema': 'ScreeningInput',
                             'limits': {   'max_cost_usd': '0.03',
                                           'max_output_tokens': 800,
                                           'max_seconds': 60,
                                           'max_steps': 1},
                             'output_schema': 'ScreeningOutput',
                             'prompt': 'evidence.screen@v0',
                             'purpose': 'Screen a retrieved trial balance and propose whether it '
                                        'is ready for review.',
                             'routes': ['bedrock', 'direct'],
                             'shape': 'single_call',
                             'task_scope': ['evidence.read', 'screening.run'],
                             'tier': 'small',
                             'tools': [],
                             'untrusted_inputs': ['account_names'],
                             'version': 1,
                             'work_class': 'time_sensitive'}}
# fmt: on
