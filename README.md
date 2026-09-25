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

Measured 2026-09-25 on an AMD Ryzen 7 5800HS (8 cores / 16 threads, Fedora 44, GCC 16.2.1, rustc
1.98.1), lexindex 4.5.0 from crates.io, three processes per structure and corpus, even rounds in the
reverse order; other work took a median of 0.03 CPUs while the 1 208 processes ran. Artifact
`results/frontier-1m-2026-09-25-arz-cc97350.json`, which names every pin and every corpus hash.
`ART` and `C-ART` are left out of the size and lookup columns: they count their nodes and not the
keys those nodes point into.

| corpus | keys | raw B/key | lexindex, smallest | smallest other | margin | fastest other | `HashedDict` closed | lexindex's fastest exact search |
|---|---:|---:|---|---|---:|---|---:|---|
| `words` | 479,823 | 9.3 | **2.51** (Dict 1024) | 2.98 (MARISA ρ=2) | **+15.6 %** | XCDAT 15 77 ns | **14 ns** | 86 ns (DoubleArray), 1.12× |
| `dna` | 1,000,000 | 24.0 | **4.23** (Dict 1024) | 6.14 (CoCo) | **+31.1 %** | XCDAT 15 277 ns | **44 ns** | 255 ns (Dict 256 routed), **0.92×** |
| `domains` | 1,000,000 | 13.8 | **4.36** (Dict 1024) | 4.87 (MARISA ρ=2) | **+10.5 %** | XCDAT 15 148 ns | **28 ns** | 209 ns (StringIndex), 1.41× |
| `idents` | 1,000,000 | 16.6 | **4.86** (Dict 1024) | 5.35 (MARISA ρ=2) | **+9.2 %** | XCDAT 15 184 ns | **35 ns** | 249 ns (StringIndex), 1.35× |
| `numeric` | 1,000,000 | 5.9 | **301 B total** (StringIndex) | 0.52 (CoCo) | **+99.9 %** | XCDAT 15 53 ns | **14 ns** | 30 ns (DoubleArray), **0.58×** |
| `opaque` | 1,000,000 | 16.0 | **10.29** (Dict 1024) | 11.11 (CoCo) | **+7.4 %** | XCDAT 15 202 ns | **45 ns** | 279 ns (Dict 256 routed), 1.38× |
| `paths` | 1,000,000 | 58.4 | **6.51** (Dict 1024) | 6.79 (MARISA ρ=2) | **+4.1 %** | XCDAT 15 438 ns | **59 ns** | 486 ns (StringIndex), 1.11× |
| `pypi` | 895,600 | 13.3 | **4.02** (Dict 1024) | 4.51 (MARISA ρ=2) | **+10.8 %** | XCDAT 15 134 ns | **27 ns** | 213 ns (StringIndex), 1.58× |
| `titles-en` | 1,000,000 | 21.0 | **7.21** (Dict 1024) | 8.19 (MARISA ρ=2) | **+11.9 %** | XCDAT 15 238 ns | **42 ns** | 318 ns (Dict 256 routed), 1.34× |
| `titles-ru` | 1,000,000 | 35.8 | **6.70** (Dict 1024) | 8.61 (MARISA ρ=2) | **+22.2 %** | XCDAT 15 361 ns | **53 ns** | 409 ns (Dict 256 routed), 1.13× |
| `titles-zh` | 1,000,000 | 16.9 | **5.69** (Dict 1024) | 6.54 (MARISA ρ=2) | **+13.0 %** | XCDAT 15 190 ns | **34 ns** | 237 ns (DoubleArray), 1.24× |
| `urls` | 1,000,000 | 52.4 | **7.27** (Dict 1024) | 8.39 (MARISA ρ=2) | **+13.4 %** | XCDAT 15 354 ns | **58 ns** | 383 ns (Dict 256 routed), 1.08× |
| `uuid` | 1,000,000 | 36.0 | **17.89** (Dict 1024) | 21.44 (PDT) | **+16.5 %** | XCDAT 15 331 ns | **56 ns** | 351 ns (Dict 256 routed), 1.06× |

Thirteen of thirteen on size — but read the size columns before the others. lexindex enters eleven
rows: `DictIndex` at three block sizes, with and without the restart words that route a lookup,
`StringIndex`, `HashedDictIndex` at three fingerprint widths, and `DoubleArrayIndex`. The fourth
column is the smallest of them on each corpus, against the smallest of eight structures on the other
side; holding one side to a single index while the other picks from eight would be a different
measurement, not a modest one. On twelve corpora that index is the front-coded `DictIndex`. On
`numeric` it is `StringIndex`, where an fst folds a dense decimal id space into **301 bytes whole**
— a real win and a degenerate corpus at once, and the total is printed rather than a rounded 0.00 so
that it reads as both. `lexindex plan` picks the index off the keys alone, which is what makes that
column something a caller gets rather than something chosen here after the fact.

**Two lookup columns, because there are two questions.** `HashedDictIndex` — a minimal perfect hash
beside the dictionary it is built over — answers first on all thirteen, 14 to 59 ns against XCDAT
15's 53 to 438. Its closed row gives a key it was not built from some id rather than none; its
fingerprinted rows, also first on every corpus, turn away all but one stranger in 2^8 or 2^16 (see
the protocol below). The last column asks the stricter question: lexindex's fastest structure that
turns *every* stranger away, as the tries do, over XCDAT 15's time. **That column is where lexindex
still loses at a million keys.** It wins `dna` (a routed `DictIndex`, 0.92×) and `numeric`
(`DoubleArrayIndex`, 30 ns against 53) and trails on the other eleven, by 6 % on `uuid` to 58 % on
`pypi`.

**`DoubleArrayIndex` is a lexicon structure, not a general one.** A double array over characters
with a whole node in one eight-byte slot, it is lexindex's fastest exact search on `words`,
`numeric` and `titles-zh` — on `words` its three rounds read 76 to 90 ns against XCDAT 15's 77 to
78, level to 17 % behind — and pays for it in size: 8 to 65 B/key where it holds a corpus. On the
longer keys it does hold, `domains`, `idents` and `pypi`, it is the slowest lexindex row, 467 to
700 ns, because a slot a character is more memory than any cache here keeps. It refuses the other
seven corpora, whose tries need more than 2^23 slots, and every corpus past 2^23 keys.

**The dial.** `DictIndex` at block 1024 is the smallest structure in the table and among the slowest
to look up, because a bigger block is more front-coded keys to scan. That is the trade-off it is
*for*, and it is a dial: on `words`, block 32 measures 2.85 B/key at 202 ns against MARISA ρ=2's
2.98 at 343 — smaller **and** faster than the trie — while XCDAT 15 answers in 77 ns at 7.30 B/key,
2.6 times block 32's size. Pick the corner you need and read the full table, which `sib table` prints with
every structure and every configuration in it.

**Builds.** ART is the quickest build from elsewhere on all thirteen, and it is kept in this
comparison, where it can only flatter the other side: it builds nodes over keys it never copies.
lexindex's quickest build leads it on `dna` and `opaque` and trails it on the other eleven, by 8 % on
`paths` to 2.5× on `titles-en`. Every other structure builds after lexindex on all thirteen, 1.35×
(`words`) to 6.5× (`dna`) slower than its quickest build. Peak memory is in the artifact and not
tabled: it counts each driver's own copies of the keys and the queries,
which frontier_lex and the C++ drivers hold differently.

## Results: ten million keys

Six corpora on 2026-09-25, the same machine, toolchain and protocol; other work took a median of
0.02 CPUs over 530 processes. Artifact `results/frontier-10m-2026-09-25-arz-cc97350.json`.

| corpus | keys | raw B/key | lexindex, smallest | smallest other | margin | fastest other | `HashedDict` closed | lexindex's fastest exact search |
|---|---:|---:|---|---|---:|---|---:|---|
| `dna` | 10,000,000 | 24.0 | **3.81** (Dict 1024) | 5.98 (C²-CoCo ρ=1) | **+36.3 %** | XCDAT 15 553 ns | **60 ns** | 429 ns (Dict 1024 routed), **0.78×** |
| `numeric` | 10,000,000 | 6.9 | **357 B total** (StringIndex) | 0.51 (CoCo) | **+99.99 %** | XCDAT 15 199 ns | **36 ns** | 97 ns (StringIndex), **0.49×** |
| `opaque` | 10,000,000 | 16.0 | **9.95** (Dict 1024) | 13.73 (PDT) | **+27.5 %** | XCDAT 15 323 ns | **72 ns** | 448 ns (Dict 1024 routed), 1.39× |
| `titles-en` | 10,000,000 | 21.0 | **5.48** (Dict 1024) | 5.71 (MARISA ρ=2) | **+4.1 %** | XCDAT 15 567 ns | **66 ns** | 545 ns (Dict 256 routed), 0.96× |
| `urls` | 10,000,000 | 52.4 | **5.53** (Dict 1024) | 5.83 (MARISA ρ=2) | **+5.2 %** | XCDAT 15 692 ns | **78 ns** | 628 ns (Dict 256 routed), **0.91×** |
| `uuid` | 10,000,000 | 36.0 | **17.42** (Dict 1024) | 20.59 (PDT) | **+15.4 %** | XCDAT 15 542 ns | **78 ns** | 528 ns (Dict 256 routed), 0.97× |

`DictIndex` is the smallest structure on five and `StringIndex` on `numeric`, at 357 bytes for ten
million keys. The exact search wins `dna` (0.78×), `numeric` (0.49×) and `urls` (0.91×), is level
on `titles-en` and `uuid` — 4 % and 3 % ahead, inside what the placement of a process's memory
moves a lookup on this machine — and loses `opaque` at 1.39×: random sixteen-symbol ids share only
their first few symbols with a neighbour, so front coding saves little and the scan still decodes.
lexindex's quickest build leads ART's on `dna`, `opaque`, `urls` and `uuid`, ties it on `numeric`
(643 against 641 ms) and trails it on `titles-en` by 12 %; every other structure builds 1.85×
(`numeric`) to 9.2× (`dna`) slower.

## Results: past ten million keys

`results/frontier-full-2026-09-25-arz-cc97350.json` runs every structure over English Wikipedia's
titles and URLs whole, 19.2 million keys each; no fetched corpus here is larger.

| corpus | keys | raw B/key | lexindex, smallest | smallest other | margin | fastest other | `HashedDict` closed | lexindex's fastest exact search |
|---|---:|---:|---|---|---:|---|---:|---|
| `titles-en` | 19,217,770 | 21.0 | **5.02** (Dict 1024) | 5.23 (MARISA ρ=2) | **+4.1 %** | XCDAT 15 660 ns | **71 ns** | 631 ns (Dict 1024 routed), 0.96× |
| `urls` | 19,217,771 | 52.4 | **5.06** (Dict 1024) | 5.33 (MARISA ρ=2) | **+4.9 %** | XCDAT 15 807 ns | **85 ns** | 734 ns (Dict 1024 routed), **0.91×** |

Both exact searches are ahead of XCDAT 15's: `urls` by 9 %, `titles-en` by 4 %, which is level.
`DictIndex` builds before every other structure on both, in 3.7 and 3.9 s against ART's 3.8 and
7.3. CoCo-trie runs out of the 28 GB of address space a process is allowed on both, as it does on
five of six at ten million.

**The exact-search gap, by scale**: lexindex's fastest exact search over XCDAT 15's time.

| corpus | 1 M | 10 M | 19.2 M |
|---|---:|---:|---:|
| `titles-en` | 1.34 | 0.96 | 0.96 |
| `urls` | 1.08 | **0.91** | **0.91** |
| `uuid` | 1.06 | 0.97 | |
| `opaque` | 1.38 | 1.39 | |
| `dna` | **0.92** | **0.78** | |
| `numeric` | **0.58** | **0.49** | |

On lexindex 4.0.0 the same cells read 1.69, 1.18 and 1.17 on `titles-en` and 1.26, 1.07 and 1.08
on `urls`: the restart words `DictIndex` gained in 4.4 are what took the ten-million cells under
one. The gap closes in one step, from a million keys to ten million, and holds past it; `opaque` is the
corpus scale does not help. The likely reason is the 16 MiB L3: at a million keys it holds much of
a structure a few bytes a key in size, at ten million most structures are several times its size.
That is a reading, not a measured miss count.

`results/frontier-100m-2026-09-21-arz-a6c13d0.json` ran the four generated corpora at a hundred
million keys on 2026-09-21, with lexindex 4.0.0 and **four structures, not twenty-five**: there
every driver peaks near ten times its ten-million figure, and the whole set would run for two days.
The four are both ends of every ten-million front then — `DictIndex` at blocks 256 and 1024,
`StringIndex`, and XCDAT 15 — so this table says where the two ends went and nothing about the
structures that were not run, and it has not been re-run on 4.5, whose routed `DictIndex` it does
not include.

| corpus | lexindex, smallest | XCDAT 15 | lexindex, fastest | XCDAT 15 |
|---|---|---:|---|---:|
| `numeric` | **420 B total** (StringIndex) | 7.05 | **156 ns** (StringIndex) | 408 ns |
| `dna` | **3.40** (Dict 1024) | 9.45 | 844 ns (Dict 1024) | 864 ns |
| `uuid` | **16.94** (Dict 1024) | 37.98 | 924 ns (StringIndex, 34.91) | **873 ns** |
| `opaque` | **9.46** (Dict 1024) | 19.99 | 833 ns (StringIndex, 19.58) | **546 ns** |

`dna` at a hundred million is a tie, not a win: 2 % is inside what the placement of a process's
memory alone moves a lookup on this machine, whose two DIMMs are unequal. `DictIndex` built in
8–14 s at a hundred million against XCDAT 15's 23–132.

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
- **A refusal is a cell.** A structure that cannot hold a corpus says so, and its cell carries the
  reason in place of numbers: lexindex's `DoubleArrayIndex` numbers its slots and its ids in 23
  bits and refuses a corpus past 8 388 608 of either — seven of the thirteen at a million keys,
  every corpus at ten million. CoCo-trie running out of the address space a process may map is
  recorded the same way.
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
