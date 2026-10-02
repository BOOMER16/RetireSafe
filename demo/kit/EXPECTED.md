# Expected results (recorded by `python demo/build_demo_kit.py --verify`)

Produced by running every scenario through the same API the console uses. Times are from the build machine; a laptop may differ.

## 01_proposed_change
* Gate **FAIL** (CLI exit 2), verdicts {'release': 1, 'tombstone': 3, 'not_name_bearing': 2}, 0.1 s
* `aws_s3_bucket.archive` → **release**
* `aws_s3_bucket.event_assets` → **tombstone**
  * `route53.json#ResourceRecordSets[3] cdn.retiresafe-pilot.example CNAME`: unknown
  * `aws_ssm_parameter.assets_base_url.value`: unknown
  * `app::index.html:7`: safe (breaks at c5)
  * `app::index.html:14`: unknown
  * `app::tools/upload_assets.py:10`: safe (breaks at c5)
* `aws_s3_bucket.event_site` → **tombstone**
  * `route53.json#ResourceRecordSets[4] event.retiresafe-pilot.example CNAME`: unknown
  * `aws_s3_bucket_website_configuration.event_site.bucket`: safe (breaks at c3)
  * `app::index.html:12`: unknown
* `aws_s3_bucket.legacy_downloads` → **tombstone**
  * `app::config/legacy.env:3`: unknown
  * `app::tools/mirror_legacy.sh:3`: unknown
  * `app::tools/sync_downloads.py:8`: unknown
  * `app::tools/sync_downloads.py:9`: unknown
* `aws_s3_bucket_website_configuration.event_site` → **not_name_bearing**
* `aws_ssm_parameter.legacy_db_password` → **not_name_bearing**

## 02_add_real_traffic
* Gate **FAIL** (CLI exit 2), verdicts {'release': 1, 'block': 2, 'tombstone': 1, 'not_name_bearing': 2}, 41.6 s
* `aws_s3_bucket.archive` → **release**
* `aws_s3_bucket.event_assets` → **block**
  * `route53.json#ResourceRecordSets[3] cdn.retiresafe-pilot.example CNAME`: hijackable
  * `aws_ssm_parameter.assets_base_url.value`: hijackable
  * `app::index.html:7`: safe (breaks at c5)
  * `app::index.html:14`: hijackable
  * `app::tools/upload_assets.py:10`: safe (breaks at c5)
  * `access logs`: unknown
* `aws_s3_bucket.event_site` → **block**
  * `route53.json#ResourceRecordSets[4] event.retiresafe-pilot.example CNAME`: hijackable
  * `aws_s3_bucket_website_configuration.event_site.bucket`: safe (breaks at c3)
  * `app::index.html:12`: hijackable
  * `access logs`: unknown
* `aws_s3_bucket.legacy_downloads` → **tombstone**
  * `app::config/legacy.env:3`: safe (breaks at c4)
  * `app::tools/mirror_legacy.sh:3`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:8`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:9`: safe (breaks at c4)
  * `access logs`: safe (breaks at c4)
* `aws_s3_bucket_website_configuration.event_site` → **not_name_bearing**
* `aws_ssm_parameter.legacy_db_password` → **not_name_bearing**

## 03_balanced_policy
* Gate **FAIL** (CLI exit 2), verdicts {'release': 2, 'block': 2, 'not_name_bearing': 2}, 37.9 s
* `aws_s3_bucket.archive` → **release**
* `aws_s3_bucket.event_assets` → **block**
  * `route53.json#ResourceRecordSets[3] cdn.retiresafe-pilot.example CNAME`: hijackable
  * `aws_ssm_parameter.assets_base_url.value`: hijackable
  * `app::index.html:7`: safe (breaks at c5)
  * `app::index.html:14`: hijackable
  * `app::tools/upload_assets.py:10`: safe (breaks at c5)
  * `access logs`: unknown
* `aws_s3_bucket.event_site` → **block**
  * `route53.json#ResourceRecordSets[4] event.retiresafe-pilot.example CNAME`: hijackable
  * `aws_s3_bucket_website_configuration.event_site.bucket`: safe (breaks at c3)
  * `app::index.html:12`: hijackable
  * `access logs`: unknown
* `aws_s3_bucket.legacy_downloads` → **release**
  * `app::config/legacy.env:3`: safe (breaks at c4)
  * `app::tools/mirror_legacy.sh:3`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:8`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:9`: safe (breaks at c4)
  * `access logs`: safe (breaks at c4)
* `aws_s3_bucket_website_configuration.event_site` → **not_name_bearing**
* `aws_ssm_parameter.legacy_db_password` → **not_name_bearing**

## 04_corrected_change
* Gate **PASS** (CLI exit 0), verdicts {'release': 1, 'not_name_bearing': 2}, 24.8 s
* `aws_s3_bucket.archive` → **release**
* `aws_s3_bucket_website_configuration.event_site` → **not_name_bearing**
* `aws_ssm_parameter.legacy_db_password` → **not_name_bearing**

## expert/A_pin_script_with_sri
* Gate **FAIL** (CLI exit 2), verdicts {'release': 1, 'block': 2, 'tombstone': 1, 'not_name_bearing': 2}, 34.3 s
* `aws_s3_bucket.archive` → **release**
* `aws_s3_bucket.event_assets` → **block**
  * `route53.json#ResourceRecordSets[3] cdn.retiresafe-pilot.example CNAME`: hijackable
  * `aws_ssm_parameter.assets_base_url.value`: hijackable
  * `app::index.html:7`: safe (breaks at c5)
  * `app::index.html:14`: safe (breaks at c5)
  * `app::tools/upload_assets.py:10`: safe (breaks at c5)
  * `access logs`: unknown
* `aws_s3_bucket.event_site` → **block**
  * `route53.json#ResourceRecordSets[4] event.retiresafe-pilot.example CNAME`: hijackable
  * `aws_s3_bucket_website_configuration.event_site.bucket`: safe (breaks at c3)
  * `app::index.html:12`: hijackable
  * `access logs`: unknown
* `aws_s3_bucket.legacy_downloads` → **tombstone**
  * `app::config/legacy.env:3`: safe (breaks at c4)
  * `app::tools/mirror_legacy.sh:3`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:8`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:9`: safe (breaks at c4)
  * `access logs`: safe (breaks at c4)
* `aws_s3_bucket_website_configuration.event_site` → **not_name_bearing**
* `aws_ssm_parameter.legacy_db_password` → **not_name_bearing**

## expert/B_drop_owner_check
* Gate **FAIL** (CLI exit 2), verdicts {'release': 1, 'block': 2, 'tombstone': 1, 'not_name_bearing': 2}, 34.4 s
* `aws_s3_bucket.archive` → **release**
* `aws_s3_bucket.event_assets` → **block**
  * `route53.json#ResourceRecordSets[3] cdn.retiresafe-pilot.example CNAME`: hijackable
  * `aws_ssm_parameter.assets_base_url.value`: hijackable
  * `app::index.html:7`: safe (breaks at c5)
  * `app::index.html:14`: hijackable
  * `app::tools/upload_assets.py:10`: hijackable
  * `access logs`: unknown
* `aws_s3_bucket.event_site` → **block**
  * `route53.json#ResourceRecordSets[4] event.retiresafe-pilot.example CNAME`: hijackable
  * `aws_s3_bucket_website_configuration.event_site.bucket`: safe (breaks at c3)
  * `app::index.html:12`: hijackable
  * `access logs`: unknown
* `aws_s3_bucket.legacy_downloads` → **tombstone**
  * `app::config/legacy.env:3`: safe (breaks at c4)
  * `app::tools/mirror_legacy.sh:3`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:8`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:9`: safe (breaks at c4)
  * `access logs`: safe (breaks at c4)
* `aws_s3_bucket_website_configuration.event_site` → **not_name_bearing**
* `aws_ssm_parameter.legacy_db_password` → **not_name_bearing**

## expert/C_comment_out_script
* Gate **FAIL** (CLI exit 2), verdicts {'release': 1, 'block': 2, 'tombstone': 1, 'not_name_bearing': 2}, 37.4 s
* `aws_s3_bucket.archive` → **release**
* `aws_s3_bucket.event_assets` → **block**
  * `route53.json#ResourceRecordSets[3] cdn.retiresafe-pilot.example CNAME`: hijackable
  * `aws_ssm_parameter.assets_base_url.value`: hijackable
  * `app::index.html:7`: safe (breaks at c5)
  * `app::index.html:14`: safe (breaks at c4)
  * `app::tools/upload_assets.py:10`: safe (breaks at c5)
  * `access logs`: unknown
* `aws_s3_bucket.event_site` → **block**
  * `route53.json#ResourceRecordSets[4] event.retiresafe-pilot.example CNAME`: hijackable
  * `aws_s3_bucket_website_configuration.event_site.bucket`: safe (breaks at c3)
  * `app::index.html:12`: hijackable
  * `access logs`: unknown
* `aws_s3_bucket.legacy_downloads` → **tombstone**
  * `app::config/legacy.env:3`: safe (breaks at c4)
  * `app::tools/mirror_legacy.sh:3`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:8`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:9`: safe (breaks at c4)
  * `access logs`: safe (breaks at c4)
* `aws_s3_bucket_website_configuration.event_site` → **not_name_bearing**
* `aws_ssm_parameter.legacy_db_password` → **not_name_bearing**

## expert/D_hostile_markup
* Gate **FAIL** (CLI exit 2), verdicts {'release': 1, 'block': 2, 'tombstone': 1, 'not_name_bearing': 2}, 36.1 s
* `aws_s3_bucket.archive` → **release**
* `aws_s3_bucket.event_assets` → **block**
  * `route53.json#ResourceRecordSets[3] cdn.retiresafe-pilot.example CNAME`: hijackable
  * `aws_ssm_parameter.assets_base_url.value`: hijackable
  * `app::index.html:7`: safe (breaks at c5)
  * `app::index.html:14`: hijackable
  * `app::tools/upload_assets.py:10`: safe (breaks at c5)
  * `app::docs/notes.html:1`: hijackable
  * `access logs`: unknown
* `aws_s3_bucket.event_site` → **block**
  * `route53.json#ResourceRecordSets[4] event.retiresafe-pilot.example CNAME`: hijackable
  * `aws_s3_bucket_website_configuration.event_site.bucket`: safe (breaks at c3)
  * `app::index.html:12`: hijackable
  * `access logs`: unknown
* `aws_s3_bucket.legacy_downloads` → **tombstone**
  * `app::config/legacy.env:3`: safe (breaks at c4)
  * `app::tools/mirror_legacy.sh:3`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:8`: safe (breaks at c4)
  * `app::tools/sync_downloads.py:9`: safe (breaks at c4)
  * `access logs`: safe (breaks at c4)
* `aws_s3_bucket_website_configuration.event_site` → **not_name_bearing**
* `aws_ssm_parameter.legacy_db_password` → **not_name_bearing**

## expert/E_zip_slip
* **HTTP 400**: archive member escapes the extraction directory: ../../outside.txt
