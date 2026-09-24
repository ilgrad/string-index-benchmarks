# string-index-benchmarks

One protocol, thirteen corpora, every compressed string dictionary anyone will let you build.

A *string dictionary* maps a set of strings to dense integer ids and back. Every published one comes
with a table, and no two tables are comparable: different corpora, different machines, different
definitions of "size", different ideas of what counts as a lookup. This repository is one harness
that builds them all from source at pinned commits, measures them the same way on the same keys, and
writes an artifact naming the machine, the commits and the corpus hashes behind every number.

It exists because a benchmark you cannot re-run is a claim, not a measurement.

**What it measures.** MARISA, XCDAT, CoCo-trie, PDT, FST, ART, the C² framework's four compressed
variants, and lexindex — each at its own best configuration, never at a default chosen to flatter
someone. Serialised bytes per key, single-key lookup latency, build time and peak RSS.

**Who wrote it.** The author of [lexindex](https://github.com/ilgrad/lexindex), which is one of the
competitors here. That is a conflict of interest and the reason the protocol below is as explicit as
it is: lexindex is fetched from crates.io at a pinned version like every other entrant, this
repository has no dependency on a lexindex checkout, and the one corpus where a trie is smaller is
in the headline table rather than a footnote. Re-run it and disagree; see the last section.

## Quickstart

```bash
git clone https://github.com/ilgrad/string-index-benchmarks && cd string-index-benchmarks
sib build                      # fetch and compile every competitor at its pinned commit
sib corpora build              # fetch and derive the thirteen corpora (4.6 GB, once)
sib run                        # the campaign at a million keys
sib table results/<latest>.json
```

`sib` needs Python 3.11+ and nothing else; `sib build` needs a C++20 compiler, CMake, Boost and a
Rust toolchain. If you would rather not install those, the `Containerfile` has them:

```bash
podman build -t sib . && podman run --rm -v "$PWD:/w" -w /w sib sib build
```

### Your keys, not ours

```bash
sib run --keys my_catalog.txt
```

This is the subcommand most people actually want. Bytes per key is a property of the *keys* at least
as much as of the structure — the spread across the thirteen corpora below is 0.5 to 21 bytes for
the same structures — so the only table that answers "what would this cost on my data" is the one
run on your data. It stages your file as a corpus, runs the same protocol, and prints the same
columns. The quiet-machine gates come off for such a run and the output says so: the sizes are
deterministic and stand anywhere, the nanoseconds are your laptop under whatever else it is doing.

## The corpora

Thirteen, of four kinds, defined in `sib/corpora.py` and hashed in `sib/corpora.json`:

| kind | corpora |
|---|---|
| fetched from a pinned URL | `titles-en`, `titles-ru`, `titles-zh` (Wikipedia dumps), `domains` (Tranco), `pypi`, `paths` (a Debian archive's file list), `idents` (every identifier in the `rustc` source release) |
| derived from a fetched one | `urls` — the article titles under Wikipedia's own prefix and escaping |
| generated from a fixed seed | `uuid`, `numeric`, `opaque`, `dna` |
| read off the machine | `words` — `/usr/share/dict/words`, tagged `host`, the only one that is |

Eleven of thirteen reproduce byte-for-byte anywhere and at any time; rebuilding them nine days
apart reproduced every SHA-256. The other two carry a tag that says why they do not. `words` is
`host` — it is read off the machine, and the manifest records which one. `pypi` is `dated` — the
simple index is live and publishes no snapshot, so a rebuild picks up whatever was registered since
(889 864 names on 2026-09-12, 895 600 on 2026-09-21), and the manifest's `built` date is which index
a file is. Sizes are nested — the 1 M file is a prefix of
the 10 M one — so a difference between two scales is scale and never composition. Every file is
UTF-8, one key per line, deduplicated, and **shuffled with a fixed seed**: a sorted build order is
the one order an ordered index must not be handed by accident.

## Results: a million keys

Measured 2026-09-20 on an AMD Ryzen 7 5800HS (8 cores / 16 threads, Fedora 44, GCC 16.2.1, rustc
1.98.1), three processes per structure and corpus, even rounds in the reverse order. Artifact
`results/frontier-1m-2026-09-20-arz-7e42c43.json`, which names every pin and every corpus hash.
`ART` and `C-ART` are excluded from the size comparison: they count their nodes and not the keys
those nodes point into.

| corpus | keys | raw B/key | lexindex, best index | smallest other | margin | fastest lookup |
|---|---:|---:|---|---|---:|---|
| `numeric` | 1,000,000 | 5.9 | **301 B total** (StringIndex) | 0.52 (CoCo) | **+99.9 %** | XCDAT 15 55 ns |
| `dna` | 1,000,000 | 24.0 | **4.23** (Dict 1024) | 6.14 (CoCo) | **+31.1 %** | XCDAT 15 285 ns |
| `uuid` | 1,000,000 | 36.0 | **17.89** (Dict 1024) | 21.44 (PDT) | **+16.5 %** | XCDAT 15 334 ns |
| `words` | 479,823 | 9.3 | **2.51** (Dict 1024) | 2.98 (MARISA ρ=2) | **+15.6 %** | XCDAT 15 80 ns |
| `titles-ru` | 1,000,000 | 35.8 | **7.45** (Dict 1024) | 8.61 (MARISA ρ=2) | **+13.5 %** | XCDAT 15 365 ns |
| `urls` | 1,000,000 | 52.4 | **7.27** (Dict 1024) | 8.39 (MARISA ρ=2) | **+13.4 %** | XCDAT 15 364 ns |
| `titles-en` | 1,000,000 | 21.0 | **7.21** (Dict 1024) | 8.19 (MARISA ρ=2) | **+11.9 %** | XCDAT 15 239 ns |
| `pypi` | 889,864 | 13.3 | **4.02** (Dict 1024) | 4.51 (MARISA ρ=2) | **+10.9 %** | XCDAT 15 135 ns |
| `domains` | 1,000,000 | 13.8 | **4.36** (Dict 1024) | 4.87 (MARISA ρ=2) | **+10.5 %** | XCDAT 15 148 ns |
| `idents` | 1,000,000 | 17.3 | **5.07** (Dict 1024) | 5.61 (MARISA ρ=2) | **+9.8 %** | XCDAT 15 203 ns |
| `opaque` | 1,000,000 | 16.0 | **10.29** (Dict 1024) | 11.11 (CoCo) | **+7.4 %** | XCDAT 15 205 ns |
| `titles-zh` | 1,000,000 | 16.9 | **6.12** (Dict 1024) | 6.54 (MARISA ρ=2) | **+6.4 %** | XCDAT 15 199 ns |
| `paths` | 1,000,000 | 125.0 | **9.32** (Dict 1024) | 9.47 (MARISA ρ=2) | **+1.5 %** | XCDAT 15 625 ns |

Thirteen of thirteen — but read the fourth column before the sixth. lexindex ships five indexes and
this is the smallest of them on each corpus, against the smallest of eight structures on the other
side; holding one side to a single index while the other picks from eight would be a different
measurement, not a modest one. On twelve corpora that index is the front-coded `DictIndex`. On
`numeric` it is `StringIndex`, where an fst folds a dense decimal id space into **301 bytes whole**
— a real win and a degenerate corpus at once, and the total is printed rather than a rounded 0.00 so
that it reads as both. `lexindex plan` picks the index off the keys alone, which is what makes that
column something a caller gets rather than something chosen here after the fact.

**The last column is the honest caveat.** `DictIndex` at block 1024 is the smallest structure in
the table and among the slowest to look up, because a bigger block is more front-coded keys to scan.
That is the trade-off it is *for*, and it is a dial: on `words`, block 32 measures 2.85 B/key at
247 ns against MARISA ρ=2's 2.98 at 349 — smaller **and** faster than the trie — while XCDAT 15
answers in 80 ns at 7.30 B/key, 2.9× the size. Nobody dominates. Pick the corner you need and read
the full table, which `sib table` prints with every structure and every configuration in it.

A ten-million-key campaign over six of the corpora is in
`results/frontier-10m-2026-09-20-arz-7e42c43.json`, and reads the same way: `DictIndex` smallest on
five, `StringIndex` on `numeric` at 356 bytes for ten million keys.

## Results: past ten million keys

Two campaigns on 2026-09-21, same machine, toolchain and protocol, at this repository's `a6c13d0`.
`results/frontier-full-2026-09-21-arz-a6c13d0.json` runs every structure over English Wikipedia's
titles and URLs whole, 19.2 million keys each; no fetched corpus here is larger.

| corpus | keys | lexindex, best index | smallest other | margin | fastest lookup | lexindex's fastest |
|---|---:|---|---|---:|---|---|
| `urls` | 19,217,771 | **5.06** (Dict 1024) | 5.33 (MARISA ρ=2) | **+4.9 %** | XCDAT 15 824 ns | Dict 256 891 ns |
| `titles-en` | 19,217,770 | **5.02** (Dict 1024) | 5.23 (MARISA ρ=2) | **+4.1 %** | XCDAT 15 659 ns | Dict 256 769 ns |

`results/frontier-100m-2026-09-21-arz-a6c13d0.json` runs the four generated corpora at a hundred
million keys with **four structures, not twenty-five**: there every driver peaks near ten times its
ten-million figure, and the whole set would run for two days. The four are both ends of every
ten-million front — `DictIndex` at blocks 256 and 1024, `StringIndex`, and XCDAT 15, the fastest
lookup at every smaller scale — so this table says where the two ends went and nothing about the
structures that were not run.

| corpus | lexindex, smallest | XCDAT 15 | lexindex, fastest | XCDAT 15 |
|---|---|---:|---|---:|
| `numeric` | **420 B total** (StringIndex) | 7.05 | **156 ns** (StringIndex) | 408 ns |
| `dna` | **3.40** (Dict 1024) | 9.45 | 844 ns (Dict 1024) | 864 ns |
| `uuid` | **16.94** (Dict 1024) | 37.98 | 924 ns (StringIndex, 34.91) | **873 ns** |
| `opaque` | **9.46** (Dict 1024) | 19.99 | 833 ns (StringIndex, 19.58) | **546 ns** |

**The lookup gap closed from a million keys to ten million, and then stopped closing.** lexindex's
fastest index over XCDAT 15's time:

| corpus | 1 M | 10 M | 19.2 M or 100 M |
|---|---:|---:|---:|
| `titles-en` | 1.69 | 1.18 | 1.17 |
| `urls` | 1.26 | 1.07 | 1.08 |
| `uuid` | 1.36 | 1.24 | 1.06 (`DictIndex` 1.21) |
| `opaque` | 1.70 | 1.72 | 1.53 (`DictIndex` 1.59) |
| `dna` | 1.23 | **0.91** | 0.98 |
| `numeric` | 2.05 | **0.67** | **0.38** |

`dna` at a hundred million is a tie, not a win: 2 % is inside what the placement of a process's
memory alone moves a lookup on this machine, whose two DIMMs are unequal — the artifact records the
layout. `DictIndex` builds before every structure at both sizes: 3.8 and 4.0 s on the 19.2 M
corpora against ART's 3.9 and 7.2, C-ART's 5.1 and 8.3, and 12.8 s or more for everything else,
and 8–14 s at a hundred million against XCDAT 15's 23–132. CoCo-trie runs out of the 28 GB of
address space a process is allowed on both 19.2 M corpora, as it did on five of six at ten million.

## The protocol

The rules a number here had to survive:

- **One process per structure per corpus.** A structure measured after another in the same process
  inherits its allocator state and its warmed caches. Rounds alternate order (`A B B A`), so drift
  over a campaign is visible rather than attributed to whichever ran last.
- **A quiet machine, checked rather than assumed.** Each process waits for the load to fall below
  one busy CPU before it starts; `run.sh` records the load average at the start of the campaign into
  the artifact. Latency is the only thing this protects — **sizes are deterministic and need no
  quiet machine**, which is why size tables here are the load-bearing ones.
- **Probes in a shuffled order.** A probe set built with a stride is a stride, and the L2 prefetcher
  learns it: on one structure the in-order walk and the shuffled walk *reversed the ranking of two
  layouts*. Shuffled with a fixed seed, always.
- **Size is what a file costs.** Serialised bytes on disk divided by keys, not a resident-set
  reading and not a sum of a structure's internal arrays. One row holds more than its file and
  counts it: a routed `DictIndex` is the blob and the restart words `route_microblocks()` derives
  beside it at load.
- **A lookup is a lookup.** `id(key) -> u64` for a key that is present, one at a time, from a
  shuffled probe set — not a batch, not a prefix walk, not an iterator. Every probe is a member, so
  a row that cannot turn a stranger away is timed like one that can: `HashedDictIndex` closed
  answers through `id_unchecked`, which gives a stranger some id rather than none, where its
  fingerprinted rows turn away all but one stranger in `2^bits` and the tries every one.
- **Everything is pinned.** Competitors by commit in `harness/pins.sh`, lexindex by crates.io
  version in `harness/lex/Cargo.toml`, corpora by SHA-256 in `sib/corpora.json`, and every one of
  those lands in the artifact next to the numbers.
- **The artifact is the claim.** A table in this README is a rendering of a JSON file in `results/`
  that names the machine, the commit, the pins and the date. If a table and an artifact disagree,
  the artifact is right and the table is a bug.

`run.sh` refuses to run on a dirty checkout unless told `--allow-dirty`, and stamps the commit it
ran at into the filename.

## Layout

| path | what |
|---|---|
| `harness/build.sh` | fetches and compiles every competitor at its pinned commit into `build/` |
| `harness/pins.sh` | the commits, in one place |
| `harness/run.sh` | the campaign: quiet gate, rounds, ordering, artifact |
| `harness/lex/` | the lexindex entrant, depending on the published crate |
| `harness/xcdat_frontier.cpp` | the XCDAT entrant, since XCDAT ships no benchmark driver |
| `harness/tables.py` | artifact → markdown |
| `sib/corpora.py` | the corpus definitions, fetching and hashing |
| `sib/chart.py` | artifact → figure |
| `results/` | the artifacts, committed |

## Licensing

The harness is MIT. **No competitor's source is vendored** — several are GPL-3, and `sib build`
assembles them on your machine rather than this repository redistributing them. That is also why
there is a `Containerfile` and no published image. The licence of each competitor, read from its own
repository, is in [`NOTICE.md`](NOTICE.md), along with the corpora's terms.

## Disagreeing with a number

Open an issue with the artifact. Every number here names the machine, the commits and the corpus
hashes that produced it, which makes a disagreement answerable: either the protocol differs, the
corpus differs, the machine differs, or there is a bug. All four are worth knowing.
