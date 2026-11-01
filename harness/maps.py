"""Static maps that do not store their keys, sized over one campaign scale.

    uv run --no-sync python harness/maps.py                  # the thirteen corpora at 1 M
    uv run --no-sync python harness/maps.py --scale 10m      # the six with a 10 M file
    uv run --no-sync python harness/maps.py --scale full     # English titles and URLs whole
    uv run --no-sync python harness/maps.py --allow-dirty    # tagged <sha>-dirty

`harness/maps` builds, from crates.io, constmap's `ConstMap` and `VerifiedConstMap` -- binary
fuse maps from a string to a 64-bit value, the second with a 64-bit check that rejects a non-key --
beside lexindex's `ClosedHashIndex`, its `CompactHashIndex` at 8, 16, 32 and 64 fingerprint bits,
and its `PerfectHashIndex`, which stores the keys. It checks that each answers every key, counts
the strings that are not keys each structure that can reject one accepts, and prints their sizes.
This runs it over a scale's corpora and writes what it printed into
`results/maps-<scale>-<date>-<host>-<commit>.json`.

None of these structures answers id to key except `PerfectHashIndex`, and none but it is exact on
a string that is not a key, so no row here is a dictionary in the campaign's sense and there is no
"smallest": read each row with the guarantee its `structure` and `parameter` name.

Nothing is timed, so no quiet-machine gate applies and the corpora run side by side. The gates
that make a number attributable do apply: a clean tree, the binary built from the committed
lockfile, and every corpus file the manifest's.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from marisa_floor import CORPORA, COUNTS, ROOT, commit, default_jobs, stems

CRATE = ROOT / "harness/maps"
BINARY = CRATE / "target/release/maps"
CRATES = ("constmap", "lexindex")


def versions() -> dict[str, str]:
    """The version of each measured crate in the committed lockfile, which `build.sh` builds by."""
    lock = tomllib.loads((CRATE / "Cargo.lock").read_text(encoding="utf-8"))
    found = {p["name"]: p["version"] for p in lock["package"] if p["name"] in CRATES}
    if set(found) != set(CRATES):
        raise SystemExit(f"refusing: harness/maps/Cargo.lock does not name all of {CRATES}")
    return found


def measure(stem: str) -> dict:
    """One corpus: every configuration the binary built."""
    done = subprocess.run(
        [str(BINARY), str(CORPORA / f"{stem}.txt")], capture_output=True, text=True, check=False
    )
    if done.returncode != 0:
        why = f"signal {-done.returncode}" if done.returncode < 0 else f"exit {done.returncode}"
        return {"corpus": stem, "failure": f"{why}: {done.stderr.strip()}"}
    first, *table = done.stdout.splitlines()
    counts = COUNTS.match(first)
    if counts is None:
        return {"corpus": stem, "failure": f"no key count in {first!r}"}
    keys, raw = int(counts["keys"]), int(counts["raw"])
    configurations = [
        {
            "structure": row["structure"],
            "parameter": row["parameter"],
            "bytes": int(row["bytes"]),
            "bytes_per_key": round(int(row["bytes"]) / keys, 4),
            # Of `keys` strings that are not keys; None where the structure cannot reject one.
            "absent_accepted": int(row["absent_accepted"]) if row["absent_accepted"] else None,
        }
        for row in csv.DictReader(table)
    ]
    return {
        "corpus": stem,
        "keys": keys,
        "raw_bytes": raw,
        "raw_bytes_per_key": round(raw / keys, 3),
        "configurations": configurations,
    }


def progress(corpus: dict, seconds: float) -> str:
    if "failure" in corpus:
        return f"{corpus['corpus']}: {corpus['failure']}"
    sizes = ", ".join(
        f"{c['structure'].split()[-1]} {c['parameter'] or '-'} {c['bytes_per_key']:.3f}"
        for c in corpus["configurations"]
    )
    return f"{corpus['corpus']}: {corpus['keys']:,} keys, B/key: {sizes}; {seconds:.0f} s in"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scale", choices=("1m", "10m", "full"), default="1m")
    parser.add_argument(
        "--jobs",
        type=int,
        default=default_jobs(),
        help="corpora built at once (default: a CPU each, as memory allows)",
    )
    parser.add_argument(
        "--allow-dirty", action="store_true", help="for development; tagged <sha>-dirty"
    )
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error(f"--jobs takes a positive count, not {args.jobs}")

    names = stems(args.scale)
    sha = commit(args.allow_dirty)
    if not os.access(BINARY, os.X_OK):
        raise SystemExit(f"refusing: {BINARY} is missing; run harness/build.sh")
    crates = versions()
    for stem in names:
        if not (CORPORA / f"{stem}.txt").is_file():
            raise SystemExit(f"refusing: no corpus file {CORPORA}/{stem}.txt; see sib/corpora.py")
    verified = subprocess.run([sys.executable, "sib/corpora.py", "verify"], cwd=ROOT, check=False)
    if verified.returncode:
        raise SystemExit("refusing: a corpus file is not the one sib/corpora.json hashes")
    print(
        "\nNOTE: sizes only. A size is deterministic, so none of the campaign's quiet-machine\n"
        "      gates apply, and the corpora are built side by side.\n",
        file=sys.stderr,
    )

    now = datetime.now().astimezone()
    uname = os.uname()
    table = f"maps-{args.scale}"
    rustc = subprocess.run(
        ["rustc", "--version"], capture_output=True, text=True, check=True
    ).stdout.strip()
    environment = {
        "date": now.isoformat(timespec="seconds"),
        "host": uname.nodename,
        "commit": sha,
        "table": table,
        "kernel": f"{uname.sysname} {uname.release} {uname.machine}",
        "compiler": rustc,
        **{f"crate {name}": f"{crates[name]} (crates.io)" for name in CRATES},
        "sizes": "a file's bytes: constmap's write_to, lexindex's serialized_len(); "
        "bytes_per_key is bytes over keys",
        "absent_accepted": "of as many strings that are not keys as there are keys, each a key "
        "with a byte appended, how many the structure accepts; null where it cannot reject one",
        "quiet-machine gates": "none: sizes are deterministic",
    }

    started = time.monotonic()
    measured: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for future in as_completed(pool.submit(measure, stem) for stem in names):
            corpus = future.result()
            measured[corpus["corpus"]] = corpus
            print(progress(corpus, time.monotonic() - started), flush=True)
    failed = [corpus for corpus in measured.values() if "failure" in corpus]
    if failed:
        # A structure that could not be built, or that lost a key, is a broken run, not a result.
        raise SystemExit(f"refusing to write an artifact: {len(failed)} corpora failed")

    out = ROOT / "results" / f"{table}-{now:%F}-{uname.nodename}-{sha}.json"
    artifact = {
        "table": table,
        "environment": environment,
        "corpora": [measured[stem] for stem in names],
    }
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
