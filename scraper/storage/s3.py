import json
import os
import sys

def save(data: dict | list, name: str, config: dict | None = None) -> str:
    """
    Save data to AWS S3. 
    Serializes to JSON and uploads to s3://bucket/prefix/name.json.
    """
    try:
        import boto3
    except ImportError:
        print("error: boto3 is not installed. Install with: pip install boto3", file=sys.stderr)
        sys.exit(1)

    if config is None:
        config = {}

    bucket = config.get("bucket") or os.environ.get("AWS_S3_BUCKET")
    if not bucket:
        print("error: S3 bucket not specified. Add 'bucket:' to directive 'output' or set AWS_S3_BUCKET env var.", file=sys.stderr)
        sys.exit(1)

    prefix = config.get("prefix", os.environ.get("AWS_S3_PREFIX", "scrapes/"))
    if prefix and not prefix.endswith("/"):
        prefix += "/"

    key = f"{prefix}{name}.json"
    
    compact = config.get("compact", False)
    indent = None if compact else 2
    body_str = json.dumps(data, indent=indent, default=str)

    try:
        s3_client = boto3.client('s3')
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body_str,
            ContentType='application/json'
        )
    except Exception as e:
        print(f"error: failed to upload to S3: {e}", file=sys.stderr)
        sys.exit(1)

    return f"s3://{bucket}/{key}"
