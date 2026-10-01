"""Publish the static assets. Uses an owner check, so a bucket owned by another account is refused."""
import boto3

ACCOUNT_ID = "123456789012"
s3 = boto3.client("s3")


def publish(path: str, key: str) -> None:
    with open(path, "rb") as f:
        s3.put_object(Bucket="rs-pilot-event-assets-2025", Key=key, Body=f, ExpectedBucketOwner=ACCOUNT_ID)
