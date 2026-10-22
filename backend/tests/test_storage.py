from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
import pytest
from app.storage import enforce_private_bucket


def error(code, status):
    return ClientError({'Error': {'Code': code}, 'ResponseMetadata': {'HTTPStatusCode': status}}, 'S3Operation')


def test_s3_compatible_store_must_deny_anonymous_reads(app):
    signed, anonymous = MagicMock(), MagicMock()
    signed.put_public_access_block.side_effect = error('NotImplemented', 501)
    anonymous.list_objects_v2.side_effect = error('AccessDenied', 403)
    anonymous.get_object.side_effect = error('AccessDenied', 403)
    with patch('app.storage.client', return_value=signed), patch('app.storage.boto3.client', return_value=anonymous):
        enforce_private_bucket()
    signed.delete_object.assert_called_once()
    anonymous.get_object.assert_called_once()


def test_public_bucket_prevents_startup(app):
    signed, anonymous = MagicMock(), MagicMock()
    anonymous.list_objects_v2.return_value = {}
    with patch('app.storage.client', return_value=signed), patch('app.storage.boto3.client', return_value=anonymous):
        with pytest.raises(ValueError, match='Anonymous access'):
            enforce_private_bucket()
    signed.delete_object.assert_called_once()
