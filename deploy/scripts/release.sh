#!/usr/bin/env bash
# The deploy sequence's steps, shared by deploy-staging.yml, deploy-production.yml and
# rollback.yml (Q-01-T18, Q-01-T34; SPEC-050 AC-26). Sourced, never run on its own:
#   source deploy/scripts/release.sh
# Every function reads its inputs from the environment the workflow sets (ENV_NAME, DIGEST,
# GIT_SHA, ECR_REPOSITORY, ECS_CLUSTER, TASK_SUBNETS, TASK_SECURITY_GROUP, ...). Images are named
# by digest only (`<repository>@sha256:...`), never by tag. Nothing here runs Terraform, and
# nothing here downgrades a database: rollback re-points code and bundle only.
set -euo pipefail

ARTIFACTS="${ARTIFACTS:-abacus-shared-artifacts}"

# A new revision of a task definition family running the release image: every container whose
# image is from our repository is pointed at the digest; sidecars (ADOT) keep theirs.
render_task_definition() {
  local family="$1"
  aws ecs describe-task-definition --task-definition "$family" --query taskDefinition > td.json
  jq --arg repo "$ECR_REPOSITORY" --arg image "$ECR_REPOSITORY@$DIGEST" '
    .containerDefinitions |= map(if (.image | startswith($repo)) then .image = $image else . end)
    | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities,
          .registeredAt, .registeredBy, .deregisteredAt)' td.json > td-new.json
  aws ecs register-task-definition --cli-input-json file://td-new.json \
    --query 'taskDefinition.taskDefinitionArn' --output text
}

# A one-off task (migrate, ops): run it on the release image, wait, and fail on a non-zero exit.
run_task() {
  local family="$1" container="$2"
  shift 2
  local arn overrides task code
  arn=$(render_task_definition "$family")
  if [ "$#" -gt 0 ]; then
    overrides=$(jq -cn --arg c "$container" '{containerOverrides: [{name: $c, command: $ARGS.positional}]}' --args "$@")
  else
    overrides='{}'
  fi
  task=$(aws ecs run-task --cluster "$ECS_CLUSTER" --task-definition "$arn" --launch-type FARGATE \
    --started-by "deploy-${GITHUB_RUN_ID}" \
    --network-configuration "awsvpcConfiguration={subnets=[$TASK_SUBNETS],securityGroups=[$TASK_SECURITY_GROUP],assignPublicIp=DISABLED}" \
    --overrides "$overrides" --query 'tasks[0].taskArn' --output text)
  aws ecs wait tasks-stopped --cluster "$ECS_CLUSTER" --tasks "$task"
  code=$(aws ecs describe-tasks --cluster "$ECS_CLUSTER" --tasks "$task" \
    --query 'tasks[0].containers[?name==`'"$container"'`].exitCode | [0]' --output text)
  if [ "$code" != "0" ]; then
    echo "::error title=$family failed::exit code $code"
    return 1
  fi
}

# Roll one service onto the release image with the ECS circuit breaker and alarm rollback, then
# check the deployment that settled is ours (a rollback by ECS fails the deploy).
roll_service() {
  local service="$1" alarms="${2:-}"
  local family arn config primary
  family=$(aws ecs describe-services --cluster "$ECS_CLUSTER" --services "$service" \
    --query 'services[0].taskDefinition' --output text | sed 's|.*/||; s|:[0-9]*$||')
  arn=$(render_task_definition "$family")
  config="deploymentCircuitBreaker={enable=true,rollback=true}"
  if [ -n "$alarms" ]; then
    config="$config,alarms={alarmNames=[$alarms],enable=true,rollback=true}"
  fi
  aws ecs update-service --cluster "$ECS_CLUSTER" --service "$service" --task-definition "$arn" \
    --deployment-configuration "$config" > /dev/null
  aws ecs wait services-stable --cluster "$ECS_CLUSTER" --services "$service"
  primary=$(aws ecs describe-services --cluster "$ECS_CLUSTER" --services "$service" \
    --query 'services[0].deployments[?status==`PRIMARY`].taskDefinition | [0]' --output text)
  if [ "$primary" != "$arn" ]; then
    echo "::error title=$service rolled back::the circuit breaker or an alarm rolled $service back"
    return 1
  fi
}

# runtime-config.json for this environment and release (platform-ops contract 3.2), from SSM.
render_runtime_config() {
  local release="$1" prefix="/abacus/${ENV_NAME}/runtime-config"
  local authority client portal sentry
  authority=$(aws ssm get-parameter --name "$prefix/oidc_authority" --query Parameter.Value --output text)
  client=$(aws ssm get-parameter --name "$prefix/oidc_client_id" --query Parameter.Value --output text)
  portal=$(aws ssm get-parameter --name "$prefix/portal_base_domain" --query Parameter.Value --output text)
  sentry=$(aws ssm get-parameter --name "$prefix/sentry_dsn" --query Parameter.Value --output text 2>/dev/null || true)
  (cd backend && uv run --locked python -m abacus_tools.release runtime-config \
    --environment "$ENV_NAME" --release "$release" --authority "$authority" --client-id "$client" \
    --portal-base-domain "$portal" ${sentry:+--sentry-dsn "$sentry"}) > runtime-config.json
}

# The SPA of release `$1`: hashed assets first (immutable, never deleted, so the previous bundle
# keeps working and rollback can return to it), then the entry, then runtime-config.json, then an
# invalidation of exactly those three paths. The portal entry is never cached at the edge.
publish_spa() {
  local release="$1" source="s3://$ARTIFACTS/web/$1"
  render_runtime_config "$release"
  aws s3 cp "$source/firm/assets/" "s3://$WEB_BUCKET/assets/" --recursive --only-show-errors \
    --cache-control "public, max-age=31536000, immutable"
  aws s3 cp "$source/firm/index.html" "s3://$WEB_BUCKET/index.html" --cache-control "no-cache"
  aws s3 cp runtime-config.json "s3://$WEB_BUCKET/runtime-config.json" --cache-control "no-cache"
  aws cloudfront create-invalidation --distribution-id "$FIRM_DISTRIBUTION_ID" \
    --paths "/index.html" "/" "/runtime-config.json" > /dev/null
  if [ -n "${PORTAL_BUCKET:-}" ] && aws s3 ls "$source/portal/portal.html" > /dev/null 2>&1; then
    aws s3 cp "$source/portal/assets/" "s3://$PORTAL_BUCKET/assets/" --recursive --only-show-errors \
      --cache-control "public, max-age=31536000, immutable"
    aws s3 cp "$source/portal/portal.html" "s3://$PORTAL_BUCKET/portal.html" --cache-control "no-cache"
    aws s3 cp runtime-config.json "s3://$PORTAL_BUCKET/runtime-config.json" --cache-control "no-cache"
  fi
}

# The release record: the environment's current release moves to `release-previous` (what
# rollback returns to), and this one becomes current, with how it got there.
record_release() {
  local how="$1" previous
  previous=$(aws ssm get-parameter --name "/abacus/${ENV_NAME}/release" --query Parameter.Value \
    --output text 2>/dev/null || true)
  if [ -n "$previous" ]; then
    aws ssm put-parameter --name "/abacus/${ENV_NAME}/release-previous" --type String --overwrite \
      --value "$previous" > /dev/null
  fi
  jq -c --arg how "$how" --arg run "$RUN_REF" --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '. + {deployed_by: $how, run: $run, deployed_at: $at}' release.json > current.json
  aws ssm put-parameter --name "/abacus/${ENV_NAME}/release" --type String --overwrite \
    --value "file://current.json" > /dev/null
}
