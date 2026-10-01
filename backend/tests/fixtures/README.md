# Test fixtures

| File | Origin | Real or constructed |
|---|---|---|
| `aws_s3_access_log_doc_examples.log` | Example log records from the Amazon S3 Developer Guide, *Amazon S3 server access log format* (`awsdocs/amazon-s3-developer-guide`, `doc_source/LogFormat.md`, lines 13–17). Licence CC BY-SA 4.0. | AWS-published example records |
| `aws_cloudfront_doc_examples.log` | `#Version`/`#Fields` header and example records from the Amazon CloudFront Developer Guide, *Standard logs* (`awsdocs/amazon-cloudfront-developer-guide`, `doc_source/AccessLogs.md`, lines 444–449). Licence CC BY-SA 4.0. | AWS-published example records |
| `nasa_jul95_first2000.log` | First 2,000 lines of NASA-HTTP `NASA_access_log_Jul95` (Internet Traffic Archive). | Real traffic |
| `plan_azure_eb_fragment.json` | Minimal Terraform plan JSON with an `azurerm_linux_web_app` and an `aws_elastic_beanstalk_environment` deletion, written to the documented plan JSON schema. | **Constructed**: no Azure emulator or account was available to generate a real azurerm/EB plan. Used only to test rule dispatch. |

The pilot's Terraform plans and Route 53 exports in `../../pilot/generated/` are real tool output
(Terraform 1.16.4, hashicorp/aws 6.67.0 against moto 5.2.3); see `pilot/generated/manifest.json`.
| `cloudtrail_deletebucket_event.json` | AWS's documented CloudTrail S3 record (`PutBucketAcl` example in `awsdocs/amazon-s3-userguide`, `cloudtrail-logging-understanding-s3-entries.md`, CC BY-SA 4.0) with `eventName` changed to `DeleteBucket`, a placeholder bucket name added, and the access key removed, wrapped in EventBridge's "AWS API Call via CloudTrail" envelope. | **Adapted** from an AWS example |
| `sarif-schema-2.1.0.json` | OASIS SARIF 2.1.0 JSON schema (`oasis-tcs/sarif-spec`). | Official schema |
