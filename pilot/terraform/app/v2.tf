# Version 2 (proposed change after the event): delete all four buckets.
# The SSM parameter stays, and DNS lives in another root, so references survive.
resource "aws_ssm_parameter" "assets_base_url" {
  name  = "/pilot/assets_base_url"
  type  = "String"
  value = "https://rs-pilot-event-assets-2025.s3.amazonaws.com"
}
