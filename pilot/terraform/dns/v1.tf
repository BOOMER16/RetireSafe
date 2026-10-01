# DNS is owned by a separate team and a separate Terraform root (the coordination gap).
resource "aws_route53_zone" "pilot" {
  name = "retiresafe-pilot.example"
}

# Event website served from an S3 website bucket named after the hostname.
resource "aws_route53_record" "event" {
  zone_id = aws_route53_zone.pilot.zone_id
  name    = "event.retiresafe-pilot.example"
  type    = "CNAME"
  ttl     = 300
  records = ["event.retiresafe-pilot.example.s3-website-us-east-1.amazonaws.com"]
}

# Static assets served straight from an S3 REST endpoint.
resource "aws_route53_record" "cdn" {
  zone_id = aws_route53_zone.pilot.zone_id
  name    = "cdn.retiresafe-pilot.example"
  type    = "CNAME"
  ttl     = 300
  records = ["rs-pilot-event-assets-2025.s3.amazonaws.com"]
}

# Unrelated records (documentation-range IP, mail policy) that must not be flagged.
resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.pilot.zone_id
  name    = "www.retiresafe-pilot.example"
  type    = "A"
  ttl     = 300
  records = ["192.0.2.10"]
}

resource "aws_route53_record" "spf" {
  zone_id = aws_route53_zone.pilot.zone_id
  name    = "retiresafe-pilot.example"
  type    = "TXT"
  ttl     = 300
  records = ["v=spf1 include:_spf.mail.retiresafe-pilot.example -all"]
}
