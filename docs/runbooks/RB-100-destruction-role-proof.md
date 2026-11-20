---
id: RB-100
title: "Destruction role: staging proof (Q-05-T14)"
owner: builder
owning_epic: Q-05
alarms: []
last_rehearsed: never
rehearse_by: 2028-10-27
---
# RB-100 · Destruction role: staging proof (Q-05-T14; ADR-179 / OQ-1; DEC-5823)

**Who:** a security admin with staging AWS access (two people for the apply: one plans, the other
approves the plan). **When:** before Q-05-T15's DestructionExecuteWorkflow runs on staging.

1. `terraform -chdir=infra/envs/staging plan -var destruction_role_enabled=true
   -var oncall_topic_arn=<the on-call SNS topic>`; check the plan creates only the role, its
   inline policy and the EventBridge rule and target. Apply.
2. Attach `infra/landing-zone/scp-evidence-destruction.json` to the staging OU (landing zone).
3. Seed three synthetic objects in the staging evidence bucket: A with retain-until in the future,
   B with a legal hold on, C expired and unheld.
4. From a worker-batch task, assume `abacus-staging-destruction` with session tag
   `destruction_batch=RB100-proof`. Delete the versions of A, B and C:
   - A answers AccessDenied (retention), B AccessDenied (legal hold), C deletes.
5. Assume the role **without** the tag: the assumption is refused by the trust policy; a manual
   attempt by an admin with the tag but outside a batch run is still recorded, and the
   EventBridge rule pages on-call within five minutes for an untagged assumption.
6. From any other principal (the ops role), DeleteObjectVersion on any evidence object answers
   AccessDenied (the SCP).
7. Record the outcome (date, operator, three results, the page) in
   `docs/plan/status/S52-quality-lanes.md` under Q-05-T14. Roll back: `destruction_role_enabled=false`.
