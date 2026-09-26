"""MARISA's size at every configuration that could make it smaller, over one campaign scale.

    uv run --no-sync python harness/marisa_floor.py                  # the thirteen corpora at 1 M
    uv run --no-sync python harness/marisa_floor.py --scale 10m      # the six with a 10 M file
    uv run --no-sync python harness/marisa_floor.py --scale full     # English titles and URLs whole
    uv run --no-sync python harness/marisa_floor.py --jobs 2         # two corpora at a time
    uv run --no-sync python harness/marisa_floor.py --allow-dirty    # tagged <sha>-dirty

The campaign builds MARISA as the C² benchmark does, at 1, 2 and 3 tries and the default cache, and
that is not marisa's smallest trie: the tiny cache is smaller on every corpus, and most take more
tries than three before they stop getting smaller. A size table that holds every structure at its
best has to measure where marisa's best is, from the marisa it pins. `build/marisa_floor` builds the
grid over one corpus file -- 1 to 32 tries at the tiny cache, and the campaign's three as the
control -- and this runs it over a scale's corpora and writes what it printed into
`results/marisa-floor-<scale>-<date>-<host>-<commit>.json`.

Two sizes a configuration, because they do not always pick the same one. `bytes_io` is `io_size()`,
what `save()` writes: a size here is what a file costs, so it is the one `bytes_per_key` divides.
`bytes_total` is `total_size()`, the trie's arrays without the file's framing, which is what C²'s
`space_cost()` counts and so what the campaign's MARISA rows are; the control rows are checked by
it. Each corpus names its smallest configuration under both.

Nothing is timed, so none of run.sh's quiet-machine gates apply and the corpora run side by side: a
size is deterministic and stands on a busy machine. The gates that make a number attributable do
apply -- a clean tree, marisa at its pin, every corpus file the manifest's. The files are the ones
run.sh measures at the same scale, read from its own `case`, so the two cannot drift apart.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = Path(os.environ.get("SIB_BUILD", ROOT / "build"))
CORPORA = Path(os.environ.get("SIB_CORPORA", ROOT / "corpora"))
MARISA = "c2/baseline_marisa/marisa"
COUNTS = re.compile(r"^(?P<keys>\d+) keys, (?P<raw>\d+) raw bytes$")
# A build over ten or 19.2 million keys peaks near 3 GB, so a job is given 4 GiB.
JOB_GIB = 4


def git(*argv: str, at: Path = ROOT) -> str:
    """A git command's output, or nothing where it fails -- as it does in a pin never fetched."""
    done = subprocess.run(
        ["git", "-C", str(at), *argv], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() if done.returncode == 0 else ""


def stems(scale: str) -> list[str]:
    """The corpus files run.sh measures at `scale`, read from its `case` arm for that scale."""
    arm = re.search(
        rf"^\s*{scale}\)\n\s*stems=\((?P<stems>[^)]*)\)",
        (ROOT / "harness/run.sh").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if arm is None:
        raise SystemExit(f"harness/run.sh has no `{scale})` arm with a stems list")
    return arm["stems"].split()


def commit(allow_dirty: bool) -> str:
    """The commit the artifact is named after, as run.sh names its own."""
    sha = git("rev-parse", "--short", "HEAD")
    if git("status", "--porcelain", "--untracked-files=no"):
        if not allow_dirty:
            raise SystemExit(
                "refusing: the working tree has uncommitted changes, so the result would not be\n"
                "attributable to the commit it is named after. Commit, stash, or --allow-dirty."
            )
        sha += "-dirty"
    return sha


def pin() -> str:
    """marisa's pin as run.sh's header writes it, once the checkout is shown to be at it."""
    line = re.search(
        rf'^\s*"{MARISA} (?P<url>\S+) (?P<commit>[0-9a-f]{{40}})"$',
        (ROOT / "harness/pins.sh").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    if line is None:
        raise SystemExit(f"harness/pins.sh does not pin {MARISA}")
    at = git("rev-parse", "HEAD", at=BUILD / MARISA) or "none"
    if at != line["commit"]:
        raise SystemExit(
            f"refusing: {MARISA} is at {at}, not the pinned {line['commit']}; run harness/build.sh"
        )
    status = git("status", "--porcelain", "--untracked-files=no", at=BUILD / MARISA)
    changed = ",".join(entry.split()[-1] for entry in status.splitlines())
    return f"{line['commit'][:12]} {line['url']}" + (f" (modified: {changed})" if changed else "")


def measure(binary: Path, stem: str) -> dict:
    """One corpus: every configuration marisa_floor built, and the smallest under each size."""
    done = subprocess.run(
        [str(binary), str(CORPORA / f"{stem}.txt")], capture_output=True, text=True, check=False
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
            "cache": row["cache"],
            "tries": int(row["tries"]),
            "tries_built": int(row["tries_built"]),
            "bytes_io": int(row["bytes_io"]),
            "bytes_total": int(row["bytes_total"]),
            "bytes_per_key": round(int(row["bytes_io"]) / keys, 4),
        }
        for row in csv.DictReader(table)
    ]
    # `min` keeps the first of equal sizes -- the control before the grid, fewer tries before
    # more -- and ties are real: past the depth where a corpus's tails run out, marisa builds the
    # same trie however many tries it is asked for, which `tries_built` shows.
    return {
        "corpus": stem,
        "keys": keys,
        "raw_bytes": raw,
        "raw_bytes_per_key": round(raw / keys, 3),
        "configurations": configurations,
        "smallest_io": min(configurations, key=lambda c: c["bytes_io"]),
        "smallest_total": min(configurations, key=lambda c: c["bytes_total"]),
    }


def default_jobs() -> int:
    """A corpus a CPU, as many as the available memory holds: a size run that swaps takes the
    afternoon, and one the OOM killer ends writes no artifact."""
    meminfo = Path("/proc/meminfo")
    available = meminfo.is_file() and re.search(
        r"^MemAvailable:\s+(\d+) kB$", meminfo.read_text(encoding="utf-8"), re.MULTILINE
    )
    if not available:
        return 1
    return max(1, min(os.cpu_count() or 1, int(available[1]) // (JOB_GIB * 1024 * 1024)))


def progress(corpus: dict, seconds: float) -> str:
    if "failure" in corpus:
        return f"{corpus['corpus']}: {corpus['failure']}"
    io, total = corpus["smallest_io"], corpus["smallest_total"]
    return (
        f"{corpus['corpus']}: {corpus['keys']:,} keys, smallest {io['bytes_per_key']:.4f} B/key "
        f"at {io['tries']} tries and the {io['cache']} cache (by total_size(), {total['tries']} "
        f"and {total['cache']}), {seconds:.0f} s in"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scale", choices=("1m", "10m", "full"), default="1m")
    parser.add_argument(
        "--jobs",
        type=int,
        default=default_jobs(),
        help=f"corpora built at once (default: a CPU each, {JOB_GIB} GiB of available memory each)",
    )
    parser.add_argument(
        "--allow-dirty", action="store_true", help="for development; tagged <sha>-dirty"
    )
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error(f"--jobs takes a positive count, not {args.jobs}")

    names = stems(args.scale)
    sha = commit(args.allow_dirty)
    binary = BUILD / "marisa_floor"
    if not os.access(binary, os.X_OK):
        raise SystemExit(f"refusing: {binary} is missing; run harness/build.sh")
    marisa = pin()
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
    table = f"marisa-floor-{args.scale}"
    compiler = subprocess.run(
        ["c++", "--version"], capture_output=True, text=True, check=True
    ).stdout.splitlines()[0]
    environment = {
        "date": now.isoformat(timespec="seconds"),
        "host": uname.nodename,
        "commit": sha,
        "table": table,
        "kernel": f"{uname.sysname} {uname.release} {uname.machine}",
        "compiler": compiler,
        f"pin {MARISA}": marisa,
        "sizes": "bytes_io is io_size(), what save() writes, and bytes_per_key is it over keys; "
        "bytes_total is total_size(), what C²'s space_cost() counts and so the campaign's MARISA",
        "quiet-machine gates": "none: sizes are deterministic",
    }

    started = time.monotonic()
    measured: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for future in as_completed(pool.submit(measure, binary, stem) for stem in names):
            corpus = future.result()
            measured[corpus["corpus"]] = corpus
            print(progress(corpus, time.monotonic() - started), flush=True)
    failed = [corpus for corpus in measured.values() if "failure" in corpus]
    if failed:
        # A size that could not be built is a broken run, not a result, so nothing is written.
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
