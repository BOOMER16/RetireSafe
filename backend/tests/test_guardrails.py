"""Out-of-gate deletion controls: SCP, EventBridge rule, Azure locks."""
import json

import pytest

from conftest import FIX
from retiresafe import guardrails

EVENT = json.loads((FIX / "cloudtrail_deletebucket_event.json").read_text(encoding="utf-8"))


def test_scp_shape_and_limits():
    scp = guardrails.aws_scp(["arn:aws:iam::123456789012:role/ci-*"])
    st = scp["Statement"][0]
    assert st["Effect"] == "Deny" and "s3:DeleteBucket" in st["Action"]
    assert list(st["Condition"]) == ["ArnNotLike"] and list(st["Condition"]["ArnNotLike"]) == ["aws:PrincipalArn"]
    assert len(json.dumps(scp, separators=(",", ":"))) <= guardrails.SCP_MAX_CHARS
    with pytest.raises(ValueError):
        guardrails.aws_scp([])


def test_scp_passes_parliament_lint():
    parliament = pytest.importorskip("parliament")
    pol = parliament.analyze_policy_string(json.dumps(guardrails.aws_scp(["arn:aws:iam::1:role/ci"])),
                                           ignore_private_auditors=True)
    assert not pol.findings


def test_eventbridge_pattern_matches_deletebucket_only():
    # moto's TestEventPattern API handler is a stub (returns nothing), so use the matcher moto uses
    # to route events to rules.
    from moto.events.models import EventPattern
    p = EventPattern.load(json.dumps(guardrails.eventbridge_pattern()))
    assert p.matches_event(EVENT)
    other = json.loads(json.dumps(EVENT))
    other["detail"]["eventName"] = "PutBucketAcl"
    assert not p.matches_event(other)


def test_azure_lock_hcl():
    hcl = guardrails.azure_locks_terraform(["azurerm_linux_web_app.portal"])
    assert 'scope      = azurerm_linux_web_app.portal.id' in hcl and '"CanNotDelete"' in hcl
