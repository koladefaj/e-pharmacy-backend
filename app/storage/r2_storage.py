import os
import logging
import tempfile
from io import BytesIO
import boto3
from app.storage.base import StorageInterface
from app.core.config import settings

logger = logging.getLogger(__name__)

class R2Storage(StorageInterface):
    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        self.bucket = settings.s3_bucket

    def generate_presigned_url(self, key: str, expires_in: int = 300) -> str:

        return self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
            },
            ExpiresIn=expires_in,
        )


    async def upload(self, file_id: str, file_name: str, file_bytes: bytes, content_type: str):
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=file_id,
                Body=BytesIO(file_bytes),
                ContentType=content_type,
            )
            logger.info(f"R2 uploaded: {file_id}")
        except Exception as e:
            logger.error(f"R2 upload failed: {str(e)}")
            raise

    def get_file_path(self, file_id: str) -> str:
        safe_name = file_id.replace("/", "_")
        with tempfile.NamedTemporaryFile(prefix=safe_name, delete=False) as tmp_file:
            temp_path = tmp_file.name

        if os.path.exists(temp_path):
            return temp_path

        try:
            self.client.download_file(
                Bucket=self.bucket,
                Key=file_id,
                Filename=temp_path,
            )
            return temp_path
        except Exception as e:
            logger.error(f"R2 download failed: {str(e)}")
            raise
