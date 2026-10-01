# Version 3 (after applying RetireSafe's patches): global-namespace names are kept as
# tombstones, content moves to an account-regional bucket, the archive is released.
resource "aws_s3_bucket" "event_site" {
  bucket = "event.retiresafe-pilot.example"
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "event_assets" {
  bucket = "rs-pilot-event-assets-2025"
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "legacy_downloads" {
  bucket = "rs-pilot-legacy-downloads"
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket" "event_assets_v2" {
  bucket           = "rs-pilot-event-assets-123456789012-us-east-1-an"
  bucket_namespace = "account-regional"
}

resource "aws_ssm_parameter" "assets_base_url" {
  name  = "/pilot/assets_base_url"
  type  = "String"
  value = "https://rs-pilot-event-assets-123456789012-us-east-1-an.s3.amazonaws.com"
}
