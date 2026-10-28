import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


SOURCE = Path("storage/dashboard")
DESTINATION = Path("web/public/data")
RELEASES = DESTINATION / "releases"

FILES = ("stations.json", "hourly.json", "health.json", "insights.json")


def atomic_json_write(path: Path, payload: dict):
    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=".manifest_",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)

            json.dump(payload, temporary, separators=(",", ":"))
            temporary.flush()
            os.fsync(temporary.fileno())

        os.replace(temporary_path, path)

    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main():
    RELEASES.mkdir(parents=True, exist_ok=True)

    release_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )

    release_dir = RELEASES / release_id
    release_dir.mkdir()

    try:
        for filename in FILES:
            source = SOURCE / filename

            if not source.is_file():
                raise FileNotFoundError(source)

            raw = source.read_bytes()

            # Validate before publishing.
            json.loads(raw)

            destination = release_dir / filename
            destination.write_bytes(raw)

            print(f"Prepared {filename}: {len(raw):,} bytes")

        manifest = {
            "release_id": release_id,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "files": {
                name.removesuffix(".json"): (
                    f"/data/releases/{release_id}/{name}"
                )
                for name in FILES
            },
        }

        # Publish the manifest last.
        atomic_json_write(DESTINATION / "manifest.json", manifest)

        print(f"\nPublished release: {release_id}")
        print("Manifest updated atomically.")

    except Exception:
        shutil.rmtree(release_dir, ignore_errors=True)
        raise


if __name__ == "__main__":
    main()
