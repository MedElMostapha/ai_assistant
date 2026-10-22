from pathlib import Path
from flask import current_app
import boto3


def client():
    from botocore.config import Config
    c = current_app.config
    return boto3.client('s3', endpoint_url=c['S3_ENDPOINT'], region_name=c['S3_REGION'], aws_access_key_id=c['S3_ACCESS_KEY'], aws_secret_access_key=c['S3_SECRET_KEY'], config=Config(connect_timeout=5, read_timeout=15, retries={'max_attempts': 2}, s3={'addressing_style': 'path'}))


def put(key, content):
    c = current_app.config
    if c['STORAGE_BACKEND'] == 's3':
        client().put_object(Bucket=c['S3_BUCKET'], Key=key, Body=content, ContentType='application/octet-stream')
    else:
        folder = Path(c['STORAGE_PATH'])
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = folder / key
        target.write_bytes(content)
        target.chmod(0o600)


def get(key):
    c = current_app.config
    if c['STORAGE_BACKEND'] == 's3':
        return client().get_object(Bucket=c['S3_BUCKET'], Key=key)['Body'].read()
    return (Path(c['STORAGE_PATH']) / key).read_bytes()


def delete(key):
    c = current_app.config
    if c['STORAGE_BACKEND'] == 's3':
        client().delete_object(Bucket=c['S3_BUCKET'], Key=key)
    else:
        (Path(c['STORAGE_PATH']) / key).unlink(missing_ok=True)


def enforce_private_bucket():
    """Use the AWS block when supported, and always test anonymous list/read denial."""
    import secrets
    from botocore import UNSIGNED
    from botocore.config import Config
    from botocore.exceptions import ClientError
    cfg = current_app.config
    s3, bucket = client(), cfg['S3_BUCKET']
    try:
        s3.put_public_access_block(Bucket=bucket, PublicAccessBlockConfiguration=dict(BlockPublicAcls=True, IgnorePublicAcls=True, BlockPublicPolicy=True, RestrictPublicBuckets=True))
    except ClientError as exc:
        # Some compatible stores (including SeaweedFS) have private IAM defaults
        # but do not implement AWS's account-level public access block API.
        if exc.response['Error']['Code'] not in ('NotImplemented', '501'):
            raise
    anonymous = boto3.client('s3', endpoint_url=cfg['S3_ENDPOINT'], region_name=cfg['S3_REGION'], aws_access_key_id='anonymous', aws_secret_access_key='anonymous', config=Config(signature_version=UNSIGNED, connect_timeout=5, read_timeout=10, retries={'max_attempts': 1}, s3={'addressing_style': 'path'}))
    key = secrets.token_hex(32)
    s3.put_object(Bucket=bucket, Key=key, Body=b'privacy-check')
    try:
        operations = [lambda: anonymous.list_objects_v2(Bucket=bucket, MaxKeys=1), lambda: anonymous.get_object(Bucket=bucket, Key=key)]
        for operation in operations:
            try:
                result = operation()
                if 'Body' in result:
                    result['Body'].close()
            except ClientError as exc:
                if exc.response['ResponseMetadata']['HTTPStatusCode'] in (401, 403):
                    continue
                raise
            raise ValueError('Anonymous access is enabled; refusing to start.')
    finally:
        s3.delete_object(Bucket=bucket, Key=key)
