# string-index-benchmarks

One protocol, thirteen corpora, every compressed string dictionary anyone will let you build.

A *string dictionary* maps a set of strings to dense integer ids and back. Every published one comes
with a table, and no two tables are comparable: different corpora, different machines, different
definitions of "size", different ideas of what counts as a lookup. This repository is one harness
that builds them all from source at pinned commits, measures them the same way on the same keys, and
writes an artifact naming the machine, the commits and the corpus hashes behind every number.

It exists because a benchmark you cannot re-run is a claim, not a measurement.

**What it measures.** MARISA, XCDAT, CoCo-trie, PDT, FST, ART, the C² framework's four compressed
variants, and lexindex — each over a grid of its own configurations, never at a default chosen to
flatter someone. Serialised bytes per key, single-key lookup latency, build time and peak RSS.
MARISA's grid is the one to three tries the C² benchmark builds, at the default cache; its smallest
configuration lies outside it, so its size has an artifact of its own: [MARISA at its
smallest](#marisa-at-its-smallest). What it and lexindex hold once loaded has another: [What a
loaded index holds](#what-a-loaded-index-holds). Plain front coding, the yardstick under all of
them, has a third: [Plain front coding](#plain-front-coding).

**Who wrote it.** The author of [lexindex](https://github.com/ilgrad/lexindex), which is one of the
competitors here. That is a conflict of interest and the reason the protocol below is as explicit as
it is: lexindex is fetched from crates.io at a pinned version like every other entrant, this
repository has no dependency on a lexindex checkout, and the corpora where a trie comes within a few
tenths of a per cent of it, or passes it once both are loaded — MARISA at its smallest, on `paths`
and on the larger titles and URLs files — are in tables of their own rather than a footnote. Re-run
it and disagree; see the last section.

## Quickstart

```bash
git clone https://github.com/ilgrad/string-index-benchmarks && cd string-index-benchmarks
sib build                      # fetch and compile every competitor at its pinned commit
sib corpora build              # fetch and derive the thirteen corpora (4.6 GB, once)
sib run                        # the campaign at a million keys
sib marisa-floor               # MARISA's smallest size on the same corpora -- sizes only, minutes
sib resident                   # what each loaded index holds beside its file -- sizes only, minutes
sib baselines                  # front coding on the same corpora -- sizes only; Re-Pair is slow
sib maps                       # static maps that do not store their keys -- sizes only, minutes
sib table results/<latest>.json
```

`sib corpora build` rewrites the tracked `sib/corpora.json`, so `sib run` and the four size-only
commands refuse until they are given `--allow-dirty`; [The corpora](#the-corpora) says why.

`sib` needs Python 3.11+ and nothing else; `sib build` needs a C++20 compiler, CMake, Boost and a
Rust toolchain. If you would rather not install those, the `Containerfile` has them:

```bash
podman build -t sib . && podman run --rm -v "$PWD:/w:Z" -w /w sib sib build
```

The `:Z` is what lets a container read the volume on a host with SELinux enforcing; without it,
`sib` stops at `Permission denied`. The volume has to be a plain clone: a `git worktree` keeps its
repository outside the mount, and `harness/build.sh` then stops at `not a git repository`.

**One run inside the image is on record**, 2026-11-02, at commit `9172cb3`, on Fedora 44 with
podman 5.8.9, the image built with no cache, over a fresh clone and a 20,000-line key file:

```bash
podman build -t sib .
podman run --rm -v "$PWD:/w:Z" -w /w sib sib build
podman run --rm -v "$PWD:/w:Z" -w /w sib sib run --rounds 1 --keys my_catalog.txt
```

Each command exited 0. The image holds GCC 14.2, CMake 3.31, Boost 1.83, rustc 1.99.1 and uv 0.9.7,
and `sib build` compiled every entrant with them, though the campaigns here ran on GCC 16.2. The run
gave all 32 structures a cell, none failed, and it wrote its artifact and its table. The 21 C²
and XCDAT rows hold the same sizes as the same drivers built on the host with GCC 16.2. The
times of that run are not quoted: the machine was busy, and they are the machine's. The artifact's
`host` is the container's id. At `68652c5`, `sib build` in the image compiled libCSD and
RearCodedArray too, and on that file their drivers printed the same bytes as the host's. No campaign
and no corpus but `words` has been run inside the image.

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
| fetched from a pinned URL | `titles-en`, `titles-ru`, `titles-zh` (Wikipedia dumps), `domains` (Tranco), `paths` (a Debian archive's file list), `idents` (every identifier in the `rustc` source release); `pypi` too, but what that URL serves is not pinned |
| derived from a fetched one | `urls` — the article titles under Wikipedia's own prefix and escaping |
| generated from a fixed seed | `uuid`, `numeric`, `opaque`, `dna` |
| read off the machine | `words` — `/usr/share/dict/words`, tagged `host`, the only one that is |

**Two of the thirteen do not reproduce: `words` and `pypi`.** Eleven reproduce byte-for-byte
anywhere and at any time; rebuilding them nine days apart reproduced every SHA-256. For the other
two, `sib corpora build` gives you another file than the one behind the tables here:

- **`words`**, tagged `host` in `sib/corpora.py`, is whatever `/usr/share/dict/words` your machine
  holds. The tables' file is Fedora 44's `words` package, 479,823 keys. The `Containerfile`'s
  `wamerican` gives 104,334 keys, so `words-full` there is a smaller file of other words.
- **`pypi`**, tagged `dated`, is the simple index on the day you build it. The index is live and
  publishes no snapshot, so a rebuild picks up whatever was registered since: 889,864 names on
  2026-09-12, 895,600 on 2026-09-21, which is the tables' file, and 929,729 on 2026-11-02. The
  shuffle runs over the whole pool, so every line can move, `pypi-100000.txt` included.

So a re-run's rows for those two corpora describe other keys: **their cells cannot confirm or refute
the `words` and `pypi` rows here. The other eleven rows compare cell by cell.**

`sib corpora build` also writes what it built into `sib/corpora.json`, which is tracked: the hashes
and key counts of those two, each corpus's `built` date, the machine's name and kernel. From then
on the tree is dirty, so `sib run` and the size-only commands refuse until they are given
`--allow-dirty`, and the artifact is tagged `<commit>-dirty`. Putting the manifest back does not
help: `sib corpora verify` then reports both corpora `CHANGED`, and the same commands refuse for
that reason. What the manifest holds is the hash of the file on the machine that last built it.

Sizes are nested — the 1 M file is a prefix of the 10 M one — so a difference between two scales is
scale and never composition. Every file is UTF-8, one key per line, deduplicated, and **shuffled
with a fixed seed**: a sorted build order is the one order an ordered index must not be handed by
accident.

## The entrants, and their versions

Every entrant is pinned at its latest release on 2026-10-31, or at its latest commit where it has
none: `harness/pins.sh` for the C++ code, a `Cargo.lock` for each Rust harness. The size-only
artifacts — the MARISA floor, what a loaded index holds, plain front coding — were re-run at these
pins and hold the same bytes as the ones they replace, but for fcsd's 4-byte header. The timed
campaigns ran before the bump, so their tables name the versions their artifacts record; rebuilt at
the new pins, the C² driver gave the same `space_cost` on all 208 runs of the million-key
campaign's first round that recorded one. **The lookup and build columns wait for the next
campaign**, which needs a quiet machine. lexindex moved again on 2026-11-06, to 5.0.0: what a loaded
index holds and the static maps were re-run at it, and the campaigns, with the lexindex columns of
the MARISA floor and front coding tables that quote them, still hold 4.5.2's sizes.

| entrant | language | structure | pinned now | the timed campaigns |
|---|---|---|---|---|
| lexindex `DictIndex`, routed `DictIndex`, `StringIndex`, `HashedDictIndex`, `DoubleArrayIndex` | Rust | front-coded blocks under a symbol table; a finite-state transducer (`fst` 0.4.7); a minimal perfect hash over the dictionary; a character-wise double-array trie | 5.0.0 (crates.io), 2026-11-06 | 4.5.2 |
| MARISA, [`s-yata/marisa-trie`](https://github.com/s-yata/marisa-trie) | C++ | recursive LOUDS Patricia trie | 0.3.1, `3e87d53`, 2025-07-20; the commits past it change CI only | 0.2.6, `e54f296` |
| XCDAT, [`kampersanda/xcdat`](https://github.com/kampersanda/xcdat) | C++ | compressed double-array trie, in four layouts (types 7, 8, 15, 16) | 0.2.2, `2451441`, 2024-09-10 | the same |
| C²-FST, C²-CoCo, C²-MARISA, [`alexztc/C2`](https://github.com/alexztc/C2) | C++ | succinct tries with cache-conscious bit vectors and adaptive unary-path compression | `92c1b86`, 2026-06-20 | the same |
| FST, as C² carries it | C++ | SuRF's LOUDS-Dense/Sparse fast succinct trie | C² `92c1b86` | the same |
| CoCo-trie, as C² carries it | C++ | succinct trie of collapsed nodes, each coded by its own best encoding | C² `92c1b86`, with CoCo-trie's adapted headers at `ee860d4`, 2026-04-09 | the same |
| PDT, as C² carries it | C++ | path-decomposed trie | C² `92c1b86` | the same |
| ART, C-ART, as C² carries them | C++ | adaptive radix tree, and its compact form | C² `92c1b86` | the same |
| sux, fcsd ([Plain front coding](#plain-front-coding)) | Rust | rear-coded list; front-coded set | sux 0.15.3, 2026-10-29; fcsd 0.3.1, 2026-10-25 | never timed; sized at the new versions, after sux 0.15.0 and fcsd 0.2.0 |
| libCSD PFC, RPFC, HTFC, HHTFC, RPHTFC, [`migumar2/libCSD`](https://github.com/migumar2/libCSD) ([Plain front coding](#plain-front-coding)) | C++ | front coding in buckets, its internal strings plain or by Re-Pair; the same with Hu-Tucker-coded headers | `568bf8a`, 2016-04-07; it has no release | never timed; sized at this commit |
| RearCodedArray, [`gvinciguerra/RearCodedArray`](https://github.com/gvinciguerra/RearCodedArray) ([Plain front coding](#plain-front-coding)) | C++ | rear coding in blocks of a fixed number of bytes | `608b35e`, 2022-02-15; it has no release | never timed; sized at this commit |
| constmap `ConstMap`, `VerifiedConstMap`, [`lemire/rsconstmap`](https://github.com/lemire/rsconstmap) ([Static maps](#static-maps-that-do-not-store-their-keys)) | Rust | binary fuse map from a string to a 64-bit value; the same with a 64-bit check | 0.3.0 (crates.io), 2026-09-17 | never timed; sized at this version |
| lexindex `ClosedHashIndex`, `CompactHashIndex`, `PerfectHashIndex` ([Static maps](#static-maps-that-do-not-store-their-keys)) | Rust | minimal perfect hash; the same with a fingerprint a key; the same with the keys | 5.0.0 (crates.io), 2026-11-06 | never timed; sized at this version |
| sdsl-lite, sux, ds2i, FSST: what C² builds on | C++ | succinct bit vectors and sequences; Elias–Fano; string compression | `0b861c7` 2026-10-10, `568903f` 2024-10-07, `4f46606` 2021-01-21, `e638d4c` 2026-04-06 | sdsl-lite `4312ea9`, sux `5944f6b`; the other two the same |
| ctriepp, [`ofek.gila1/ctriepp`](https://gitlab.com/ofek.gila1/ctriepp) | C++ | compiled into C²'s driver for a prefix test the campaign does not run | `52d2c16`, 2025-04-09 | the same |

C² builds MARISA from the pinned release and, since 0.3.0 changed the classes its headers declare,
with that release's own headers in place of the 0.2.6 copy C² carries; the wrapper around it is C²'s,
unchanged.

## Results: a million keys

Measured 2026-09-26 on an AMD Ryzen 7 5800HS (8 cores / 16 threads, Fedora 44, GCC 16.2.1, rustc
1.98.1), lexindex 4.5.2 from crates.io, three processes per structure and corpus, even rounds in the
reverse order; other work took a median of 0.04 CPUs while the 1 208 processes ran. Artifact
`results/frontier-1m-2026-09-26-arz-be75a38.json`, which names every pin and every corpus hash.
Swap grew from 2 to 46 MiB over this run and to 269 MiB over the ten-million one: CoCo-trie reaches
26–27 GB before it runs out of address space, and that pushes other programs' idle pages out. The
other structures' lookups read a median 1.5 % slower than in the 4.5.0 campaign, run on a freshly
booted machine (`results/frontier-1m-2026-09-25-arz-cc97350.json`), 0.94–1.05 a cell.
`ART` and `C-ART` are left out of the size and lookup columns: they count their nodes and not the
keys those nodes point into.

| corpus | keys | raw B/key | lexindex, smallest | smallest other | margin | fastest other | `HashedDict` closed | lexindex's fastest exact search |
|---|---:|---:|---|---|---:|---|---:|---|
| `words` | 479,823 | 9.3 | **2.51** (Dict 1024) | 2.98 (MARISA ρ=2) | **+15.6 %** | XCDAT 15 78 ns | **14 ns** | 74 ns (DoubleArray), 0.95× |
| `dna` | 1,000,000 | 24.0 | **4.23** (Dict 1024) | 6.14 (CoCo) | **+31.1 %** | XCDAT 15 277 ns | **43 ns** | 263 ns (Dict 256 routed), **0.95×** |
| `domains` | 1,000,000 | 13.8 | **4.36** (Dict 1024) | 4.87 (MARISA ρ=2) | **+10.5 %** | XCDAT 15 147 ns | **28 ns** | 211 ns (StringIndex), 1.44× |
| `idents` | 1,000,000 | 16.6 | **4.86** (Dict 1024) | 5.35 (MARISA ρ=2) | **+9.2 %** | XCDAT 15 193 ns | **36 ns** | 251 ns (StringIndex), 1.30× |
| `numeric` | 1,000,000 | 5.9 | **301 B total** (StringIndex) | 0.52 (CoCo) | **+99.9 %** | XCDAT 15 54 ns | **14 ns** | 29 ns (DoubleArray), **0.55×** |
| `opaque` | 1,000,000 | 16.0 | **10.29** (Dict 1024) | 11.11 (CoCo) | **+7.4 %** | XCDAT 15 207 ns | **46 ns** | 288 ns (StringIndex), 1.39× |
| `paths` | 1,000,000 | 58.4 | **6.51** (Dict 1024) | 6.79 (MARISA ρ=2) | **+4.1 %** | XCDAT 15 449 ns | **61 ns** | 495 ns (StringIndex), 1.10× |
| `pypi` | 895,600 | 13.3 | **4.02** (Dict 1024) | 4.51 (MARISA ρ=2) | **+10.8 %** | XCDAT 15 136 ns | **28 ns** | 214 ns (StringIndex), 1.57× |
| `titles-en` | 1,000,000 | 21.0 | **7.21** (Dict 1024) | 8.19 (MARISA ρ=2) | **+11.9 %** | XCDAT 15 243 ns | **42 ns** | 324 ns (Dict 256 routed), 1.34× |
| `titles-ru` | 1,000,000 | 35.8 | **6.70** (Dict 1024) | 8.61 (MARISA ρ=2) | **+22.2 %** | XCDAT 15 361 ns | **53 ns** | 410 ns (Dict 256 routed), 1.14× |
| `titles-zh` | 1,000,000 | 16.9 | **5.69** (Dict 1024) | 6.54 (MARISA ρ=2) | **+13.0 %** | XCDAT 15 195 ns | **35 ns** | 235 ns (DoubleArray), 1.21× |
| `urls` | 1,000,000 | 52.4 | **7.27** (Dict 1024) | 8.39 (MARISA ρ=2) | **+13.4 %** | XCDAT 15 365 ns | **59 ns** | 381 ns (Dict 256 routed), 1.04× |
| `uuid` | 1,000,000 | 36.0 | **17.89** (Dict 1024) | 21.44 (PDT) | **+16.5 %** | XCDAT 15 339 ns | **57 ns** | 356 ns (Dict 256 routed), 1.05× |

Thirteen of thirteen on size — against MARISA as the campaign builds it; against MARISA at its
smallest, twelve and a tie on `paths` ([below](#marisa-at-its-smallest)) — but read the size columns
before the others. lexindex enters eleven rows: `DictIndex` at three block sizes, with and without
the restart words that route a lookup, `StringIndex`, `HashedDictIndex` at three fingerprint widths,
and `DoubleArrayIndex`. The fourth column is the smallest of them on each corpus, against the
smallest of eight structures on the other side; holding one side to a single index while the other
picks from eight would be a different measurement, not a modest one. On twelve corpora that index is
the front-coded `DictIndex`. On `numeric` it is `StringIndex`, where an fst folds a dense decimal id
space into **301 bytes whole** — a real win and a degenerate corpus at once, and the total is
printed rather than a rounded 0.00 so that it reads as both. The artifacts here record a size in
MiB to six decimals, a byte either way at this size, so each total is the blob's own count: the
loaded-index artifact's at a million and ten million keys ([below](#what-a-loaded-index-holds)),
and lexindex 4.0.0's `serialized_len()` over the same ids at a hundred million. `lexindex plan`
picks the index off the keys alone, which is what makes that column something a caller gets rather
than something chosen here after the fact.

**Two lookup columns, because there are two questions.** `HashedDictIndex` — a minimal perfect hash
beside the dictionary it is built over — answers first on all thirteen, 14 to 61 ns against XCDAT
15's 54 to 449. Its closed row gives a key it was not built from some id rather than none; its
fingerprinted rows, also first on every corpus, turn away all but one stranger in 2^8 or 2^16 (see
the protocol below). The last column asks the stricter question: lexindex's fastest structure that
turns *every* stranger away, as the tries do, over XCDAT 15's time. **That column is where lexindex
still loses at a million keys.** It wins `dna` (a routed `DictIndex`, 0.95×) and `numeric`
(`DoubleArrayIndex`, 29 ns against 54), is level on `words` and `urls` — 4 % ahead and 4 % behind,
inside what the placement of a process's memory moves a lookup on this machine — and trails on the
other nine, by 5 % on `uuid` to 57 % on `pypi`.

**`DoubleArrayIndex` is a lexicon structure, not a general one.** A double array over characters
with a whole node in one eight-byte slot, it is lexindex's fastest exact search on `words`,
`numeric` and `titles-zh` — on `words` its three rounds read 72 to 75 ns against XCDAT 15's 77 to
78, 4 to 7 % ahead in each — and pays for it in size: 8 to 65 B/key where it holds a corpus. On the
longer keys it does hold, `domains`, `idents` and `pypi`, it is the slowest lexindex row, 450 to
693 ns, because a slot a character is more memory than any cache here keeps. It refuses the other
seven corpora, whose tries need more than 2^23 slots, and every corpus past 2^23 keys.

**The dial.** `DictIndex` at block 1024 is the smallest structure in the table and among the slowest
to look up, because a bigger block is more front-coded keys to scan. That is the trade-off it is
*for*, and it is a dial: on `words`, block 32 measures 2.85 B/key at 208 ns against MARISA ρ=2's
2.98 at 346 — smaller **and** faster than the trie — while XCDAT 15 answers in 78 ns at 7.30 B/key,
2.6 times block 32's size. Pick the corner you need and read the full table, which `sib table` prints with
every structure and every configuration in it.

**Builds.** ART is the quickest build from elsewhere on all thirteen, and it is kept in this
comparison, where it can only flatter the other side: it builds nodes over keys it never copies.
lexindex's quickest build leads it on six — `words`, `dna`, `numeric`, `opaque`, `paths` and
`uuid` — and trails it on the other seven, by 12 % on `urls` to 2.1× on `titles-en`; C-ART builds
before it on four of those, `domains`, `pypi`, `titles-en` and `titles-zh`. Every structure but the
two ARTs builds after lexindex on all thirteen, 1.7× (`words`) to 8.3× (`dna`) slower than its
quickest build. Peak memory is in the artifact and not
tabled: it counts each driver's own copies of the keys and the queries,
which frontier_lex and the C++ drivers hold differently.

## Results: ten million keys

Six corpora on 2026-09-26, the same machine, toolchain and protocol; other work took a median of
0.03 CPUs over 530 processes, and the other structures' lookups read a median 1.7 % slower than at
4.5.0, 0.91–1.06 a cell. Artifact `results/frontier-10m-2026-09-26-arz-be75a38.json`.

| corpus | keys | raw B/key | lexindex, smallest | smallest other | margin | fastest other | `HashedDict` closed | lexindex's fastest exact search |
|---|---:|---:|---|---|---:|---|---:|---|
| `dna` | 10,000,000 | 24.0 | **3.81** (Dict 1024) | 5.98 (C²-CoCo ρ=1) | **+36.3 %** | XCDAT 15 561 ns | **60 ns** | 434 ns (Dict 1024 routed), **0.77×** |
| `numeric` | 10,000,000 | 6.9 | **356 B total** (StringIndex) | 0.51 (CoCo) | **+99.99 %** | XCDAT 15 204 ns | **37 ns** | 97 ns (StringIndex), **0.48×** |
| `opaque` | 10,000,000 | 16.0 | **9.95** (Dict 1024) | 13.73 (PDT) | **+27.5 %** | XCDAT 15 330 ns | **72 ns** | 449 ns (Dict 1024 routed), 1.36× |
| `titles-en` | 10,000,000 | 21.0 | **5.48** (Dict 1024) | 5.71 (MARISA ρ=2) | **+4.1 %** | XCDAT 15 580 ns | **67 ns** | 548 ns (Dict 256 routed), **0.95×** |
| `urls` | 10,000,000 | 52.4 | **5.53** (Dict 1024) | 5.83 (MARISA ρ=2) | **+5.2 %** | XCDAT 15 700 ns | **80 ns** | 631 ns (Dict 256 routed), **0.90×** |
| `uuid` | 10,000,000 | 36.0 | **17.42** (Dict 1024) | 20.59 (PDT) | **+15.4 %** | XCDAT 15 553 ns | **79 ns** | 534 ns (Dict 256 routed), 0.97× |

`DictIndex` is the smallest structure on five and `StringIndex` on `numeric`, at 356 bytes for ten
million keys; against MARISA at its smallest, English titles are 0.11 % apart and URLs 0.30 %
([below](#marisa-at-its-smallest)). The exact search wins `dna` (0.77×), `numeric` (0.48×), `urls`
(0.90×) and `titles-en` (0.95×), is level on `uuid` — 3 % ahead, inside what the placement of a
process's memory moves a lookup on this machine — and loses `opaque` at 1.36×: random sixteen-symbol
ids share only their first few symbols with a neighbour, so front coding saves little and the scan
still decodes.
lexindex's quickest build leads ART's on `dna`, `numeric`, `opaque`, `urls` and `uuid` and is level
on `titles-en` (1 930 against 1 968 ms); C-ART builds after it on all six, and every structure but
the two ARTs 2.7× (`numeric`) to 12.1× (`dna`) slower.

## Results: past ten million keys

`results/frontier-full-2026-09-26-arz-be75a38.json` runs every structure over English Wikipedia's
titles and URLs whole, 19.2 million keys each; no fetched corpus here is larger. It ran on a
rebooted machine and used no swap from start to end.

| corpus | keys | raw B/key | lexindex, smallest | smallest other | margin | fastest other | `HashedDict` closed | lexindex's fastest exact search |
|---|---:|---:|---|---|---:|---|---:|---|
| `titles-en` | 19,217,770 | 21.0 | **5.02** (Dict 1024) | 5.23 (MARISA ρ=2) | **+4.1 %** | XCDAT 15 672 ns | **69 ns** | 628 ns (Dict 1024 routed), **0.93×** |
| `urls` | 19,217,771 | 52.4 | **5.06** (Dict 1024) | 5.33 (MARISA ρ=2) | **+4.9 %** | XCDAT 15 800 ns | **84 ns** | 723 ns (Dict 1024 routed), **0.90×** |

Both exact searches are ahead of XCDAT 15's: `urls` by 10 %, `titles-en` by 7 %. `DictIndex` builds
before every other structure on both, in 3.3 and 3.5 s against ART's 3.8 and 7.1. CoCo-trie runs out
of the 28 GB of address space a process is allowed on both, as it does on five of six at ten
million. Against MARISA at its smallest the two size margins are 1.0 % and 1.3 %
([below](#marisa-at-its-smallest)).

**The exact-search gap, by scale**: lexindex's fastest exact search over XCDAT 15's time.

| corpus | 1 M | 10 M | 19.2 M |
|---|---:|---:|---:|
| `titles-en` | 1.34 | **0.95** | **0.93** |
| `urls` | 1.04 | **0.90** | **0.90** |
| `uuid` | 1.05 | 0.97 | |
| `opaque` | 1.39 | 1.36 | |
| `dna` | **0.95** | **0.77** | |
| `numeric` | **0.55** | **0.48** | |

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
| `numeric` | **421 B total** (StringIndex) | 7.05 | **156 ns** (StringIndex) | 408 ns |
| `dna` | **3.40** (Dict 1024) | 9.45 | 844 ns (Dict 1024) | 864 ns |
| `uuid` | **16.94** (Dict 1024) | 37.98 | 924 ns (StringIndex, 34.91) | **873 ns** |
| `opaque` | **9.46** (Dict 1024) | 19.99 | 833 ns (StringIndex, 19.58) | **546 ns** |

`dna` at a hundred million is a tie, not a win: 2 % is inside what the placement of a process's
memory alone moves a lookup on this machine, whose two DIMMs are unequal. `DictIndex` built in
8–14 s at a hundred million against XCDAT 15's 23–132.

## MARISA at its smallest

The campaign builds MARISA as the C² benchmark does, at one, two and three tries and the default
cache, and that is not marisa's smallest trie. At the same number of tries the tiny cache is smaller
on every corpus, and eleven of the thirteen at a million keys keep getting smaller past three tries,
`urls` until twenty. `sib marisa-floor` builds the pinned marisa at 1 to 32 tries with
`MARISA_TINY_CACHE` over the campaign's own corpus files and records sizes only — nothing is timed,
so these configurations have no lookup column, and marisa's own documentation says a deeper
recursion "degrades the search performance". Node order and tail mode stay at marisa's defaults:
over the same grid at a million keys, label order builds the same bytes on every corpus, and binary
tails save at most 160 bytes where they save any (`domains`), too little to move a margin below.
Every floor in the table lies inside that grid, the deepest at 30 tries. Sizes are files, as the
protocol below has it, so the campaign's-best column reads a few hundred bytes above the campaign's
own MARISA rows, which count `total_size()`. Artifacts
`results/marisa-floor-{1m,10m,full}-2026-10-31-arz-c36150a.json`, at marisa 0.3.1; the lexindex
column is the campaign's.

| corpus | keys | MARISA, the campaign's best | MARISA, smallest | lexindex, smallest | margin |
|---|---:|---:|---|---|---:|
| `words` | 479,823 | 2.978 (3 tries) | 2.955 (4 tries, tiny) | **2.513** (Dict 1024) | +14.95 % |
| `dna` | 1,000,000 | 7.562 (3 tries) | 7.525 (3 tries, tiny) | **4.231** (Dict 1024) | +43.78 % |
| `domains` | 1,000,000 | 4.874 (3 tries) | 4.796 (8 tries, tiny) | **4.363** (Dict 1024) | +9.03 % |
| `idents` | 1,000,000 | 5.350 (3 tries) | 5.123 (12 tries, tiny) | **4.860** (Dict 1024) | +5.13 % |
| `numeric` | 1,000,000 | 1.642 (1 try) | 1.624 (1 try, tiny) | **301 B total** (StringIndex) | +99.981 % |
| `opaque` | 1,000,000 | 18.037 (1 try) | 15.548 (6 tries, tiny) | **10.291** (Dict 1024) | +33.81 % |
| `paths` | 1,000,000 | 6.788 (3 tries) | 6.513 (19 tries, tiny) | **6.511** (Dict 1024) | +0.04 % |
| `pypi` | 895,600 | 4.512 (3 tries) | 4.383 (9 tries, tiny) | **4.024** (Dict 1024) | +8.20 % |
| `titles-en` | 1,000,000 | 8.187 (3 tries) | 7.494 (15 tries, tiny) | **7.212** (Dict 1024) | +3.77 % |
| `titles-ru` | 1,000,000 | 8.609 (3 tries) | 7.610 (19 tries, tiny) | **6.698** (Dict 1024) | +11.99 % |
| `titles-zh` | 1,000,000 | 6.537 (3 tries) | 6.215 (12 tries, tiny) | **5.687** (Dict 1024) | +8.51 % |
| `urls` | 1,000,000 | 8.395 (3 tries) | 7.570 (20 tries, tiny) | **7.271** (Dict 1024) | +3.95 % |
| `uuid` | 1,000,000 | 34.575 (3 tries) | 22.978 (10 tries, tiny) | **17.894** (Dict 1024) | +22.13 % |
| `dna` | 10,000,000 | 6.750 (3 tries) | 6.691 (3 tries, tiny) | **3.813** (Dict 1024) | +43.02 % |
| `numeric` | 10,000,000 | 1.657 (1 try) | 1.627 (1 try, tiny) | **356 B total** (StringIndex) | +99.998 % |
| `opaque` | 10,000,000 | 18.076 (1 try) | 14.717 (5 tries, tiny) | **9.953** (Dict 1024) | +32.37 % |
| `titles-en` | 10,000,000 | 5.715 (3 tries) | 5.484 (18 tries, tiny) | **5.478** (Dict 1024) | +0.11 % |
| `urls` | 10,000,000 | 5.833 (3 tries) | 5.547 (27 tries, tiny) | **5.530** (Dict 1024) | +0.30 % |
| `uuid` | 10,000,000 | 33.207 (3 tries) | 20.618 (9 tries, tiny) | **17.417** (Dict 1024) | +15.53 % |
| `titles-en` | 19,217,770 | 5.233 (3 tries) | 5.070 (19 tries, tiny) | **5.019** (Dict 1024) | +1.02 % |
| `urls` | 19,217,771 | 5.326 (3 tries) | 5.132 (30 tries, tiny) | **5.065** (Dict 1024) | +1.30 % |

Against its smallest, MARISA draws level on `paths`: lexindex's file is 2 431 bytes smaller in 6.5
MB, 0.04 %. That is a tie by any measure, and by the count the campaign takes for MARISA —
`total_size()`, the trie's arrays without the file's framing, 220 to 270 bytes a trie less than what
`save()` writes — MARISA is 2 206 bytes the smaller. At ten million keys English titles are 0.11 %
apart (59 KB) and URLs 0.30 %; at 19.2 million, 1.0 % and 1.3 %. Once loaded, MARISA is the smaller
on those four and on `paths` ([below](#what-a-loaded-index-holds)). The other margins narrow and
stand, from 3.8 % (`titles-en` at a million) to 15 % (`words`) on real keys. On `uuid`, `opaque`,
`dna` and `numeric` the smallest other is still PDT or a CoCo variant, smaller there than MARISA's
floor at both scales. How far the floor lies below the campaign's best is a property of the keys: at
a million, 0.5 % on `dna`, 0.8 % on `words`, 5–12 % on the titles and URLs and a third on `uuid`;
3–5 % on the larger titles and URLs files.

marisa-trie 0.3.1 (2025-07-20), three releases past 0.2.6, moves none of these sizes: the 0.2.6
artifacts these replace, `results/marisa-floor-{1m,10m,full}-2026-09-26-arz-452704f.json`, hold the
same `io_size()` and `total_size()` for all 35 configurations of all 21 rows. 0.3.0's release notes
also announce improved performance, which no size can show, so MARISA's lookup column, timed at
0.2.6, waits for the next campaign.

## What a loaded index holds

Every size above is a file. A loaded index can hold more: lexindex's `load_mmap` leaves the blob to
the page cache and derives lookup tables beside it on the heap — a `DictIndex`'s block samples, its
character-code tables and, on `paths`, a trie over the samples that tie — and marisa's `Trie::mmap`
keeps a few kilobytes of its own. `sib resident` builds each index as the campaign does, writes its
file, maps it, looks up every 97th key, and counts the bytes asked for by every allocation the load
still holds: a counting global allocator in `harness/lex`'s `resident`, replaced `operator new` in
`harness/marisa_resident.cpp`, so both sides are counted alike and neither carries the allocator's
rounding. Each load is counted on a thread of its own, so a buffer a lookup grows and the thread
keeps is charged to it. MARISA is built at each corpus's floor configuration and lexindex as
`DictIndex` at blocks 32, 256 and 1024, at 256 and 1024 with trie labels, and as `StringIndex`; the
table shows the smallest file of each. Nothing is timed. Artifacts
`results/resident-{1m,10m,full}-2026-11-06-arz-c5512f1.json`, at marisa 0.3.1 and lexindex 5.0.0.
The ones they replace, at lexindex 4.5.3
(`results/resident-{1m,10m,full}-2026-10-31-arz-c36150a.json`), hold the same MARISA bytes in
every cell.

| corpus | lexindex, smallest | its file | + `load_mmap` heap | MARISA, smallest | its file | + `mmap` heap | margin, files | margin, mapped |
|---|---|---:|---:|---|---:|---:|---:|---:|
| `words-full` | Dict 1024 | 1,200,371 | 24,234 | 4 tries, tiny | 1,418,040 | 4,544 | +15.35 % | +13.92 % |
| `dna-1000000` | Dict 1024 | 4,230,538 | 19,240 | 3 tries, tiny | 7,524,656 | 3,408 | +43.78 % | +43.55 % |
| `domains-1000000` | Dict 1024 labelled | 4,216,202 | 49,117 | 8 tries, tiny | 4,795,712 | 9,088 | +12.08 % | +11.23 % |
| `idents-1000000` | Dict 1024 labelled | 4,681,600 | 53,582 | 12 tries, tiny | 5,122,544 | 13,632 | +8.61 % | +7.81 % |
| `numeric-1000000` | StringIndex | 301 | 32 | 1 try, tiny | 1,623,704 | 1,136 | +99.98 % | +99.98 % |
| `opaque-1000000` | Dict 1024 | 10,290,593 | 20,072 | 6 tries, tiny | 15,547,856 | 6,816 | +33.81 % | +33.71 % |
| `paths-1000000` | Dict 1024 labelled | 6,094,741 | 74,377 | 19 tries, tiny | 6,513,224 | 21,584 | +6.43 % | +5.60 % |
| `pypi-full` | Dict 1024 labelled | 3,474,796 | 44,163 | 9 tries, tiny | 3,925,536 | 10,224 | +11.48 % | +10.59 % |
| `titles-en-1000000` | Dict 1024 labelled | 6,906,125 | 56,527 | 15 tries, tiny | 7,494,136 | 17,040 | +7.85 % | +7.30 % |
| `titles-ru-1000000` | Dict 1024 | 6,673,189 | 162,336 | 19 tries, tiny | 7,610,368 | 21,584 | +12.31 % | +10.44 % |
| `titles-zh-1000000` | Dict 1024 | 5,666,780 | 289,522 | 12 tries, tiny | 6,215,480 | 13,632 | +8.83 % | +4.38 % |
| `urls-1000000` | Dict 1024 labelled | 6,977,219 | 58,055 | 20 tries, tiny | 7,569,896 | 22,720 | +7.83 % | +7.34 % |
| `uuid-1000000` | Dict 1024 | 17,893,932 | 48,088 | 10 tries, tiny | 22,977,776 | 11,360 | +22.13 % | +21.95 % |
| `dna-10000000` | Dict 1024 | 38,127,206 | 187,096 | 3 tries, tiny | 66,911,944 | 3,408 | +43.02 % | +42.74 % |
| `numeric-10000000` | StringIndex | 356 | 32 | 1 try, tiny | 16,270,544 | 1,136 | +99.998 % | +99.998 % |
| `opaque-10000000` | Dict 1024 | 99,534,713 | 195,052 | 5 tries, tiny | 147,165,592 | 5,680 | +32.37 % | +32.24 % |
| `titles-en-10000000` | Dict 1024 labelled | 51,529,582 | 449,296 | 18 tries, tiny | 54,835,296 | 20,448 | +6.03 % | +5.24 % |
| `urls-10000000` | Dict 1024 labelled | 52,024,143 | 452,568 | 27 tries, tiny | 55,470,184 | 30,672 | +6.21 % | +5.45 % |
| `uuid-10000000` | Dict 1024 | 174,170,565 | 462,955 | 9 tries, tiny | 206,181,120 | 10,224 | +15.53 % | +15.31 % |
| `titles-en-full` | Dict 1024 labelled | 89,432,174 | 846,513 | 19 tries, tiny | 97,442,352 | 21,584 | +8.22 % | +7.37 % |
| `urls-full` | Dict 1024 labelled | 90,398,355 | 856,775 | 30 tries, tiny | 98,617,848 | 34,080 | +8.33 % | +7.50 % |

lexindex is the smaller on all twenty-one rows, by file and mapped; the narrowest mapped margin is
4.38 %, on `titles-zh` at a million keys. At 4.5.3 MARISA at its smallest was the smaller mapped on
five of them — `paths` at a million keys, and English titles and URLs at ten million and at 19.2
million — by 0.41 to 1.77 %. 5.0's labelled `DictIndex` takes all five: its file is 5.9 to 7.3 %
smaller than 4.5.3's smallest on them, and it derives less beside it. A `DictIndex` derives 0.02 to
0.29 bytes a key at a million keys — most on `titles-zh` and `titles-ru`, whose character-code
tables are the largest, then `paths` — and 0.04 to 0.05 on the larger titles and URLs files, where
a mapped marisa trie keeps 1 to 34 KB whatever the corpus. The file's pages are the page cache's,
shared by every process that maps them; the derived tables are each process's own. An owned load
compares the same way: lexindex's `from_bytes` holds the file and the same tables, to the byte on
every row, and marisa's `load()` its file and 0.9 to 27 KB more.

## Plain front coding

The yardstick every compressed string dictionary is measured from has no row in the campaign: the
sorted keys cut into blocks, each block's first key stored whole and every other key as the length
it shares with the key before it and the rest. `sib baselines` builds it twice from crates.io over
the campaign's corpus files — sux 0.15.3's rear-coded list at block ratios 16, 64 and 256, and fcsd
0.3.1's front-coded set at buckets of 8 keys (its default), 64 and 256 — checks that each answers
every key both ways, and records sizes only, so these rows have no lookup column either. fcsd's size
is what `serialize_into` writes; sux's is its `mem_size`, the arrays without a file's framing. fcsd
at 256 is the smaller on every corpus, sux at 256 within 0.021 bytes a key of it. A larger bucket
would shrink both further, and slowly — from 64 keys to 256 took 0.2 % (`uuid`) to 3.8 % (`paths`)
off fcsd's size at a million keys — and a lookup decodes a whole bucket. Artifacts
`results/baselines-{1m,10m,full}-2026-10-31-arz-c36150a.json`; the lexindex column is the
campaign's. They replace the 2026-10-12 ones at sux 0.15.0 and fcsd 0.2.0
(`results/baselines-{1m,10m,full}-2026-10-12-arz-4c2914d.json`): sux builds the same bytes, and
every fcsd set is 4 bytes larger, the versioned header 0.3.0 added, which moves no cell below.

| corpus | keys | raw B/key | front coding (fcsd, 256) | lexindex, smallest | margin |
|---|---:|---:|---:|---|---:|
| `words` | 479,823 | 9.3 | 5.022 | **2.513** (Dict 1024) | +49.95 % |
| `dna` | 1,000,000 | 24.0 | 16.883 | **4.231** (Dict 1024) | +74.94 % |
| `domains` | 1,000,000 | 13.8 | 10.005 | **4.363** (Dict 1024) | +56.40 % |
| `idents` | 1,000,000 | 16.6 | 9.336 | **4.860** (Dict 1024) | +47.95 % |
| `numeric` | 1,000,000 | 5.9 | 3.026 | **301 B total** (StringIndex) | +99.990 % |
| `opaque` | 1,000,000 | 16.0 | 15.250 | **10.291** (Dict 1024) | +32.52 % |
| `paths` | 1,000,000 | 58.4 | 14.395 | **6.511** (Dict 1024) | +54.77 % |
| `pypi` | 895,600 | 13.3 | 8.046 | **4.024** (Dict 1024) | +49.99 % |
| `titles-en` | 1,000,000 | 21.0 | 14.771 | **7.212** (Dict 1024) | +51.17 % |
| `titles-ru` | 1,000,000 | 35.8 | 21.859 | **6.698** (Dict 1024) | +69.36 % |
| `titles-zh` | 1,000,000 | 16.9 | 11.250 | **5.687** (Dict 1024) | +49.45 % |
| `urls` | 1,000,000 | 52.4 | 15.945 | **7.271** (Dict 1024) | +54.40 % |
| `uuid` | 1,000,000 | 36.0 | 33.709 | **17.894** (Dict 1024) | +46.92 % |
| `dna` | 10,000,000 | 24.0 | 15.230 | **3.813** (Dict 1024) | +74.97 % |
| `numeric` | 10,000,000 | 6.9 | 3.031 | **356 B total** (StringIndex) | +99.999 % |
| `opaque` | 10,000,000 | 16.0 | 14.798 | **9.953** (Dict 1024) | +32.74 % |
| `titles-en` | 10,000,000 | 21.0 | 11.950 | **5.478** (Dict 1024) | +54.16 % |
| `urls` | 10,000,000 | 52.4 | 12.890 | **5.530** (Dict 1024) | +57.10 % |
| `uuid` | 10,000,000 | 36.0 | 32.875 | **17.417** (Dict 1024) | +47.02 % |
| `titles-en` | 19,217,770 | 21.0 | 11.010 | **5.019** (Dict 1024) | +54.42 % |
| `urls` | 19,217,771 | 52.4 | 11.869 | **5.065** (Dict 1024) | +57.33 % |

lexindex's smallest index is a third to three quarters smaller than front coding on every row, from
32.5 % (`opaque` at a million keys) to 75.0 % (`dna` at ten million). At the same 256 keys a block,
a `DictIndex` is 31.8 % (`opaque`) to 74.1 % (`dna`) smaller at a million keys: what it adds to
front coding is the symbol table its suffixes are coded in. Front coding is no straw man, though. At
a million keys it is smaller than XCDAT's smallest configuration on ten corpora of the thirteen,
CoCo-trie's on six of the nine it holds, FST's on three (`dna`, `opaque`, `uuid`) and MARISA's on
`opaque` and `uuid` — and on `opaque` than MARISA at its smallest too, by 1.9 %. PDT and lexindex
are smaller on all thirteen.

### libCSD and RearCodedArray

`DictIndex` descends from libCSD's dictionaries, so `sib baselines` sizes them too, and RearCodedArray,
at a million keys and at the commits in the versions table. Artifact
`results/baselines-1m-2026-11-02-arz-68652c5.json` and what the drivers printed,
`results/baselines-1m-2026-11-02-arz-68652c5.log`. Its sux and fcsd rows hold the same bytes as the
2026-10-31 artifact's, all 78 of them. **Nothing here is timed: the `id` and build columns are empty
and owed to the next quiet window.** Nor has anything here run at ten million keys. `sib run
--baselines` is what will time them: `run.sh`'s gates, rounds and shuffled probes, libCSD's five
codings at buckets of 256 and 1024 keys and RearCodedArray's two layouts at 2048 and 8192 bytes,
from a key to its id and from an id to its key. PFC and RearCodedArray take every key; RPFC, HTFC,
HHTFC and RPHTFC decode up to a bucket of compressed strings a lookup, and take the first 20,000
keys of the same shuffle.

PFC is plain front coding, and RPFC is the same with its internal strings under Re-Pair. HTFC codes
headers and internal strings by Hu-Tucker; HHTFC and RPHTFC code the internal strings by Huffman and
by Re-Pair. Each runs at buckets of 8, 64, 256 and 1024 keys, and a cell is its smallest, at 1024
where it names no bucket. A libCSD size is the file `save()` writes, and every key is checked both
ways on that file once reloaded. RearCodedArray has two layouts and blocks of 32 to 8192 bytes; a
cell is its smallest, at 8192 on every corpus. It writes no file, so its size is `size_in_bytes()`,
without a file's framing. `HHTFC` and `RPHTFC` have no column of their own, but they are in `libCSD,
smallest`.

| corpus | keys | PFC | RPFC | HTFC | RearCodedArray | libCSD, smallest | lexindex, smallest | margin | `id` ns, owed | build ms, owed |
|---|---:|---:|---:|---:|---:|---|---|---:|---:|---:|
| `words` | 479,823 | 4.998 | 2.678 | 3.564 | 5.001 | 2.678 (RPFC) | **2.513** (Dict 1024) | +6.15 % | | |
| `dna` | 1,000,000 | 16.850 | 6.357 | 7.507 | 16.881 | 6.235 (HHTFC) | **4.231** (Dict 1024) | +32.15 % | | |
| `domains` | 1,000,000 | 9.982 | 4.583 | 6.487 | 9.995 | 4.583 (RPFC) | **4.363** (Dict 1024) | +4.82 % | | |
| `idents` | 1,000,000 | 9.303 | 5.377 | 7.148 | 9.316 | 5.377 (RPFC) | **4.860** (Dict 1024) | +9.62 % | | |
| `numeric` | 1,000,000 | 3.007 | 1.134 | 1.524 | 3.006 | 1.134 (RPFC) | **301 B total** (StringIndex) | +99.973 % | | |
| `opaque` | 1,000,000 | 15.236 | 15.923 (bucket 256) | 11.994 | 15.257 | 11.994 (HTFC) | **10.291** (Dict 1024) | +14.21 % | | |
| `paths` | 1,000,000 | 14.254 | 6.828 | 10.411 | 14.296 (1 rank wrong) | 6.828 (RPFC) | **6.511** (Dict 1024) | +4.64 % | | |
| `pypi` | 895,600 | 8.019 | 4.518 | 5.524 | 8.029 | 4.518 (RPFC) | **4.024** (Dict 1024) | +10.94 % | | |
| `titles-en` | 1,000,000 | 14.741 | 7.889 | 10.449 | 14.766 (41,085 ranks wrong) | 7.889 (RPFC) | **7.212** (Dict 1024) | +8.58 % | | |
| `titles-ru` | 1,000,000 | 21.806 | 7.333 | wrong answer | 21.866 (594,461 ranks wrong) | 7.333 (RPFC) | **6.698** (Dict 1024) | +8.66 % | | |
| `titles-zh` | 1,000,000 | 11.222 | 6.005 | 9.078 | 11.239 (492,036 ranks wrong) | 6.005 (RPFC) | **5.687** (Dict 1024) | +5.30 % | | |
| `urls` | 1,000,000 | 15.826 | 7.943 | 11.275 | 15.884 | 7.943 (RPFC) | **7.271** (Dict 1024) | +8.46 % | | |
| `uuid` | 1,000,000 | 33.690 | 22.746 (bucket 256) | 19.140 | 33.746 | 18.694 (HHTFC) | **17.894** (Dict 1024) | +4.28 % | | |

lexindex's smallest index is the smaller on all thirteen, by 4.28 % (`uuid`) to 32.15 % (`dna`) with
`numeric` aside. **Here libCSD is the closest rival, closer than MARISA in places:** its smallest
beats MARISA's floor on eight corpora and loses on `idents`, `paths`, `pypi`, `titles-en` and `urls`,
and beats the campaign's `smallest other` on seven (`words`, `domains`, `titles-en`, `titles-ru`,
`titles-zh`, `urls`, `uuid`). Those rows are not in the million-key table above, which holds only
what the campaign also times. How fast RPFC at 1024 keys a bucket answers is what the empty columns
owe. PFC is the control: at 256 keys a bucket its file is 31 to 39 bytes smaller than fcsd's, on
every corpus.

Four defects in the pinned code shape these rows. All four are upstream's, and no source is patched:

- **libCSD RPFC and RPHTFC write one `size_t` past a vector** wherever the key count is a multiple
  of the bucket size, as a million is of 8. That corrupted the heap on twelve corpora in the first
  run. Nothing reads the entry, so the driver's allocator leaves room for it.
- **libCSD RPHTFC crashes in `extract`** on some key sets, in upstream's own `Test` tool as well:
  signal 11 at bucket 256 on `dna` and `domains`, and at every bucket on `numeric`, whose row
  therefore has no RPHTFC size. The artifact holds each failure in place of a size.
- **libCSD HTFC and HHTFC answer wrong on `titles-ru`** at every bucket, so that cell holds no size.
  The first 100,000 keys of the same corpus pass. The first key to fail at each bucket is a long
  title, on which `locate` gives 0 and `extract` another string. The cause is not traced.
- **RearCodedArray's `rank` is wrong** on keys past ASCII: it compares bytes as signed `char`, against
  keys sorted as unsigned bytes. The table counts them, in the layout it sizes. Every key still comes
  back from `access`, so the size stands. An allocation one byte short of the longest key is padded
  by the driver.

## Static maps that do not store their keys

A map from a string to a number can be far smaller than any dictionary of the strings if it never
has to give a string back. constmap (`lemire/rsconstmap`, the Rust port of Daniel Lemire's
`constmap`; `fastconstmap` on PyPI) builds one by binary fuse construction: a key's value is the XOR
of three words of an array. lexindex's hash indexes build one from a minimal perfect hash.
`sib maps` builds both from crates.io over the campaign's corpus files. It checks that every
structure answers every key, asks each structure that can reject a string for as many strings that
are not keys as there are keys (each a key with one byte appended), and counts the ones it accepts.
Sizes are a file's bytes: what constmap's `write_to` writes and lexindex's `serialized_len()`.
Artifacts `results/maps-{1m,10m,full}-2026-11-06-arz-3839546.json`, at lexindex 5.0.0; bytes a
key, the range over the corpora:

| structure | a key gives | a string that is not a key gives | 1 M | 10 M | 19.2 M |
|---|---|---|---:|---:|---:|
| constmap `ConstMap` | the 64-bit value it was built with | an undefined value | 9.044–9.151 | 9.018 | 9.003 |
| lexindex `ClosedHashIndex` | its id, dense in [0, n), in an order the hash picks | some id | **0.240–0.242** | **0.239** | **0.239** |
| constmap `VerifiedConstMap` | the value | `NOT_FOUND`; a 64-bit check, accepted 0 times | 18.088–18.302 | 18.036 | 18.006 |
| lexindex `CompactHashIndex`, 64-bit fingerprint | its id | `None`; accepted 0 times | **8.240–8.242** | **8.239** | **8.239** |
| lexindex `CompactHashIndex`, 32 / 16 / 8 bits | its id | `None`, but for about 2⁻³² / 2⁻¹⁶ / 2⁻⁸ of them; accepted at 1 M 0 times, 0.0011–0.0023 %, 0.380–0.394 % (1/256 is 0.391 %) | 4.240–4.242 / 2.240–2.242 / 1.240–1.242 | 4.239 / 2.239 / 1.239 | 4.239 / 2.239 / 1.239 |
| lexindex `PerfectHashIndex` | its id, and the key back from the id | `None`: it compares the stored key | 4.116–60.622 | 4.614–52.890 | 21.003–51.370 |

The sizes of the first five rows depend on the number of keys only, not on the corpus. At 1 M the
range comes from `words` and `pypi`, which hold fewer keys.

**The two kinds of map do not answer the same question.** constmap stores a value the caller
chooses; lexindex's hash indexes choose the id themselves. Where an id is all a caller needs — to
encode a column of strings as numbers, say — `ClosedHashIndex` holds it in 2.7 % of `ConstMap`'s
bytes. Where the caller has a value of its own, it keeps an array of n values beside the index,
read at the id. With 64-bit values that adds 8 bytes a key, and the pair is still the smaller:
`ClosedHashIndex` and the array take 8.241 bytes a key on `titles-en` at a million keys against
`ConstMap`'s 9.044 (−8.9 %), and 8.239 against 9.003 at 19.2 M (−8.5 %). `CompactHashIndex` at 64
bits and the array take 16.241 against `VerifiedConstMap`'s 18.088 (−10.2 %), and 16.239 against
18.006 at 19.2 M (−9.8 %). An array of narrower values makes the gap wider; constmap's value is 64
bits wide whatever it holds.

Two differences are not about size. constmap's build fails ("duplicate key hash detected") on a key
set in which two keys share their 64-bit xxh64. lexindex builds over keys that share its own 64-bit
hash: it keeps them in a side table, told apart by a second 64-bit hash, and only a pair that shares
both is merged into one id
([its design notes](https://github.com/ilgrad/lexindex/blob/main/docs/design.md#perfecthashindex)).
No corpus here holds an xxh64 pair: every constmap build succeeded. None of these structures except
`PerfectHashIndex` gives a key back from its id, and none has an order or a prefix search, so none
is a row of the campaign's tables.

`fastconstmap` 0.11.1, the PyPI package, builds the same seed and the same array words as the
crate. Its files differ only in that they store the number of keys: `ConstMap` gains a 4-byte field
(format `CMAP0003`), and `VerifiedConstMap` writes the count into 4 bytes the crate leaves zero.
This was checked once, on `titles-en` at a million keys, and is not in an artifact. **The lookup
columns wait for the next campaign**, which needs a quiet machine.

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
  reading and not a sum of a structure's internal arrays — except where a driver can only count
  its arrays: the C² benchmark's `space_cost()` and XCDAT's `memory_in_bytes` leave out a file's
  framing, which for MARISA is 220 to 270 bytes a trie, and the MARISA floor records both. One row
  holds more than its file and counts it: a routed `DictIndex` is the blob and the restart words
  `route_microblocks()` derives beside it at load. What every other load holds beside its file is a
  table of its own: [What a loaded index holds](#what-a-loaded-index-holds).
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
  the artifact is right and the table is a bug. `harness/readme_tables.py` re-derives every cell of
  every results table from the artifacts its section cites, and CI fails on any difference. The
  prose around the tables is not checked. One cell is checked only as far as its artifact goes:
  `421 B total` at a hundred million keys, which the artifact records as 0.000401 MiB, 420 or 421
  bytes.
- **What gets bold.** Bold marks the winner of a comparison a row makes, by these rules, which the
  same script enforces:
  - *A size wins by any margin*, because a size is deterministic. The smaller of two sizes set side
    by side is bold. Bold says which file is smaller and not that the difference matters: `paths`
    in the MARISA floor's table is bold at 0.04 %, which the text below that table calls a tie.
  - *A time wins only by more than 5 %*, because the placement of a process's memory alone moves a
    lookup 4 to 7 % on this machine. The faster time has to be under 0.95 of the slower, in the
    artifact's medians and not in the printed digits. So `0.95×` is bold on `dna` (0.9487) and plain
    on `words` (0.9547).
  - In the campaign tables, lexindex's smallest is set against the smallest other, and `margin`
    takes the bold of the size it measures. `HashedDict` closed is set against the fastest other.
    The last column's ratio is bold where lexindex's exact search wins; where it loses, the ratio
    above one says so and nothing is bold. The exact-search gap's table follows that column.
  - At a hundred million keys, the two sizes are set against each other and the two times against
    each other, so XCDAT 15's time is bold where it wins.
  - In the static maps' table, each constmap row is set against the lexindex row that rejects the
    same strangers. A row with no such partner has no bold.
  - The margins of the MARISA floor's table and of the front-coding tables are plain. The
    loaded-index table has no bold at all: its margins are the result.

`run.sh` refuses to run on a dirty checkout unless told `--allow-dirty`, and stamps the commit it
ran at into the filename.

## Layout

| path | what |
|---|---|
| `harness/build.sh` | fetches and compiles every competitor at its pinned commit into `build/` |
| `harness/pins.sh` | the commits, in one place |
| `harness/run.sh` | the campaign: quiet gate, rounds, ordering, artifact |
| `harness/lex/` | the lexindex entrant and `resident`, depending on the published crate |
| `harness/xcdat_frontier.cpp` | the XCDAT entrant, since XCDAT ships no benchmark driver |
| `harness/marisa_floor.cpp` | MARISA's size at every `num_tries` and the tiny cache, from the pinned marisa |
| `harness/marisa_floor.py` | runs it over a scale's corpora into `results/marisa-floor-*.json` |
| `harness/marisa_resident.cpp` | the heap a loaded marisa trie keeps, from the pinned marisa |
| `harness/resident.py` | runs it and `harness/lex`'s `resident` over a scale's corpora into `results/resident-*.json` |
| `harness/baselines/` | plain front coding's size, sux's rear-coded list and fcsd's set, from crates.io |
| `harness/libcsd_baselines.cpp`, `harness/rca_baselines.cpp` | libCSD's and RearCodedArray's sizes, from their pins |
| `harness/libcsd_frontier.cpp`, `harness/rca_frontier.cpp` | their times under the campaign's protocol, for `run.sh --baselines` |
| `harness/baselines.py` | runs all three over a scale's corpora into `results/baselines-*.json` and its `.log` |
| `harness/maps/` | static maps that do not store their keys, constmap's and lexindex's, from crates.io |
| `harness/maps.py` | runs it over a scale's corpora into `results/maps-*.json` |
| `harness/tables.py` | artifact → markdown |
| `harness/readme_tables.py` | CI's check: every results table in this README, re-derived from the artifacts |
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
