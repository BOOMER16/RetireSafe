"""Extract cloud resource names from arbitrary text (URLs, hostnames, SDK calls)."""
from __future__ import annotations

import re

_B = r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]"
# bucket.s3.amazonaws.com, bucket.s3.us-east-1.amazonaws.com, bucket.s3-website-us-east-1.amazonaws.com,
# bucket.s3-website.eu-west-1.amazonaws.com, bucket.s3.dualstack.us-east-1.amazonaws.com, bucket.s3-us-west-2...
S3_VHOST = re.compile(rf"(?<![a-z0-9.-])({_B})\.s3(?:[.-](?:website[.-])?(?:dualstack\.)?[a-z0-9-]+)?\.amazonaws\.com(?:\.cn)?",
                      re.I)
# https://s3.amazonaws.com/bucket/key , https://s3.us-east-1.amazonaws.com/bucket
S3_PATH = re.compile(rf"(?<![a-z0-9.-])s3(?:[.-](?:dualstack\.)?[a-z0-9-]+)?\.amazonaws\.com(?:\.cn)?/({_B})(?=[/?#\"'\s)]|$)",
                     re.I)
S3_URI = re.compile(rf"\bs3a?://({_B})(?=[/\"'\s)]|$)", re.I)
S3_ARN = re.compile(rf"\barn:aws[a-z-]*:s3:::({_B})(?=[/\"'\s)*]|$)", re.I)
SDK_BUCKET = re.compile(rf"\b[Bb]ucket(?:_?[Nn]ame)?[\"']?\s*[:=]\s*[\"']({_B})[\"']")
# An S3 endpoint with no bucket label (website or REST, any region). S3 then takes the bucket name
# from the HTTP Host header, i.e. the hostname the client asked for.
S3_BARE = re.compile(r"^s3(?:[.-](?:website[.-])?(?:dualstack\.)?[a-z0-9-]+)?\.amazonaws\.com(?:\.cn)?$", re.I)
S3_WEBSITE_BARE = S3_BARE  # backwards-compatible name
HOSTNAME = re.compile(r"(?<![a-z0-9-])((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})(?![a-z0-9-])", re.I)


def s3_buckets_in(text: str) -> set[str]:
    """Bucket names referenced in ``text`` via URLs, s3:// URIs, ARNs or SDK ``Bucket=`` arguments."""
    found = set()
    for rx in (S3_VHOST, S3_PATH, S3_URI, S3_ARN, SDK_BUCKET):
        for m in rx.finditer(text):
            name = m.group(1).lower()
            if name not in ("s3", "www") and not name.startswith("s3-website"):
                found.add(name)
    return found


def bucket_from_dns(record_name: str, target: str) -> str | None:
    """Bucket a DNS target refers to. A bare S3 endpoint (no bucket label) serves the bucket whose name
    equals the requested hostname (S3 reads it from the Host header)."""
    t = target.lower().rstrip(".")
    if S3_BARE.match(t):
        return record_name.lower().rstrip(".")
    hits = s3_buckets_in(t)
    return next(iter(hits)) if hits else None


def hostnames_in(text: str) -> set[str]:
    return {m.group(1).lower() for m in HOSTNAME.finditer(text)}
