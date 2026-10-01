# RetireSafe assessment 3ffb51be-ea79-48e3-a1de-9ae16322b416

*As of 1995-09-01T03:59:53+00:00 · rules 2026-10-01.1 · policy strict*

**Gate: PASS**: all retiring resources may be released

## aws_s3_bucket.archive: **RELEASE**

Name `rs-pilot-archive-123456789012-us-east-1-an` · reclaimable: **false** (bucket is in the account regional namespace; only the owning account can create buckets there)

- the name cannot be obtained by another party (bucket is in the account regional namespace; only the owning account can create buckets there)

- Risk interval: 0.000 to 0.000

Not checked: no access logs cover this resource; consumers outside the supplied inventories (third-party sites, offline clients) can only be observed through logs

## aws_s3_bucket_website_configuration.event_site: **NOT_NAME_BEARING**

Name `None` · reclaimable: **unknown** (resource type outside pilot coverage)

- aws_s3_bucket_website_configuration is not a name-bearing type in the pilot rule set

- Risk interval: 0.000 to 0.000

Not checked: takeover rules for aws_s3_bucket_website_configuration

## Outside coverage

- deleted resource outside pilot coverage: aws_s3_bucket_website_configuration.event_site (aws_s3_bucket_website_configuration)
