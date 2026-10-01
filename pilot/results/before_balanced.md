# RetireSafe assessment da3da398-802a-4756-a528-5c3a69a78dd4

*As of 1995-09-01T03:59:53+00:00 · rules 2026-10-01.1 · policy balanced*

**Gate: FAIL**: deletion must not proceed as planned; see blocked / tombstone / review resources

## aws_s3_bucket.archive: **RELEASE**

Name `rs-pilot-archive-123456789012-us-east-1-an` · reclaimable: **false** (bucket is in the account regional namespace; only the owning account can create buckets there)

- the name cannot be obtained by another party (bucket is in the account regional namespace; only the owning account can create buckets there)

- Risk interval: 0.000 to 0.000

Not checked: no access logs cover this resource; consumers outside the supplied inventories (third-party sites, offline clients) can only be observed through logs

## aws_s3_bucket.event_assets: **BLOCK**

Name `rs-pilot-event-assets-2025` · reclaimable: **true** (bucket is in the shared global namespace; after deletion the name can be created by any AWS account in the partition)

- 3 surviving reference(s) would hand traffic to whoever reclaims the name; remove or migrate them before deleting

| Reference | Kind | Path status | Broken by |
|---|---|---|---|
| `route53_before.json#ResourceRecordSets[3] cdn.retiresafe-pilot.example CNAME` | dns | hijackable | - |
| `aws_ssm_parameter.assets_base_url.value` | iac | hijackable | - |
| `app::index.html:7` | code | safe | c5 |
| `app::index.html:14` | code | hijackable | - |
| `app::tools/upload_assets.py:10` | code | safe | c5 |
| `access logs` | traffic | unknown | - |

- Traffic `nasa_jul_aug_1995.log[/images/]`: 1206043 requests, 116125 clients (112710 external), window 62.0 d, silent 0.0 d, conservative quarantine 0.0 d
- Risk interval: 1.000 to 1.000

### Patch: Delete the surviving DNS records (Route 53 change batch)
```
{
  "Comment": "RetireSafe: remove references to rs-pilot-event-assets-2025",
  "Changes": [
    {
      "Action": "DELETE",
      "ResourceRecordSet": {
        "Name": "cdn.retiresafe-pilot.example.",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [
          {
            "Value": "rs-pilot-event-assets-2025.s3.amazonaws.com"
          }
        ]
      }
    }
  ]
}

# apply with:
# aws route53 change-resource-record-sets --hosted-zone-id <ZONE_ID> --change-batch file://change-batch.json
```

### Patch: Rewrite references from rs-pilot-event-assets-2025 to rs-pilot-event-assets-123456789012-us-east-1-an
```
--- a/index.html
+++ b/index.html
@@ -4,13 +4,13 @@
   <meta charset="utf-8">
   <title>Pilot Event 2025</title>
   <!-- Stylesheet pinned with Subresource Integrity: a swapped file would be refused. -->
-  <link rel="stylesheet" href="https://rs-pilot-event-assets-2025.s3.amazonaws.com/css/site.css" integrity="sha384-3t7H6LVInKxmxEb88i+acpyiaE6jBt4F0zncfK1kvdZWQTQf5p7YFQDIXiBnWv3M" crossorigin="anonymous">
+  <link rel="stylesheet" href="https://rs-pilot-event-assets-123456789012-us-east-1-an.s3.amazonaws.com/css/site.css" integrity="sha384-3t7H6LVInKxmxEb88i+acpyiaE6jBt4F0zncfK1kvdZWQTQf5p7YFQDIXiBnWv3M" crossorigin="anonymous">
 </head>
 <body>
   <h1>Pilot Event 2025</h1>
   <p class="countdown" data-target="2025-11-20T09:00:00Z"></p>
   <p>Schedule: <a href="https://event.retiresafe-pilot.example/schedule.html">event.retiresafe-pilot.example/schedule.html</a></p>
   <!-- Script loaded without integrity pinning: whoever owns the bucket controls this code. -->
-  <script src="https://rs-pilot-event-assets-2025.s3.amazonaws.com/js/countdown.js"></script>
+  <script src="https://rs-pilot-event-assets-123456789012-us-east-1-an.s3.amazonaws.com/js/countdown.js"></script>
 </body>
 </html>
```

### Patch: Update infrastructure that still references the resource
```
  aws_ssm_parameter.assets_base_url.value: value = https://rs-pilot-event-assets-2025.s3.amazonaws.com
```

### Patch: Tombstone aws_s3_bucket.event_assets: keep the name, drop the content
```
# Keep owning the bucket name instead of releasing it.
# 1. empty the bucket (objects and versions), 2. remove website/CORS configuration,
# 3. keep the resource below in your configuration.
resource "aws_s3_bucket" "event_assets" {
  bucket = "rs-pilot-event-assets-2025"
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "event_assets" {
  bucket                  = aws_s3_bucket.event_assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# If the content must move, create its replacement in your account regional namespace,
# which other accounts cannot claim (format verified from the AWS SDK model):
#   bucket           = "rs-pilot-event-assets-123456789012-us-east-1-an"
#   bucket_namespace = "account-regional"
```

Not checked: consumers outside the supplied inventories (third-party sites, offline clients) can only be observed through logs

## aws_s3_bucket.event_site: **BLOCK**

Name `event.retiresafe-pilot.example` · reclaimable: **true** (bucket is in the shared global namespace; after deletion the name can be created by any AWS account in the partition)

- 2 surviving reference(s) would hand traffic to whoever reclaims the name; remove or migrate them before deleting

| Reference | Kind | Path status | Broken by |
|---|---|---|---|
| `route53_before.json#ResourceRecordSets[4] event.retiresafe-pilot.example CNAME` | dns | hijackable | - |
| `aws_s3_bucket_website_configuration.event_site.bucket` | iac | safe | c3 |
| `app::index.html:12` | code | hijackable | - |
| `access logs` | traffic | unknown | - |

- Traffic `nasa_jul_aug_1995.log[/shuttle/countdown/]`: 246995 requests, 46924 clients (45628 external), window 62.0 d, silent 0.0001 d, conservative quarantine 0.0 d
- Risk interval: 1.000 to 1.000

### Patch: Delete the surviving DNS records (Route 53 change batch)
```
{
  "Comment": "RetireSafe: remove references to event.retiresafe-pilot.example",
  "Changes": [
    {
      "Action": "DELETE",
      "ResourceRecordSet": {
        "Name": "event.retiresafe-pilot.example.",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [
          {
            "Value": "event.retiresafe-pilot.example.s3-website-us-east-1.amazonaws.com"
          }
        ]
      }
    }
  ]
}

# apply with:
# aws route53 change-resource-record-sets --hosted-zone-id <ZONE_ID> --change-batch file://change-batch.json
```

### Patch: Update or remove code references
```
  app::index.html:12: <p>Schedule: <a href="https://event.retiresafe-pilot.example/schedule.html">event.retiresafe-pilot.example/schedule.html</a></p>
```

### Patch: Tombstone aws_s3_bucket.event_site: keep the name, drop the content
```
# Keep owning the bucket name instead of releasing it.
# 1. empty the bucket (objects and versions), 2. remove website/CORS configuration,
# 3. keep the resource below in your configuration.
resource "aws_s3_bucket" "event_site" {
  bucket = "event.retiresafe-pilot.example"
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "event_site" {
  bucket                  = aws_s3_bucket.event_site.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# If the content must move, create its replacement in your account regional namespace,
# which other accounts cannot claim (format verified from the AWS SDK model):
#   bucket           = "event-retiresafe-pilot-example-123456789012-us-east-1-an"
#   bucket_namespace = "account-regional"
```

Not checked: consumers outside the supplied inventories (third-party sites, offline clients) can only be observed through logs

## aws_s3_bucket.legacy_downloads: **RELEASE**

Name `rs-pilot-legacy-downloads` · reclaimable: **true** (bucket is in the shared global namespace; after deletion the name can be created by any AWS account in the partition)

- no surviving reference is hijackable and the logs show no remaining consumers

| Reference | Kind | Path status | Broken by |
|---|---|---|---|
| `app::tools/sync_downloads.py:8` | code | safe | c4 |
| `app::tools/sync_downloads.py:9` | code | safe | c4 |
| `access logs` | traffic | safe | c4 |

- Traffic `nasa_jul_aug_1995.log[/payloads/level4/]`: 87 requests, 22 clients (16 external), window 62.0 d, silent 16.4983 d, conservative quarantine 3.9 d
- Risk interval: 0.000 to 0.000

Not checked: consumers outside the supplied inventories (third-party sites, offline clients) can only be observed through logs

## aws_s3_bucket_website_configuration.event_site: **NOT_NAME_BEARING**

Name `None` · reclaimable: **unknown** (resource type outside pilot coverage)

- aws_s3_bucket_website_configuration is not a name-bearing type in the pilot rule set

- Risk interval: 0.000 to 0.000

Not checked: takeover rules for aws_s3_bucket_website_configuration

## Outside coverage

- deleted resource outside pilot coverage: aws_s3_bucket_website_configuration.event_site (aws_s3_bucket_website_configuration)
