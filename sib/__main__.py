"""The front door: build the competitors, fetch the corpora, run a campaign, read the tables.

    sib build                      # fetch and compile every competitor at its pinned commit
    sib corpora build              # fetch and derive the thirteen corpora (4.6 GB, once)
    sib corpora verify             # re-hash what is on disk against the manifest
    sib run                        # the thirteen corpora at a million keys
    sib run --scale 10m            # the six with a ten-million-key file
    sib run --scale full           # English titles and URLs whole, 19.2 M keys each
    sib run --scale 100m           # the four generated corpora at 100 M, four structures
    sib run --keys catalog.txt     # your own keys, every structure, one table
    sib marisa-floor               # MARISA's size at every num_tries and the tiny cache, at 1 M
    sib marisa-floor --scale 10m   # the same over the six ten-million-key files
    sib table results/<...>.json   # the markdown the README quotes
    sib chart results/<...>.json   # the figure

Each subcommand is a thin wrapper over the script that does the work -- `harness/build.sh`,
`sib/corpora.py`, `harness/run.sh`, `harness/marisa_floor.py`, `harness/tables.py`, `sib/chart.py`
-- so that reading any one of them tells you the whole truth about what it did. Nothing here hides
a flag.

`--keys` is the one subcommand that is not a wrapper, and the one most people want. It stages your
file as a corpus and runs the same protocol over it, so the answer is about *your* keys: a
catalogue's bytes per key is a property of the catalogue at least as much as of the structure, and
no benchmark anyone else publishes can tell you yours.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _run(argv: list[str], env: dict[str, str] | None = None) -> int:
    """Run a harness script from the repository root, inheriting stdout and stderr."""
    print(f"$ {' '.join(argv)}", file=sys.stderr)
    return subprocess.run(argv, cwd=ROOT, env={**os.environ, **(env or {})}, check=False).returncode


def _corpora_dir() -> Path:
    return Path(os.environ.get("SIB_CORPORA", ROOT / "corpora"))


def cmd_build(args: argparse.Namespace) -> int:
    return _run(["bash", "harness/build.sh"], {"JOBS": str(args.jobs)} if args.jobs else None)


def cmd_corpora(args: argparse.Namespace) -> int:
    return _run([sys.executable, "sib/corpora.py", args.action, *args.names])


def cmd_run(args: argparse.Namespace) -> int:
    argv = ["bash", "harness/run.sh", "--rounds", str(args.rounds)]
    env: dict[str, str] = {}

    if args.keys:
        source = Path(args.keys).expanduser().resolve()
        if not source.is_file():
            print(f"no such key file: {source}", file=sys.stderr)
            return 2
        stem = source.stem or "keys"
        staged = _corpora_dir() / f"{stem}.txt"
        staged.parent.mkdir(parents=True, exist_ok=True)
        # Copied, not linked: the campaign reads it once per structure per round and a link across
        # filesystems would make the first read of each process pay for someone else's disk.
        if not staged.exists() or not staged.samefile(source):
            shutil.copyfile(source, staged)
        keys = sum(1 for _ in staged.open("rb"))
        print(f"staged {source} as {staged} ({keys:,} lines)", file=sys.stderr)
        argv.append(stem)
        # Your keys are not this repository's commit, and your laptop is not a quiet machine. Both
        # gates come off, and `sib table` prints the warning that goes with that.
        argv.append("--allow-dirty")
        env |= {
            "SIB_LOAD_CEILING": "1000",
            "SIB_QUIET_CPUS": "1000",
            "SIB_SETTLE_SECONDS": "1",
            "SIB_SWAP_CEILING_MIB": "999999",
            "SIB_FREE_GIB": "0",
        }
        print(
            "\nNOTE: the quiet-machine gates are off for a --keys run. Sizes are\n"
            "      deterministic and stand anywhere; the nanoseconds are this machine\n"
            "      under whatever else it is doing, and are not comparable to any\n"
            "      published table.\n",
            file=sys.stderr,
        )
    else:
        argv += ["--scale", args.scale, *args.names]
        if args.allow_dirty:
            argv.append("--allow-dirty")
    return _run(argv, env)


def cmd_marisa_floor(args: argparse.Namespace) -> int:
    argv = [sys.executable, "harness/marisa_floor.py", "--scale", args.scale]
    if args.jobs:
        argv += ["--jobs", str(args.jobs)]
    if args.allow_dirty:
        argv.append("--allow-dirty")
    return _run(argv)


def cmd_table(args: argparse.Namespace) -> int:
    return _run([sys.executable, "harness/tables.py", args.artifact])


def cmd_chart(args: argparse.Namespace) -> int:
    return _run([sys.executable, "sib/chart.py", args.artifact])


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sib",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="fetch and compile every competitor at its pinned commit")
    build.add_argument("--jobs", type=int, default=0, help="parallel compile jobs")
    build.set_defaults(func=cmd_build)

    corpora = sub.add_parser("corpora", help="fetch, derive and verify the corpus set")
    corpora.add_argument("action", choices=("build", "verify", "status"))
    corpora.add_argument("names", nargs="*", default=[], help="default: every corpus")
    corpora.set_defaults(func=cmd_corpora)

    run = sub.add_parser("run", help="run a campaign")
    run.add_argument("--scale", choices=("1m", "10m", "full", "100m"), default="1m")
    run.add_argument("--rounds", type=int, default=3, help="processes per structure and corpus")
    run.add_argument("--keys", metavar="FILE", help="your own keys, one per line")
    run.add_argument("--allow-dirty", action="store_true")
    run.add_argument("names", nargs="*", default=[], help="named corpus stems only")
    run.set_defaults(func=cmd_run)

    floor = sub.add_parser("marisa-floor", help="MARISA's size at every num_tries and cache")
    floor.add_argument("--scale", choices=("1m", "10m", "full"), default="1m")
    floor.add_argument("--jobs", type=int, default=0, help="corpora built at once (default: CPUs)")
    floor.add_argument("--allow-dirty", action="store_true")
    floor.set_defaults(func=cmd_marisa_floor)

    table = sub.add_parser("table", help="the markdown for a campaign artifact")
    table.add_argument("artifact")
    table.set_defaults(func=cmd_table)

    chart = sub.add_parser("chart", help="the figure for a campaign artifact")
    chart.add_argument("artifact")
    chart.set_defaults(func=cmd_chart)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
