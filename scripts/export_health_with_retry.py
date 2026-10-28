import subprocess
import sys
import time


MAX_ATTEMPTS = 12
RETRY_DELAY_SECONDS = 5


def main():
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(
            f"Health export attempt {attempt}/{MAX_ATTEMPTS}",
            flush=True,
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "scripts.export_health_json",
            ],
            check=False,
        )

        if result.returncode == 0:
            print("Health export succeeded.", flush=True)
            return 0

        if attempt == MAX_ATTEMPTS:
            print(
                "Health export failed after all retry attempts.",
                file=sys.stderr,
            )
            return result.returncode

        print(
            f"Health export failed; retrying in "
            f"{RETRY_DELAY_SECONDS} seconds...",
            flush=True,
        )

        time.sleep(RETRY_DELAY_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
