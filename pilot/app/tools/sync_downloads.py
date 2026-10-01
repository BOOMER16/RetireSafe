"""Nightly job that mirrors the legacy download area. No owner check."""
import boto3

s3 = boto3.client("s3")


def mirror(prefix: str, dest: str) -> None:
    for obj in s3.list_objects_v2(Bucket="rs-pilot-legacy-downloads", Prefix=prefix).get("Contents", []):
        s3.download_file("rs-pilot-legacy-downloads", obj["Key"], f"{dest}/{obj['Key'].split('/')[-1]}")
