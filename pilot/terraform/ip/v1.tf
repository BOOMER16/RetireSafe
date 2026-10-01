# IP-address scenario (Ghostbuster class): DNS points at an Elastic IP and at an instance's public IP.
data "aws_ami" "any" {
  most_recent = true
  owners      = ["amazon"]
}

resource "aws_instance" "web" {
  ami                         = data.aws_ami.any.id
  instance_type               = "t3.micro"
  associate_public_ip_address = true
}

resource "aws_eip" "api" {
  domain = "vpc"
}

resource "aws_route53_zone" "ipzone" {
  name = "ip.retiresafe-pilot.example"
}

resource "aws_route53_record" "api" {
  zone_id = aws_route53_zone.ipzone.zone_id
  name    = "api.ip.retiresafe-pilot.example"
  type    = "A"
  ttl     = 300
  records = [aws_eip.api.public_ip]
}

resource "aws_route53_record" "web" {
  zone_id = aws_route53_zone.ipzone.zone_id
  name    = "web.ip.retiresafe-pilot.example"
  type    = "A"
  ttl     = 300
  records = [aws_instance.web.public_ip]
}
