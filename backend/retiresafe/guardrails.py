"""Controls that stop name-releasing deletions from bypassing the RetireSafe gate.

The gate only sees deletions that go through the pipeline. These artefacts close the other paths:

1. **AWS Service Control Policy**: denies the API calls that release reclaimable names to every
   principal except the pipeline role(s) that run the gate. Caveats (AWS Organizations
   documentation): SCPs do not apply to the organisation's management account, and a policy may
   hold at most 5,120 characters. The pipeline role itself must only be assumable from CI.
2. **EventBridge rule**: real-time alert on any such call that still happens (for example from
   the management account or during break-glass), so the drift scanner can run within minutes.
3. **Azure management locks** (``CanNotDelete``) on name-bearing resources. Terraform removes
   locks it manages before destroying, so locks guard against portal/CLI deletion while the gate
   covers Terraform.
"""
from __future__ import annotations

import json

# API calls that release a name the pilot rules treat as reclaimable.
RELEASING_ACTIONS = {
    "s3:DeleteBucket": ("aws.s3", "s3.amazonaws.com", "DeleteBucket"),
    "elasticbeanstalk:TerminateEnvironment": ("aws.elasticbeanstalk", "elasticbeanstalk.amazonaws.com",
                                              "TerminateEnvironment"),
    "elasticbeanstalk:DeleteApplication": ("aws.elasticbeanstalk", "elasticbeanstalk.amazonaws.com",
                                           "DeleteApplication"),
    "ec2:ReleaseAddress": ("aws.ec2", "ec2.amazonaws.com", "ReleaseAddress"),
}
SCP_MAX_CHARS = 5120


def aws_scp(pipeline_role_arns: list[str], break_glass_arns: list[str] | None = None) -> dict:
    if not pipeline_role_arns:
        raise ValueError("at least one pipeline role ARN is required")
    allowed = sorted(set(pipeline_role_arns) | set(break_glass_arns or []))
    policy = {
        "Version": "2012-10-17",
        "Statement": [{
            "Sid": "RetireSafeOnlyPipelineReleasesNames",
            "Effect": "Deny",
            "Action": sorted(RELEASING_ACTIONS),
            "Resource": "*",
            "Condition": {"ArnNotLike": {"aws:PrincipalArn": allowed}},
        }],
    }
    size = len(json.dumps(policy, separators=(",", ":")))
    if size > SCP_MAX_CHARS:
        raise ValueError(f"SCP would be {size} characters; AWS limit is {SCP_MAX_CHARS}")
    return policy


def eventbridge_pattern() -> dict:
    sources = sorted({v[0] for v in RELEASING_ACTIONS.values()})
    return {
        "source": sources,
        "detail-type": ["AWS API Call via CloudTrail"],
        "detail": {
            "eventSource": sorted({v[1] for v in RELEASING_ACTIONS.values()}),
            "eventName": sorted({v[2] for v in RELEASING_ACTIONS.values()}),
        },
    }


def eventbridge_terraform(topic_name: str = "retiresafe-releases") -> str:
    pattern = json.dumps(eventbridge_pattern(), indent=2)
    return f'''# Alert on any name-releasing deletion, wherever it came from.
# Requires an organisation or account CloudTrail trail delivering management events.
resource "aws_sns_topic" "retiresafe_releases" {{
  name = "{topic_name}"
}}

resource "aws_cloudwatch_event_rule" "retiresafe_releases" {{
  name          = "retiresafe-name-releasing-deletions"
  description   = "RetireSafe: a call that releases a reclaimable cloud name"
  event_pattern = <<PATTERN
{pattern}
PATTERN
}}

resource "aws_cloudwatch_event_target" "retiresafe_releases" {{
  rule = aws_cloudwatch_event_rule.retiresafe_releases.name
  arn  = aws_sns_topic.retiresafe_releases.arn
}}
'''


def azure_locks_terraform(addresses: list[str]) -> str:
    blocks = []
    for addr in addresses:
        label = addr.replace(".", "_").replace("[", "_").replace("]", "").replace('"', "")
        blocks.append(f'''resource "azurerm_management_lock" "retiresafe_{label}" {{
  name       = "retiresafe-no-delete"
  scope      = {addr}.id
  lock_level = "CanNotDelete"
  notes      = "Name is reclaimable after deletion; retire through the RetireSafe gate"
}}''')
    return "\n\n".join(blocks) + "\n"
