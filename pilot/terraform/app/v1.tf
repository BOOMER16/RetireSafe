# Application root (owned by the app team). Version 1: everything live.
resource "aws_s3_bucket" "event_site" {
  bucket = "event.retiresafe-pilot.example"
}

resource "aws_s3_bucket_website_configuration" "event_site" {
  bucket = aws_s3_bucket.event_site.id
  index_document {
    suffix = "index.html"
  }
}

resource "aws_s3_bucket" "event_assets" {
  bucket = "rs-pilot-event-assets-2025"
}

resource "aws_s3_bucket" "legacy_downloads" {
  bucket = "rs-pilot-legacy-downloads"
}

# Created in the account regional namespace: only this account can ever hold the name.
resource "aws_s3_bucket" "archive" {
  bucket           = "rs-pilot-archive-123456789012-us-east-1-an"
  bucket_namespace = "account-regional"
}

# Configuration that outlives the buckets (an infrastructure reference).
resource "aws_ssm_parameter" "assets_base_url" {
  name  = "/pilot/assets_base_url"
  type  = "String"
  value = "https://rs-pilot-event-assets-2025.s3.amazonaws.com"
}
