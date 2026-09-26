# What this repository contains, and what it only fetches

The harness — everything under `harness/`, `sib/` and `results/` — is MIT, in `LICENSE`.

**No competitor's source is vendored here.** `harness/build.sh` fetches each one at a pinned commit
into `build/`, which is gitignored, and compiles it on the machine that will run it. That is not
tidiness: the structures this suite measures carry licences that differ from each other's and from
this harness's, and several are copyleft. A machine that runs `sib build` assembles those sources
for itself and distributes nothing.

## The licences, read from each repository on 2026-09-21 and 2026-09-26

| what | repository | licence, as its own file states it |
|---|---|---|
| MARISA | [`s-yata/marisa-trie`](https://github.com/s-yata/marisa-trie) | BSD-2-Clause **OR** LGPL-2.1-or-later (`COPYING.md`) |
| XCDAT | [`kampersanda/xcdat`](https://github.com/kampersanda/xcdat) | MIT |
| C² benchmark driver | [`alexztc/C2`](https://github.com/alexztc/C2) | MIT — the repository's own file; the PDT and FST code it carries comes from the next two rows |
| PDT, C²'s `baseline_pdt/` | [`ot/path_decomposed_tries`](https://github.com/ot/path_decomposed_tries), whose `tries/path_decomposed_trie.hpp` C² carries with only its include paths changed | **Microsoft Research License Agreement, non-commercial use only** (`LICENSE` upstream; the copy in C² carries no notice) |
| FST, C²'s `baseline_fst/` | SuRF, [`efficient/SuRF`](https://github.com/efficient/SuRF), with modifications by Shunsuke Kanda | Apache-2.0 (`LICENSE` upstream) |
| CoCo-trie | [`aboffa/CoCo-trie`](https://github.com/aboffa/CoCo-trie) | **GPL-3.0** |
| sdsl-lite | [`vgteam/sdsl-lite`](https://github.com/vgteam/sdsl-lite) | **GPL-3.0-or-later** (`COPYING`) |
| ds2i, with the `succinct` library PDT builds on | [`aboffa/ds2i`](https://github.com/aboffa/ds2i) | Apache-2.0 (`LICENSE`, and `succinct/LICENSE`) |
| sux | [`vigna/sux`](https://github.com/vigna/sux) | **GPL-3** with a runtime exception (`COPYING3`, `COPYING.RUNTIME`) |
| FSST | [`cwida/fsst`](https://github.com/cwida/fsst) | MIT |
| ctriepp | [`ofek.gila1/ctriepp`](https://gitlab.com/ofek.gila1/ctriepp) | MIT (`LICENSE.txt`) |
| lexindex | [`ilgrad/lexindex`](https://github.com/ilgrad/lexindex) | MIT (fetched from crates.io like any dependency) |

**PDT is the one entrant whose licence restricts use, not only redistribution.** The Microsoft
Research License Agreement allows non-commercial use — its own examples are teaching, academic
research, public demonstrations and personal experimentation — and publishing results obtained with
the software; it forbids commercial use of the software and of any derivative work. Whether a run of
yours is commercial is for you to judge before `sib build` compiles it.

GitHub's API reports `NOASSERTION` for seven of these, which means its classifier did not recognise
the file, **not** that the project is unlicensed. The table above is what those files actually say.
Verify any of them yourself before you rely on it; a licence is not a benchmark result and this
table is not authoritative.

## Why there is a `Containerfile` and no published image

`sib build` compiles GPL-3 code (CoCo-trie, sdsl-lite, sux) into one `benchmark` binary. Publishing
a prebuilt image of that binary would be *distributing* it, which the GPL permits on terms —
offering corresponding source, licensing the whole under the GPL — that a benchmark harness has no
business taking on. Building the image locally is not distribution, so the `Containerfile` ships
and the image does not.

```bash
podman build -t sib .          # or docker build
podman run --rm -v "$PWD:/w" -w /w sib sib build
```

## The corpora

`sib/corpora.py` downloads from Wikimedia dumps, tranco-list.eu, pypi.org, snapshot.debian.org and
static.rust-lang.org, and records a SHA-256 for every file in `sib/corpora.json`. Nothing it
downloads is redistributed here — 4.6 GB of keys has no place in a git history, and the manifest is
what makes a run checkable without one. The data carry their own terms; the Wikipedia titles are
CC BY-SA, Tranco's list is CC BY, and the Debian archive is whatever its packages are. Read them
before republishing a corpus rather than the numbers measured on one.
