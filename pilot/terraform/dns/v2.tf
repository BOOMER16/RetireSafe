# After remediation: event and cdn records removed.
# DNS is owned by a separate team and a separate Terraform root (the coordination gap).
resource "aws_route53_zone" "pilot" {
  name = "retiresafe-pilot.example"
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
