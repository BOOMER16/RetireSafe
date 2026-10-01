"""Provider rules: which retiring resources carry a reclaimable public name.

Pilot coverage (each rule cites ids from ``sources.SOURCES``):

* aws_s3_bucket                       global namespace -> reclaimable; account-regional -> not
* aws_elastic_beanstalk_environment   CNAME prefix pool -> reclaimable
* azurerm_*web_app / app_service / *function_app
                                      classic <name>.azurewebsites.net -> reclaimable;
                                      scoped default hostnames -> not reclaimable by outsiders
Any other resource type is reported as NOT_NAME_BEARING (outside pilot scope) and
listed in the evidence record so the scope limit is visible.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import ConditionResult, Endpoint, Tri

RULES_VERSION = "2026-10-01.2"

ACCOUNT_REGIONAL_NAME = re.compile(r"^(?P<prefix>.+)-(?P<account>\d{12})-(?P<region>[a-z]{2}(?:-[a-z]+)+-\d)-an$")
AZURE_WEBAPP_TYPES = {
    "azurerm_linux_web_app", "azurerm_windows_web_app", "azurerm_app_service",
    "azurerm_function_app", "azurerm_linux_function_app", "azurerm_windows_function_app",
}
S3_TYPES = {"aws_s3_bucket"}
EB_TYPES = {"aws_elastic_beanstalk_environment"}
IP_TYPES = {"aws_eip", "aws_instance"}
# Azure resources whose public hostname embeds a globally unique, reusable name.
# (type, hostname attribute in azurerm 5.7.0, fallback suffix) - Microsoft's dangling-DNS article table
# (MicrosoftDocs/azure-docs subdomain-takeover.md) unless marked; container registry from can-i-take-over-xyz.
AZURE_NAMED = {
    "azurerm_storage_account": ("primary_blob_host", "blob.core.windows.net", ["src:ms-learn-dangling-dns"]),
    "azurerm_cdn_endpoint": ("fqdn", "azureedge.net", ["src:ms-learn-dangling-dns"]),
    "azurerm_api_management": ("gateway_url", "azure-api.net", ["src:ms-learn-dangling-dns"]),
    "azurerm_traffic_manager_profile": ("fqdn", "trafficmanager.net", ["src:ms-learn-dangling-dns"]),
    "azurerm_container_registry": ("login_server", "azurecr.io", ["src:cito-fingerprints"]),
}
AZURE_LABELLED = {"azurerm_container_group", "azurerm_public_ip"}
NAME_BEARING = S3_TYPES | EB_TYPES | AZURE_WEBAPP_TYPES | IP_TYPES | set(AZURE_NAMED) | AZURE_LABELLED


@dataclass
class ProviderView:
    name: str | None
    region: str | None
    endpoints: list[Endpoint]
    reclaimable: ConditionResult
    holdable: bool = True       # can the organisation keep the name/address instead of releasing it?


def s3_endpoints(bucket: str, region: str | None) -> list[Endpoint]:
    eps = [Endpoint(bucket, "s3_bucket"), Endpoint(f"{bucket}.s3.amazonaws.com", "s3_rest")]
    if region:
        eps += [Endpoint(f"{bucket}.s3.{region}.amazonaws.com", "s3_rest"),
                Endpoint(f"{bucket}.s3-website-{region}.amazonaws.com", "s3_website"),
                Endpoint(f"{bucket}.s3-website.{region}.amazonaws.com", "s3_website")]
    return eps


def _s3(attrs: dict, provider_region: str | None) -> ProviderView:
    bucket = attrs.get("bucket")
    region = attrs.get("region") or provider_region
    ns = attrs.get("bucket_namespace")
    if ns == "account-regional":
        rec = ConditionResult(Tri.FALSE, "bucket is in the account regional namespace; only the owning account "
                              "can create buckets there", ["src:aws-sdk-s3-account-regional"])
    elif ns == "global":
        rec = ConditionResult(Tri.TRUE, "bucket is in the shared global namespace; after deletion the name can be "
                              "created by any AWS account in the partition",
                              ["src:aws-sdk-s3-createbucket", "src:watchtowr-s3-2025", "src:infoblox-hazyhawk-2025"])
    elif bucket and ACCOUNT_REGIONAL_NAME.match(bucket):
        rec = ConditionResult(Tri.UNKNOWN, "name follows the account-regional format but the plan does not record "
                              "bucket_namespace; confirm the namespace", ["src:aws-sdk-s3-account-regional"])
    elif bucket:
        rec = ConditionResult(Tri.TRUE, "no account-regional namespace recorded, so the bucket is a global-namespace "
                              "bucket (the default); its name is reclaimable after deletion",
                              ["src:aws-sdk-s3-createbucket", "src:watchtowr-s3-2025", "src:infoblox-hazyhawk-2025"])
    else:
        rec = ConditionResult(Tri.UNKNOWN, "bucket name not present in the plan", [])
    eps = s3_endpoints(bucket, region) if bucket else []
    if attrs.get("website_endpoint"):
        eps.append(Endpoint(attrs["website_endpoint"], "s3_website"))
    return ProviderView(bucket, region, _dedupe(eps), rec)


def _eb(attrs: dict, provider_region: str | None) -> ProviderView:
    prefix = attrs.get("cname_prefix")
    region = attrs.get("region") or provider_region
    eps = []
    if attrs.get("cname"):
        eps.append(Endpoint(attrs["cname"].rstrip("."), "eb_cname"))
    if prefix and region:
        eps.append(Endpoint(f"{prefix}.{region}.elasticbeanstalk.com", "eb_cname"))
    if prefix:
        rec = ConditionResult(Tri.TRUE, "Elastic Beanstalk CNAME prefixes come from a shared pool checked for "
                              "availability; a released prefix can be reserved by another account",
                              ["src:aws-sdk-eb-checkdns", "src:cito-fingerprints"])
    else:
        rec = ConditionResult(Tri.UNKNOWN, "no cname_prefix in the plan; cannot tell which name is released", [])
    return ProviderView(prefix or attrs.get("cname"), region, _dedupe(eps), rec)


def _azure(attrs: dict, provider_region: str | None) -> ProviderView:
    name = attrs.get("name")
    host = (attrs.get("default_hostname") or (f"{name}.azurewebsites.net" if name else "")).lower().rstrip(".")
    scope = attrs.get("auto_generated_domain_name_label_scope")
    eps = [Endpoint(host, "azure_app")] if host else []
    if scope:
        rec = ConditionResult(Tri.FALSE, f"default hostname uses autoGeneratedDomainNameLabelScope={scope}; the "
                              "endpoint name is not reusable outside that scope", ["src:azure-sdk-web-label-scope"])
    elif host and re.fullmatch(r"[a-z0-9-]+\.azurewebsites\.net", host):
        rec = ConditionResult(Tri.TRUE, "classic <name>.azurewebsites.net hostname; the app name can be claimed by "
                              "another tenant after deletion",
                              ["src:ms-learn-dangling-dns", "src:infoblox-cdc-2025", "src:cito-fingerprints"])
    else:
        rec = ConditionResult(Tri.UNKNOWN, "hostname is not the classic single-label form; confirm the label scope",
                              ["src:azure-sdk-web-label-scope"])
    return ProviderView(name, attrs.get("location") or provider_region, eps, rec)


def _host_of(v: str | None) -> str | None:
    if not v:
        return None
    v = v.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
    return v.lower().rstrip(".") or None


def _azure_named(rtype: str, attrs: dict, provider_region: str | None) -> ProviderView:
    attr, suffix, srcs = AZURE_NAMED[rtype]
    name = attrs.get("name")
    host = _host_of(attrs.get(attr)) or (f"{name}.{suffix}" if name else None)
    eps = [Endpoint(host, "azure_named")] if host else []
    if host:
        rec = ConditionResult(Tri.TRUE, f"{host} embeds the resource name in the shared {suffix} namespace; "
                              "after deletion another tenant can create a resource with the same name", srcs)
    else:
        rec = ConditionResult(Tri.UNKNOWN, "no name or hostname in the plan", [])
    return ProviderView(name, attrs.get("location") or provider_region, eps, rec)


def _azure_labelled(rtype: str, attrs: dict, provider_region: str | None) -> ProviderView:
    """Container groups and public IPs: an optional DNS label in <label>.<region>.<suffix>."""
    if rtype == "azurerm_container_group":
        label, scope_attr, unsafe = attrs.get("dns_name_label"), "dns_name_label_reuse_policy", {"", "unsecure"}
        src = "src:azure-sdk-aci-reuse-policy"
    else:
        label, scope_attr, unsafe = attrs.get("domain_name_label"), "domain_name_label_scope", {""}
        src = "src:azure-sdk-publicip-label-scope"
    scope = (attrs.get(scope_attr) or "").strip()
    fqdn = _host_of(attrs.get("fqdn"))
    eps = [Endpoint(fqdn, "azure_label")] if fqdn else []
    ip = attrs.get("ip_address") if rtype == "azurerm_public_ip" else None
    if ip:
        eps.append(Endpoint(ip, "ip"))
    if label and scope.lower() in unsafe:
        rec = ConditionResult(Tri.TRUE, f"DNS label {label!r} has no reuse scope ({scope_attr} "
                              f"{'unset' if not scope else scope}); another tenant can claim it after deletion",
                              ["src:ms-learn-dangling-dns", src])
    elif label:
        rec = ConditionResult(Tri.FALSE, f"DNS label uses {scope_attr}={scope}: the FQDN carries a hash and the "
                              "label cannot be reused outside that scope", [src])
    elif ip:
        rec = ConditionResult(Tri.UNKNOWN, "no DNS label; whether Azure re-assigns this released IP address to "
                              "another customer was not verified from a primary source", [])
    else:
        rec = ConditionResult(Tri.FALSE, "no public DNS label or address", [])
    return ProviderView(label, attrs.get("location") or provider_region, eps, rec,
                        holdable=rtype == "azurerm_public_ip")


def _aws_ip(rtype: str, attrs: dict, provider_region: str | None) -> ProviderView:
    ip = attrs.get("public_ip")
    eps = [Endpoint(ip, "ip")] if ip else []
    if attrs.get("public_dns"):
        eps.append(Endpoint(attrs["public_dns"].lower(), "ip_dns"))
    if not ip:
        return ProviderView(None, provider_region, [], ConditionResult(Tri.FALSE, "no public IP address"),
                            holdable=False)
    rec = ConditionResult(Tri.TRUE, f"public IP {ip} returns to AWS's shared pool and can be allocated to another "
                          "account; attackers repeatedly allocate addresses to land on ones still referenced by DNS",
                          ["src:assetnote-ghostbuster"])
    # an Elastic IP can be kept allocated; an instance's auto-assigned address cannot
    return ProviderView(ip, attrs.get("region") or provider_region, eps, rec, holdable=rtype == "aws_eip")


def view(resource_type: str, attrs: dict, provider_region: str | None) -> ProviderView | None:
    if resource_type in AZURE_NAMED:
        return _azure_named(resource_type, attrs, provider_region)
    if resource_type in AZURE_LABELLED:
        return _azure_labelled(resource_type, attrs, provider_region)
    if resource_type in IP_TYPES:
        return _aws_ip(resource_type, attrs, provider_region)
    if resource_type in S3_TYPES:
        return _s3(attrs, provider_region)
    if resource_type in EB_TYPES:
        return _eb(attrs, provider_region)
    if resource_type in AZURE_WEBAPP_TYPES:
        return _azure(attrs, provider_region)
    return None


def _dedupe(eps: list[Endpoint]) -> list[Endpoint]:
    seen, out = set(), []
    for e in eps:
        k = (e.name.lower(), e.kind)
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out
