import boto3
from botocore.client import Config
from app.core.config import settings


class FileSystemClient:
    def __init__(self):
        client_kwargs = dict(
            aws_access_key_id=settings.FILESYSTEM_ID_KEY,
            aws_secret_access_key=settings.FILESYSTEM_ACCESS_KEY,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"} if settings.FORCE_PATH_STYLE else {},
            ),
            region_name=settings.REGION_NAME,
        )
        self.s3_client = boto3.client("s3", endpoint_url=settings.FILESYSTEM_URL, **client_kwargs)

        # Separate client whose endpoint is the public URL — presigned URLs
        # generated with this client are resolvable by the browser.
        public_url = settings.FILESYSTEM_PUBLIC_URL or settings.FILESYSTEM_URL
        self.s3_public_client = boto3.client("s3", endpoint_url=public_url, **client_kwargs)

        self.bucket = settings.BUCKET_NAME
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.s3_client.create_bucket(Bucket=self.bucket)

    def _object_name(self, user_id: int, group_id: int, file_name: str) -> str:
        return f"{user_id}/{group_id}/{file_name}"

    def upload_video_stream(
        self, file_stream, filename: str, user_id: int, group_id: int
    ):
        """Stream-upload directly to MinIO using multipart transfer (no ContentLength required)."""
        import mimetypes
        content_type = mimetypes.guess_type(filename)[0] or "video/mp4"
        self.s3_client.upload_fileobj(
            file_stream,
            self.bucket,
            self._object_name(user_id, group_id, filename),
            ExtraArgs={"ContentType": content_type},
        )

    def get_object_size(self, user_id: int, group_id: int, file_name: str) -> int:
        head = self.s3_client.head_object(
            Bucket=self.bucket,
            Key=self._object_name(user_id, group_id, file_name),
        )
        return head["ContentLength"]

    def get_object_range(self, user_id: int, group_id: int, file_name: str, start: int, end: int):
        """Return an iterable over `start`–`end` bytes of the stored object."""
        response = self.s3_client.get_object(
            Bucket=self.bucket,
            Key=self._object_name(user_id, group_id, file_name),
            Range=f"bytes={start}-{end}",
        )
        return response["Body"].iter_chunks(512 * 1024)  # 512 KB chunks

    def get_object_first_bytes(self, user_id: int, group_id: int, file_name: str, size: int) -> bytes:
        """Fetch the first `size` bytes of a stored object (used for previews)."""
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=self._object_name(user_id, group_id, file_name),
                Range=f"bytes=0-{size - 1}",
            )
            return response["Body"].read()
        except Exception:
            return b""

    def upload_thumbnail(self, thumbnail_data: bytes, user_id: int, group_id: int):
        import io
        self.s3_client.upload_fileobj(
            io.BytesIO(thumbnail_data),
            self.bucket,
            self._object_name(user_id, group_id, "thumbnail.jpg"),
            ExtraArgs={"ContentType": "image/jpeg"},
        )

    def get_thumbnail(self, user_id: int, group_id: int) -> bytes:
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket,
                Key=self._object_name(user_id, group_id, "thumbnail.jpg"),
            )
            return response["Body"].read()
        except Exception:
            return b""

    def delete_object(self, user_id: int, group_id: int, file_name: str):
        self.s3_client.delete_object(
            Bucket=self.bucket,
            Key=self._object_name(user_id, group_id, file_name),
        )

    def get_object_bytes(self, key: str) -> bytes | None:
        """Return the full content of an object, or None if it doesn't exist."""
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except Exception:
            return None

    def list_objects_with_prefix(self, prefix: str) -> list[dict]:
        """Return [{key, size}] for every object under prefix (directory markers excluded)."""
        paginator = self.s3_client.get_paginator("list_objects_v2")
        objects = []
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if not obj["Key"].endswith("/"):
                    objects.append({"key": obj["Key"], "size": obj["Size"]})
        return objects

    def generate_presigned_url(self, key: str, expiry: int = 3600) -> str:
        return self.s3_public_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expiry,
        )

    def get_object_range_by_key(self, key: str, start: int, end: int):
        response = self.s3_client.get_object(
            Bucket=self.bucket,
            Key=key,
            Range=f"bytes={start}-{end}",
        )
        return response["Body"].iter_chunks(512 * 1024)

    def delete_group(self, user_id: int, group_id: int):
        """Delete all objects under {user_id}/{group_id}/ (video file + thumbnail + any derivatives)."""
        prefix = f"{user_id}/{group_id}/"
        paginator = self.s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = page.get("Contents", [])
            if not objects:
                continue
            self.s3_client.delete_objects(
                Bucket=self.bucket,
                Delete={"Objects": [{"Key": obj["Key"]} for obj in objects]},
            )

    # Legacy file-based upload (kept for backward compatibility)
    def upload_video(self, file_path: str, object_name: str, user_id: str, processed: bool = False):
        try:
            try:
                self.s3_client.create_bucket(Bucket=self.bucket)
            except self.s3_client.exceptions.BucketAlreadyOwnedByYou:
                pass

            proc = "processed" if processed else "raw"
            self.s3_client.upload_file(
                file_path, self.bucket, f"{user_id}/{proc}/{object_name}"
            )
        except Exception as e:
            print(f"Error uploading file: {e}")
            raise
