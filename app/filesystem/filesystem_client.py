import boto3
from botocore.client import Config
import os
from dotenv import load_dotenv

load_dotenv()

class FileSystemClient:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            # --- MINIO Configuration ---
            endpoint_url=os.getenv('FILESYSTEM_URL'),
            aws_access_key_id=os.getenv('FILESYSTEM_ID_KEY'),
            aws_secret_access_key=os.getenv('FILESYSTEM_ACCESS_KEY'),
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'} if os.getenv('FORCE_PATH_STYLE') == 'true' else {}
            ),
            region_name=os.getenv('REGION_NAME')
        )
        self.bucket = os.getenv('BUCKET_NAME')

    def upload_video(self, file_path: str, object_name: str, user_id: str, processed: bool = False):
        """Upload a video file to the filesystem bucket."""
        try:
            # tries to create the bucket on upload
            try:
                self.s3_client.create_bucket(Bucket=self.bucket)
            except self.s3_client.exceptions.BucketAlreadyOwnedByYou:
                pass

            if processed:
                proc = 'processed'
            else:
                proc = 'raw'

            object_key = f"{user_id}/{proc}/{object_name}"
            self.s3_client.upload_file(file_path, self.bucket, object_key)
            print(f"Uploaded {object_name} to bucket {self.bucket}")
        
        except Exception as e:
            print(f"Error uploading file: {e}")
            raise