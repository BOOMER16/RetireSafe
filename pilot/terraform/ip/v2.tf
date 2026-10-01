# Proposed change: delete the instance and release the Elastic IP; the DNS zone lives in
# another root (here: kept), so the A records survive.
resource "aws_route53_zone" "ipzone" {
  name = "ip.retiresafe-pilot.example"
}

resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.ipzone.zone_id
  name    = "api.ip.retiresafe-pilot.example"
  type    = "A"
  ttl     = 300
  records = ["PLACEHOLDER_EIP"]
}

resource "aws_route53_record" "web" {
  zone_id = aws_route53_zone.ipzone.zone_id
  name    = "web.ip.retiresafe-pilot.example"
  type    = "A"
  ttl     = 300
  records = ["PLACEHOLDER_WEB"]
}
