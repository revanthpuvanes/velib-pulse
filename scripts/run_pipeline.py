import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_stage(name, command, env=None):
    print(f"\n{'=' * 55}", flush=True)
    print(f"🚀 STARTING: {name}", flush=True)
    print(f"{'=' * 55}", flush=True)

    start = time.monotonic()

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        env=env,
    )

    duration = time.monotonic() - start

    if result.returncode != 0:
        print(
            f"\n❌ {name} FAILED "
            f"(exit code {result.returncode})",
            flush=True,
        )
        raise SystemExit(result.returncode)

    print(
        f"\n✅ {name} COMPLETED "
        f"in {duration:.2f} seconds",
        flush=True,
    )

    return duration


def main():
    started_at = datetime.now(timezone.utc)

    print("\n🚲 VÉLIB' LIVE PIPELINE")
    print("=" * 55)
    print("Started at:", started_at.isoformat())

    durations = {}

    # Generate one poll ID for the entire pipeline run.
    bucket_minute = (started_at.minute // 5) * 5

    poll_bucket = started_at.replace(
        minute=bucket_minute,
        second=0,
        microsecond=0,
    )

    poll_id = poll_bucket.strftime("%Y-%m-%dT%H:%M:%SZ")

    collector_env = dict(__import__("os").environ)
    collector_env["VELIB_POLL_ID"] = poll_id

    durations["collector"] = run_stage(
        "Collector",
        [sys.executable, "-m", "collector.collector"],
        env=collector_env,
    )

    # Use the exact same poll bucket passed to the collector.
    snapshot_name = (
        f"velib_poll_{poll_bucket.strftime('%Y%m%dT%H%M%SZ')}.json"
    )

    latest_snapshot = (
        PROJECT_ROOT / "storage/raw" / snapshot_name
    )

    if not latest_snapshot.is_file():
        raise RuntimeError(
            "Collector did not produce the expected snapshot: "
            f"{latest_snapshot}"
        )

    print("\n📸 Snapshot:", latest_snapshot.name, flush=True)

    durations["producer"] = run_stage(
        "Kafka Producer",
        [
            sys.executable,
            "-m",
            "producer.producer",
            str(latest_snapshot),
        ],
    )

    durations["consumer"] = run_stage(
        "Kafka Consumer",
        [sys.executable, "-m", "consumer.consumer"],
    )

    finished_at = datetime.now(timezone.utc)

    print("\n" + "=" * 55)
    print("📊 PIPELINE RUN SUMMARY")
    print("=" * 55)

    for stage, duration in durations.items():
        print(f"{stage}: {duration:.2f} seconds")

    print("Started:", started_at.isoformat())
    print("Finished:", finished_at.isoformat())
    print(
        "Total duration:",
        f"{sum(durations.values()):.2f} seconds",
    )

    print("\n✅ PIPELINE RUN COMPLETE")


if __name__ == "__main__":
    main()
