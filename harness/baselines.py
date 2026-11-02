"""Front-coded string dictionaries the campaign does not run, sized over one campaign scale.

    uv run --no-sync python harness/baselines.py                  # the thirteen corpora at 1 M
    uv run --no-sync python harness/baselines.py --scale 10m      # the six with a 10 M file
    uv run --no-sync python harness/baselines.py --scale full     # English titles and URLs whole
    uv run --no-sync python harness/baselines.py --allow-dirty    # tagged <sha>-dirty

Plain front coding is the yardstick every compressed string dictionary is measured from, and the
campaign has no row of it. `harness/baselines` builds two from crates.io over one corpus file --
sux's rear-coded list at block ratios 16, 64 and 256, and fcsd's front-coded set at bucket sizes 8,
64 and 256 -- checks that each answers every key both ways, and prints their sizes. At 1 M, two C++
drivers beside it do the same for libCSD's dictionaries (`libcsd_baselines`) and RearCodedArray
(`rca_baselines`), both from `build/` at their pins. They do not run at 10 M or at the full files:
libCSD's Re-Pair has not been tried at those scales. This runs them over a scale's corpora, writes
what they printed into `results/baselines-<scale>-<date>-<host>-<commit>.log` and what it parses to
into the `.json` of the same name.

Nothing is timed, so, as with the MARISA floor, no quiet-machine gate applies and the corpora run
side by side. The gates that make a number attributable do apply: a clean tree, the binary built
from the committed lockfile, and every corpus file the manifest's.
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
from pathlib import Path

from marisa_floor import BUILD, CORPORA, COUNTS, ROOT, commit, default_jobs, pin, stems

CRATE = ROOT / "harness/baselines"
BINARY = CRATE / "target/release/baselines"
# The scale they run at, and the pin behind each.
CPP_DRIVERS_SCALE = "1m"
CPP_DRIVERS = {BUILD / "libcsd_baselines": "libcsd", BUILD / "rca_baselines": "rca"}


def versions() -> dict[str, str]:
    """The version of each measured crate in the committed lockfile, which `build.sh` builds by."""
    lock = tomllib.loads((CRATE / "Cargo.lock").read_text(encoding="utf-8"))
    found = {p["name"]: p["version"] for p in lock["package"] if p["name"] in ("sux", "fcsd")}
    if set(found) != {"sux", "fcsd"}:
        raise SystemExit("refusing: harness/baselines/Cargo.lock names neither sux nor fcsd")
    return found


def configuration(row: dict[str, str], keys: int) -> dict:
    parsed = {
        "structure": row["structure"],
        "parameter": row["parameter"],
        "bytes": int(row["bytes"]),
        "bytes_per_key": round(int(row["bytes"]) / keys, 4),
    }
    if "rank_wrong" in row:
        parsed["rank_wrong"] = int(row["rank_wrong"])
    return parsed


def measure(stem: str, binaries: list[Path]) -> dict:
    """One corpus: every configuration the binaries built, and the smallest."""
    configurations: list[dict] = []
    output: list[str] = []
    seen: set[tuple[int, int]] = set()
    for binary in binaries:
        done = subprocess.run(
            [str(binary), str(CORPORA / f"{stem}.txt")], capture_output=True, text=True, check=False
        )
        if done.returncode != 0:
            why = f"signal {-done.returncode}" if done.returncode < 0 else f"exit {done.returncode}"
            return {"corpus": stem, "failure": f"{binary.name}, {why}: {done.stderr.strip()}"}
        output += [f"--- {binary.name} {stem}", done.stdout.rstrip("\n")]
        first, *table = done.stdout.splitlines()
        counts = COUNTS.match(first)
        if counts is None:
            return {"corpus": stem, "failure": f"{binary.name}: no key count in {first!r}"}
        keys, raw = int(counts["keys"]), int(counts["raw"])
        seen.add((keys, raw))
        configurations += [configuration(row, keys) for row in csv.DictReader(table)]
    if len(seen) != 1:
        return {"corpus": stem, "failure": f"the binaries read different keys: {sorted(seen)}"}
    return {
        "output": output,
        "corpus": stem,
        "keys": keys,
        "raw_bytes": raw,
        "raw_bytes_per_key": round(raw / keys, 3),
        "configurations": configurations,
        "smallest": min(configurations, key=lambda c: c["bytes"]),
    }


def progress(corpus: dict, seconds: float) -> str:
    if "failure" in corpus:
        return f"{corpus['corpus']}: {corpus['failure']}"
    best = corpus["smallest"]
    return (
        f"{corpus['corpus']}: {corpus['keys']:,} keys, smallest {best['bytes_per_key']:.4f} B/key "
        f"({best['structure']}, {best['parameter']}), {seconds:.0f} s in"
    )


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
    drivers = CPP_DRIVERS if args.scale == CPP_DRIVERS_SCALE else {}
    for driver in drivers:
        if not os.access(driver, os.X_OK):
            raise SystemExit(f"refusing: {driver} is missing; run harness/build.sh")
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
    table = f"baselines-{args.scale}"
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
        "crate sux": f"{crates['sux']} (crates.io)",
        "crate fcsd": f"{crates['fcsd']} (crates.io)",
        **{f"pin {name}": pin(name) for name in drivers.values()},
        "sizes": "fcsd: size_in_bytes(), what serialize_into writes; sux: mem_size, its arrays "
        "and fields without a file's framing; libCSD: the file its save() writes; RearCodedArray: "
        "size_in_bytes(), its arrays and object, for it writes no file; bytes_per_key is bytes "
        "over keys",
        "quiet-machine gates": "none: sizes are deterministic",
    }

    started = time.monotonic()
    measured: dict[str, dict] = {}
    binaries = [BINARY, *drivers]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for future in as_completed(pool.submit(measure, stem, binaries) for stem in names):
            corpus = future.result()
            measured[corpus["corpus"]] = corpus
            print(progress(corpus, time.monotonic() - started), flush=True)
    failed = [corpus for corpus in measured.values() if "failure" in corpus]
    if failed:
        # A structure that could not be built, or that lost a key, is a broken run, not a result.
        raise SystemExit(f"refusing to write an artifact: {len(failed)} corpora failed")

    out = ROOT / "results" / f"{table}-{now:%F}-{uname.nodename}-{sha}.json"
    log = [f"{key}: {value}" for key, value in environment.items()]
    for stem in names:
        log += measured[stem].pop("output")
    out.with_suffix(".log").write_text("\n".join(log) + "\n", encoding="utf-8")
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
