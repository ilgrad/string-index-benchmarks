"""What a loaded index holds beside its file: lexindex against MARISA at its smallest, one scale.

    uv run --no-sync python harness/resident.py                  # the thirteen corpora at 1 M
    uv run --no-sync python harness/resident.py --scale 10m      # the six with a 10 M file
    uv run --no-sync python harness/resident.py --scale full     # English titles and URLs whole
    uv run --no-sync python harness/resident.py --allow-dirty    # tagged <sha>-dirty

Every size elsewhere in this repository is a file: the serialised blob for lexindex, `io_size()` for
MARISA's smallest. A loaded index can hold more than its file. `load_mmap` leaves a lexindex blob to
the page cache but derives lookup tables beside it on the heap; `Trie::mmap` does the same for
MARISA with almost nothing. So this counts, for each corpus, the heap each load keeps:
`build/marisa_resident` for MARISA's configurations -- the smallest by either size in the scale's
`results/marisa-floor-*` artifact, and three tries at the default cache as the control -- and
`harness/lex`'s `resident` for lexindex's `DictIndex` at blocks 32, 256 and 1024 and `StringIndex`.
Both count `malloc_usable_size` of every allocation still live after the load and a pass of
lookups. The result goes to `results/resident-<scale>-<date>-<host>-<commit>.json`, and the table
it prints is the one the README quotes.

Nothing is timed, so none of run.sh's quiet-machine gates apply and corpora run side by side. The
gates that make a number attributable do apply, and they are marisa_floor.py's, imported from it:
a clean tree, marisa at its pin, every corpus file the manifest's. A MARISA configuration that does
not rebuild to the floor artifact's size refuses the run.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from marisa_floor import BUILD, CORPORA, MARISA, ROOT, commit, default_jobs, pin

LEX = ROOT / "harness/lex"
LEX_KINDS = ("dict32", "dict256", "dict1024", "string")
LABELS = {
    "dict32": "Dict 32",
    "dict256": "Dict 256",
    "dict1024": "Dict 1024",
    "string": "StringIndex",
}
CONTROL = {"cache": "default", "tries": 3}


def run(argv: list[str]) -> tuple[str | None, str]:
    """A tool's stdout, or None and why it failed."""
    done = subprocess.run(argv, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        why = f"signal {-done.returncode}" if done.returncode < 0 else f"exit {done.returncode}"
        return None, f"{why}: {done.stderr.strip()[-500:]}"
    return done.stdout, ""


def measure(corpus: dict) -> dict:
    """One corpus: lexindex's kinds, then MARISA at the floor's configurations and the control."""
    stem, path = corpus["corpus"], str(CORPORA / f"{corpus['corpus']}.txt")
    out, why = run([str(LEX / "target/release/resident"), path, *LEX_KINDS])
    if out is None:
        return {"corpus": stem, "failure": f"resident: {why}"}
    lexindex = [
        {
            "structure": LABELS[row["kind"]],
            "blob": int(row["blob"]),
            "from_bytes_heap": int(row["from_bytes_heap"]),
            "mmap_heap": int(row["mmap_heap"]),
        }
        for row in csv.DictReader(out.splitlines())
    ]

    roles: dict[tuple[str, int], list[str]] = {}
    for role in ("smallest_io", "smallest_total"):
        at = corpus[role]
        roles.setdefault((at["cache"], at["tries"]), []).append(role)
    roles.setdefault((CONTROL["cache"], CONTROL["tries"]), []).append("default")
    out, why = run(
        [str(BUILD / "marisa_resident"), path, *(f"{cache}:{tries}" for cache, tries in roles)]
    )
    if out is None:
        return {"corpus": stem, "failure": f"marisa_resident: {why}"}
    first, *table = out.splitlines()
    keys = int(first.split()[0])
    marisa = []
    for row in csv.DictReader(table):
        at = (row["cache"], int(row["tries"]))
        marisa.append(
            {
                "roles": roles[at],
                "cache": at[0],
                "tries": at[1],
                "tries_built": int(row["tries_built"]),
                "bytes_io": int(row["bytes_io"]),
                "bytes_total": int(row["bytes_total"]),
                "mmap_heap": int(row["mmap_heap"]),
                "load_heap": int(row["load_heap"]),
            }
        )
    floor = next(m for m in marisa if "smallest_io" in m["roles"])
    if floor["bytes_io"] != corpus["smallest_io"]["bytes_io"]:
        return {
            "corpus": stem,
            "failure": f"MARISA's smallest built {floor['bytes_io']} bytes here and "
            f"{corpus['smallest_io']['bytes_io']} in the floor artifact",
        }
    return {"corpus": stem, "keys": keys, "lexindex": lexindex, "marisa": marisa}


def version(argv: list[str]) -> str:
    return subprocess.run(argv, capture_output=True, text=True, check=True).stdout.splitlines()[0]


def margin(ours: int, theirs: int) -> str:
    return f"{100 * (theirs - ours) / theirs:+.2f} %"


def table(corpora: list[dict]) -> str:
    """lexindex's smallest file against MARISA's, then each with what its mapped load keeps."""
    lines = [
        "| corpus | lexindex, smallest | its file | + `load_mmap` heap | MARISA, smallest "
        "| its file | + `mmap` heap | margin, files | margin, mapped |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for corpus in corpora:
        ours = min(corpus["lexindex"], key=lambda row: row["blob"])
        theirs = next(m for m in corpus["marisa"] if "smallest_io" in m["roles"])
        mapped_ours = ours["blob"] + ours["mmap_heap"]
        mapped_theirs = theirs["bytes_io"] + theirs["mmap_heap"]
        lines.append(
            f"| `{corpus['corpus']}` | {ours['structure']} | {ours['blob']:,} "
            f"| {ours['mmap_heap']:,} | {theirs['tries']} tries, {theirs['cache']} "
            f"| {theirs['bytes_io']:,} | {theirs['mmap_heap']:,} "
            f"| {margin(ours['blob'], theirs['bytes_io'])} "
            f"| {margin(mapped_ours, mapped_theirs)} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scale", choices=("1m", "10m", "full"), default="1m")
    parser.add_argument("--jobs", type=int, default=default_jobs(), help="corpora measured at once")
    parser.add_argument(
        "--allow-dirty", action="store_true", help="for development; tagged <sha>-dirty"
    )
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error(f"--jobs takes a positive count, not {args.jobs}")

    floors = sorted((ROOT / "results").glob(f"marisa-floor-{args.scale}-*.json"))
    if not floors:
        raise SystemExit(f"refusing: no results/marisa-floor-{args.scale}-*.json; run it first")
    floor_artifact = floors[-1]
    floor = json.loads(floor_artifact.read_text(encoding="utf-8"))

    sha = commit(args.allow_dirty)
    for binary in (BUILD / "marisa_resident", LEX / "target/release/resident"):
        if not os.access(binary, os.X_OK):
            raise SystemExit(f"refusing: {binary} is missing; run harness/build.sh")
    marisa = pin()
    for corpus in floor["corpora"]:
        if not (CORPORA / f"{corpus['corpus']}.txt").is_file():
            raise SystemExit(f"refusing: no corpus file {CORPORA}/{corpus['corpus']}.txt")
    verified = subprocess.run([sys.executable, "sib/corpora.py", "verify"], cwd=ROOT, check=False)
    if verified.returncode:
        raise SystemExit("refusing: a corpus file is not the one sib/corpora.json hashes")
    lock = (LEX / "Cargo.lock").read_text(encoding="utf-8")
    lexindex = re.search(r'name = "lexindex"\nversion = "([^"]+)"', lock)

    now = datetime.now().astimezone()
    uname = os.uname()
    name = f"resident-{args.scale}"
    environment = {
        "date": now.isoformat(timespec="seconds"),
        "host": uname.nodename,
        "commit": sha,
        "table": name,
        "kernel": f"{uname.sysname} {uname.release} {uname.machine}",
        "compiler": version(["c++", "--version"]),
        "rustc": version(["rustc", "--version"]),
        f"pin {MARISA}": marisa,
        "lexindex": lexindex[1] if lexindex else "unknown",
        "marisa configurations from": f"results/{floor_artifact.name}",
        "sizes": "blob and bytes_io are the file; from_bytes_heap, mmap_heap and load_heap are "
        "malloc_usable_size of every allocation a load keeps, after a pass of lookups",
        "quiet-machine gates": "none: sizes are deterministic",
    }

    started = time.monotonic()
    measured: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for future in as_completed(pool.submit(measure, c) for c in floor["corpora"]):
            corpus = future.result()
            measured[corpus["corpus"]] = corpus
            status = corpus.get("failure", f"{corpus.get('keys', 0):,} keys")
            print(
                f"{corpus['corpus']}: {status}, {time.monotonic() - started:.0f} s in", flush=True
            )
    failed = [corpus for corpus in measured.values() if "failure" in corpus]
    if failed:
        raise SystemExit(f"refusing to write an artifact: {len(failed)} corpora failed")

    corpora = [measured[c["corpus"]] for c in floor["corpora"]]
    out = ROOT / "results" / f"{name}-{now:%F}-{uname.nodename}-{sha}.json"
    artifact = {"table": name, "environment": environment, "corpora": corpora}
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {out}\n")
    print(table(corpora))
    return 0


if __name__ == "__main__":
    sys.exit(main())
