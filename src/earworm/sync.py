"""Mirror the content dir to a Cloudflare R2 bucket over the S3 API.

Configuration comes from R2_* environment variables, read from a repo-root
`.env` file if present (see `.env.example`): R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
R2_SECRET_ACCESS_KEY, R2_BUCKET. The bucket layout mirrors the content dir
exactly (library.json at the bucket root, then <id>/...), so the web app can
use the bucket's public URL as its content base.

Uploads are content-addressed: a file is skipped when the remote ETag matches
its local MD5 (objects are uploaded single-part so the ETag *is* the MD5).
Bucket CORS is (re)applied on every sync so browser fetches and Web Audio
media elements work from any app origin.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

_ENV_KEYS = ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET")

_CONTENT_TYPES = {
    ".json": "application/json",
    ".m4a": "audio/mp4",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".mid": "audio/midi",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

# JSON is re-written on every process/library run; media only changes if a song
# is re-processed under the same id, so it can cache much longer.
_CACHE_JSON = "public, max-age=300"
_CACHE_MEDIA = "public, max-age=86400"

_CORS = {
    "CORSRules": [
        {
            "AllowedMethods": ["GET", "HEAD"],
            "AllowedOrigins": ["*"],
            "AllowedHeaders": ["*"],
            "ExposeHeaders": ["Content-Length", "Content-Range", "ETag"],
            "MaxAgeSeconds": 86400,
        }
    ]
}


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _config() -> dict[str, str]:
    _load_dotenv()
    missing = [k for k in _ENV_KEYS if not os.environ.get(k)]
    if missing:
        raise SystemExit(
            f"missing R2 config: {', '.join(missing)} "
            "(set in the environment or a repo-root .env; see .env.example)"
        )
    return {k: os.environ[k] for k in _ENV_KEYS}


def _client(cfg: dict[str, str]):
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=f"https://{cfg['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=cfg["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=cfg["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def _remote_etags(s3, bucket: str) -> dict[str, str]:
    etags: dict[str, str] = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            etags[obj["Key"]] = obj["ETag"].strip('"')
    return etags


def sync(content_dir: Path, *, delete: bool = False, dry_run: bool = False) -> None:
    """Upload changed files, optionally delete remote strays, ensure CORS."""
    if not content_dir.is_dir():
        raise SystemExit(f"no content dir at {content_dir}")
    cfg = _config()
    s3, bucket = _client(cfg), cfg["R2_BUCKET"]

    local = {
        str(p.relative_to(content_dir)): p
        for p in sorted(content_dir.rglob("*"))
        if p.is_file() and p.name != ".DS_Store"
    }
    remote = _remote_etags(s3, bucket)

    uploaded = skipped = 0
    for key, path in local.items():
        data = path.read_bytes()
        if remote.get(key) == hashlib.md5(data).hexdigest():
            skipped += 1
            continue
        suffix = path.suffix.lower()
        print(f"{'would upload' if dry_run else 'upload'}  {key}  ({len(data) / 1e6:.1f} MB)")
        if not dry_run:
            s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=data,
                ContentType=_CONTENT_TYPES.get(suffix, "application/octet-stream"),
                CacheControl=_CACHE_JSON if suffix == ".json" else _CACHE_MEDIA,
            )
        uploaded += 1

    stray = sorted(set(remote) - set(local))
    if delete and stray:
        for key in stray:
            print(f"{'would delete' if dry_run else 'delete'}  {key}")
        if not dry_run:
            for i in range(0, len(stray), 1000):
                batch = [{"Key": k} for k in stray[i : i + 1000]]
                s3.delete_objects(Bucket=bucket, Delete={"Objects": batch})

    if not dry_run:
        try:
            s3.put_bucket_cors(Bucket=bucket, CORSConfiguration=_CORS)
        except s3.exceptions.ClientError:
            # Object-scoped tokens can't manage bucket CORS; without it the
            # deployed app can't fetch content (and stems play silently).
            print(
                "note: couldn't set bucket CORS with this token — if not already "
                "configured, add a CORS policy in the R2 dashboard (bucket -> "
                "Settings) allowing GET/HEAD from any origin."
            )

    note = f", {len(stray)} stray remote (use --delete)" if stray and not delete else ""
    print(f"{uploaded} uploaded, {skipped} unchanged{note}")
