"""Elastic IP / instance public IP (real Terraform+moto plans) and Azure name rules."""
from conftest import GEN
from retiresafe.analysis.traffic import Policy
from retiresafe.engine.assess import AssessmentInput, run
from retiresafe.knowledge import providers
from retiresafe.models import Tri, Verdict


def _v(plan, dns=True):
    res = run(AssessmentInput(str(GEN / plan), [(str(GEN / "ip_route53.json"), None)] if dns else [], {}, [],
                              Policy()))
    return {a.resource.address: a.verdict for a in res.resources}


def test_instance_ip_blocks_while_dns_points_at_it():
    v = _v("ip_plan_before.json")
    assert v["aws_instance.web"] == Verdict.BLOCK          # cannot be held: references must go first
    assert v["aws_eip.api"] == Verdict.TOMBSTONE            # can be held: keep the allocation


def test_instance_ip_released_once_records_go_with_it():
    assert _v("ip_plan_after.json")["aws_instance.web"] == Verdict.RELEASE
    assert _v("ip_plan_after.json", dns=False)["aws_instance.web"] == Verdict.REVIEW


def test_azure_rules():
    sa = providers.view("azurerm_storage_account", {"name": "contosoprod", "primary_blob_host":
                                                    "contosoprod.blob.core.windows.net"}, None)
    assert sa.reclaimable.value == Tri.TRUE and sa.endpoints[0].name == "contosoprod.blob.core.windows.net"
    apim = providers.view("azurerm_api_management", {"name": "contoso", "gateway_url": "https://contoso.azure-api.net"}, None)
    assert apim.endpoints[0].name == "contoso.azure-api.net"
    aci = providers.view("azurerm_container_group", {"dns_name_label": "contoso-jobs",
                                                     "fqdn": "contoso-jobs.westeurope.azurecontainer.io"}, None)
    assert aci.reclaimable.value == Tri.TRUE                # Unsecure is the documented default
    aci2 = providers.view("azurerm_container_group", {"dns_name_label": "x", "dns_name_label_reuse_policy": "NoReuse",
                                                      "fqdn": "x-h4sh.westeurope.azurecontainer.io"}, None)
    assert aci2.reclaimable.value == Tri.FALSE
    pip = providers.view("azurerm_public_ip", {"ip_address": "20.1.2.3"}, None)
    assert pip.reclaimable.value == Tri.UNKNOWN             # no primary source for Azure IP reuse
    pip2 = providers.view("azurerm_public_ip", {"domain_name_label": "contoso", "ip_address": "20.1.2.3",
                                                "fqdn": "contoso.westeurope.cloudapp.azure.com"}, None)
    assert pip2.reclaimable.value == Tri.TRUE
