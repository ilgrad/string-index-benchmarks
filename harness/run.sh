#!/usr/bin/env bash
# The research-frontier campaign: lexindex, the nine structures of the C² benchmark and XCDAT's four
# tries on the corpus set, one process per structure and corpus, into results/.
#
#   harness/run.sh                          # the thirteen corpora at 1 M keys, or all a corpus has
#   harness/run.sh --scale 10m              # the six corpora with a ten-million-key file
#   harness/run.sh urls-1000000            # named corpus files only
#   harness/run.sh --rounds 1                 # one process a structure and corpus rather than three
#   harness/run.sh --allow-dirty          # for development; the artifact is tagged <sha>-dirty
#
# One protocol for every row, C²'s `benchmark.cpp`: read the file, sort and deduplicate, build once,
# report the structure's own size, then look every key up once in one fixed shuffle -- a single timed
# pass, no warm-up -- and report the mean. `frontier_lex` and `xcdat_frontier` do the same for
# lexindex and XCDAT. Each round runs every process once, even rounds in the reverse order, and
# tables.py reports the median. Build everything first with harness/build.sh.
set -euo pipefail

# Overridable, because the two gates answer different questions. A *published* latency number needs
# both at their defaults -- a benchmark on a busy machine measures the machine. A run over someone
# else's own keys usually wants the sizes, which are deterministic, and cannot wait half an hour for
# a laptop to go quiet; `sib run --keys` raises both and says on the table that the ns column is not
# comparable to anything.
LOAD_CEILING=${SIB_LOAD_CEILING:-1.0}
# Before each process, other work must keep fewer CPUs than this busy for a second; an idle desktop
# session on the machine the published tables come from measures 0.6-0.7.
QUIET_CPUS=${SIB_QUIET_CPUS:-1.0}
# How long one process may wait for that before the run stops.
SETTLE_SECONDS=${SIB_SETTLE_SECONDS:-1800}
# A build that runs away fails instead of swapping the machine.
ADDRESS_SPACE_KB=28000000

root=$(git -C "$(dirname "$0")" rev-parse --show-toplevel)
cd "$root"
# shellcheck source=harness/pins.sh
. harness/pins.sh
frontier=${SIB_BUILD:-$root/build}
corpora=${SIB_CORPORA:-$root/corpora}
c2=$frontier/c2/build/benchmark
xcdat=$frontier/xcdat_frontier
lex=$root/harness/lex/target/release/frontier_lex

allow_dirty=0
scale=1m
rounds=3
named=()
while [ $# -gt 0 ]; do
  case "$1" in
    --allow-dirty) allow_dirty=1 ;;
    --scale)
      scale=${2:-}
      shift
      ;;
    --rounds)
      rounds=${2:-}
      shift
      ;;
    -h | --help)
      sed -n '2,15p' "$0" | cut -c3-
      exit 0
      ;;
    -*)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
    *) named+=("$1") ;;
  esac
  shift
done

case "$scale" in
  1m)
    stems=(words-full dna-1000000 domains-1000000 idents-1000000 numeric-1000000 opaque-1000000
      paths-1000000 pypi-full titles-en-1000000 titles-ru-1000000 titles-zh-1000000 urls-1000000
      uuid-1000000)
    limit=1800
    ;;
  10m)
    stems=(dna-10000000 numeric-10000000 opaque-10000000 titles-en-10000000 urls-10000000
      uuid-10000000)
    limit=7200
    ;;
  *)
    echo "--scale takes 1m or 10m, not '$scale'" >&2
    exit 2
    ;;
esac
if ! [[ "$rounds" =~ ^[1-9][0-9]*$ ]]; then
  echo "--rounds takes a positive count, not '$rounds'" >&2
  exit 2
fi
table=frontier-$scale
if [ ${#named[@]} -gt 0 ]; then
  stems=("${named[@]}")
  table="frontier-named"
fi

commit=$(git rev-parse --short HEAD)
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  if [ "$allow_dirty" -eq 0 ]; then
    echo "refusing: the working tree has uncommitted changes, so the result would not be" >&2
    echo "attributable to the commit it is named after. Commit, stash, or --allow-dirty." >&2
    exit 1
  fi
  commit=$commit-dirty
fi

load=$(cut -d' ' -f1 /proc/loadavg)
if awk -v l="$load" -v c="$LOAD_CEILING" 'BEGIN { exit !(l > c) }'; then
  echo "refusing: load average $load is above $LOAD_CEILING -- a benchmark on a busy machine" >&2
  echo "measures the machine. Wait for it to settle." >&2
  exit 1
fi

# Swap in use means pages have already been evicted, and on a machine whose swap is zram the
# compressor competes for the same cores a probe is being timed on. Sizes do not care; a
# nanosecond does.
swap_mib=$(awk '/SwapTotal/ { t = $2 } /SwapFree/ { f = $2 } END { print int((t - f) / 1024) }' /proc/meminfo)
if [ "$swap_mib" -gt "${SIB_SWAP_CEILING_MIB:-64}" ]; then
  echo "refusing: ${swap_mib} MiB of swap is in use -- something has already been evicted, and a" >&2
  echo "latency number measured over it is the swap's. Free memory or reboot, then re-run." >&2
  exit 1
fi

# Two DIMMs of different size interleave only over twice the smaller one; the rest is single
# channel, and which half a buffer lands in is the kernel's choice. Headroom is what keeps a
# campaign out of the half it did not measure last time.
avail_gib=$(awk '/MemAvailable/ { printf "%.1f", $2 / 1048576 }' /proc/meminfo)
if awk -v a="$avail_gib" -v n="${SIB_FREE_GIB:-12}" 'BEGIN { exit !(a < n) }'; then
  echo "refusing: ${avail_gib} GiB available, under ${SIB_FREE_GIB:-12} GiB -- a campaign this" >&2
  echo "close to the edge measures reclaim. Close what is holding memory, or reboot." >&2
  exit 1
fi

if [ ! -x /usr/bin/time ]; then
  echo "refusing: /usr/bin/time (GNU time) is needed for each process's peak memory" >&2
  exit 1
fi
for binary in "$c2" "$xcdat"; do
  if [ ! -x "$binary" ]; then
    echo "refusing: $binary is missing; run harness/build.sh" >&2
    exit 1
  fi
done
for pin in "${PINS[@]}"; do
  read -r path _ pinned <<< "$pin"
  at=$(git -C "$frontier/$path" rev-parse HEAD 2> /dev/null || echo none)
  if [ "$at" != "$pinned" ]; then
    echo "refusing: $path is at $at, not the pinned $pinned; run harness/build.sh" >&2
    exit 1
  fi
done
for stem in "${stems[@]}"; do
  if [ ! -r "$corpora/$stem.txt" ]; then
    echo "refusing: no corpus file $corpora/$stem.txt; see sib/corpora.py" >&2
    exit 1
  fi
done
uv run --no-sync python sib/corpora.py verify
# The tree is clean, so this is the commit the artifact is named after.
cargo build --release --locked --quiet --manifest-path harness/lex/Cargo.toml

host=$(uname -n)
ticks=$(getconf CLK_TCK)
log=results/$table-$(date +%F)-$host-$commit.log

# One process a structure, labelled as tables.py reads them.
processes=()
for kind in dict32 dict256 dict1024 string; do
  processes+=("lexindex $kind")
done
# C²'s fourth argument is the depth of the recursion its paper ablates; for the MARISA baseline it is
# the number of tries less one, so depth 0 is a one-level MARISA and depth 2 marisa's 3-try default.
for run in "0 0" "0 1" "0 2" "1 0" "1 1" "1 2" "2 0" "2 1" "2 2" "3 0" "4 0" "5 0" "5 1" "5 2" \
  "6 0" "7 0" "8 0"; do
  processes+=("c2 case ${run% *} rec ${run#* }")
done
for type in 7 8 15 16; do
  processes+=("xcdat $type")
done

header() {
  local l2 l3 changed
  l2=$(getconf LEVEL2_CACHE_SIZE 2> /dev/null || true)
  l3=$(getconf LEVEL3_CACHE_SIZE 2> /dev/null || true)
  echo "frontier campaign"
  echo "date: $(date -Is)"
  echo "host: $host"
  echo "commit: $commit"
  echo "table: $table"
  # The published crate the harness depends on, read from its own lockfile -- lexindex is a
  # pinned competitor here like every other, not the repository this runs in.
  echo "lexindex: $(awk '/^name = "lexindex"$/ { getline; gsub(/[version = "]/, ""); print; exit }' \
    harness/lex/Cargo.lock)"
  echo "kernel: $(uname -srm)"
  echo "cpu: $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | xargs)"
  echo "cores/threads: $(grep -m1 'cpu cores' /proc/cpuinfo | cut -d: -f2 | xargs) / $(nproc --all)"
  echo "caches: L2 $((${l2:-0} / 1024)) KiB, L3 $((${l3:-0} / 1024)) KiB"
  if [ -r /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor ]; then
    echo "governor: $(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor)"
  fi
  if [ -r /sys/kernel/mm/transparent_hugepage/enabled ]; then
    echo "transparent hugepages: $(cat /sys/kernel/mm/transparent_hugepage/enabled)"
  fi
  echo "compiler: $(c++ --version | head -1)"
  echo "rustc: $(rustc --version)"
  echo "load at start: $(cut -d' ' -f1-3 /proc/loadavg)"
  # A machine with two unequal DIMMs interleaves only part of its memory, so how much was free
  # says which half a campaign is likely to have run in. Swap in use says the answer is neither.
  echo "memory: $(awk '/MemTotal/ { printf "%.1f GiB total", $2 / 1048576 }' /proc/meminfo), \
$(awk '/MemAvailable/ { printf "%.1f available", $2 / 1048576 }' /proc/meminfo)"
  echo "swap in use: ${swap_mib} MiB"
  # Unequal modules interleave only across twice the smaller one and differ in rank, and neither
  # shows in any counter a benchmark can read. Recorded when the run has the rights to read it,
  # and named as absent when it does not -- an unstated memory layout is a missing variable, not a
  # neutral one.
  if layout=$(dmidecode -t 17 2>/dev/null | awk '
      /^\tBank Locator:/ { sub(/^\tBank Locator: */, ""); sub(/ *$/, ""); bank = $0; next }
      /^\tSize:/ && $2 != "No" { size = $2 $3; next }
      /^\tRank:/ { printf "%s %s rank %s; ", bank, size, $2 }') && [ -n "$layout" ]; then
    echo "memory layout: ${layout%; }"
  else
    echo "memory layout: not read (needs root)"
  fi
  echo "rounds: $rounds, even rounds in the reverse order"
  echo "quiet before each process: under $QUIET_CPUS busy CPUs for 1 s"
  echo "clock ticks: $ticks"
  echo "address space cap: $ADDRESS_SPACE_KB KB"
  echo "timeout: $limit s a process"
  for pin in "${PINS[@]}"; do
    read -r path url pinned <<< "$pin"
    changed=$(git -C "$frontier/$path" status --porcelain --untracked-files=no | awk '{ print $2 }' |
      paste -sd, -)
    echo "pin $path: ${pinned:0:12} $url${changed:+ (modified: $changed)}"
  done
  for path in c2/lib/ds2i/succinct c2/lib/sdsl-lite/external/googletest \
    c2/lib/sdsl-lite/external/libdivsufsort; do
    echo "pin $path: $(git -C "$frontier/$path" rev-parse HEAD | cut -c1-12) (gitlink)"
  done
  echo "pin coco adapted headers: ${COCO_COMMIT:0:12} https://github.com/aboffa/CoCo-trie (by sha256)"
}

# CPU time every CPU has spent busy since boot, in clock ticks: user, nice, system, irq, softirq and
# steal, without idle and iowait.
busy_ticks() { awk '/^cpu / { print $2 + $3 + $4 + $7 + $8 + $9; exit }' /proc/stat; }

quiet() {
  local waited=0 before
  while :; do
    before=$(busy_ticks)
    sleep 1
    if awk -v d="$(($(busy_ticks) - before))" -v t="$ticks" -v c="$QUIET_CPUS" \
      'BEGIN { exit !(d / t < c) }'; then
      return
    fi
    waited=$((waited + 1))
    if [ "$waited" -ge "$SETTLE_SECONDS" ]; then
      echo "refusing: other work kept $QUIET_CPUS CPUs busy for $SETTLE_SECONDS s" >&2
      exit 1
    fi
  done
}

# One process, once the machine is quiet: its own output, its wall and CPU time and peak memory from
# GNU time, the CPU time the whole machine spent meanwhile, and its exit status, left in `status`.
measure() {
  local label=$1 before
  shift
  quiet
  echo "--- $label   load $(cut -d' ' -f1-3 /proc/loadavg)"
  before=$(busy_ticks)
  status=0
  /usr/bin/time -f '[time %e s, user %U s, sys %S s, maxrss %M KB]' timeout "$limit" "$@" 2>&1 ||
    status=$?
  echo "[busy $(($(busy_ticks) - before)) jiffies]"
  echo "[exit $status]"
}

invoke() {
  local label=$1 file=$2 tool a b d
  read -r tool a b _ d <<< "$label"
  case "$tool" in
    lexindex) measure "$label" "$lex" "$file" "$a" ;;
    c2) measure "$label" "$c2" "$file" "$b" 0 "$d" 0 ;;
    xcdat) measure "$label" "$xcdat" "$file" "$a" ;;
  esac
}

reversed() {
  local i
  for ((i = $#; i > 0; i--)); do
    printf '%s\n' "${!i}"
  done
}

campaign() {
  local round stem file label key
  local -a stem_order process_order
  local -A failed=()
  header
  ulimit -v "$ADDRESS_SPACE_KB"
  # A crashing competitor would otherwise be dumped through systemd-coredump, which compresses the
  # whole address space while the next processes are timed: CoCo-trie's aborts at 1 M keys left 1 to
  # 2.5 GB of zstd each and a load average of 3.
  ulimit -c 0
  for ((round = 1; round <= rounds; round++)); do
    stem_order=("${stems[@]}")
    process_order=("${processes[@]}")
    if [ $((round % 2)) -eq 0 ]; then
      mapfile -t stem_order < <(reversed "${stems[@]}")
      mapfile -t process_order < <(reversed "${processes[@]}")
    fi
    for stem in "${stem_order[@]}"; do
      file=$corpora/$stem.txt
      printf '\n##### %s (%s lines, %s bytes)   round %d/%d   %s\n' "$stem" "$(wc -l < "$file")" \
        "$(stat -c %s "$file")" "$round" "$rounds" "$(date -Is)"
      for label in "${process_order[@]}"; do
        key="$stem $label"
        # A crash here is a property of the structure and the corpus, not of the round.
        if [ -n "${failed[$key]:-}" ]; then
          echo "--- $label   skipped: ${failed[$key]}"
          continue
        fi
        invoke "$label" "$file"
        if [ "$status" -ne 0 ]; then
          failed[$key]="exit $status in round $round"
        fi
      done
    done
  done
  echo
  echo "campaign done $(date -Is), load $(cut -d' ' -f1-3 /proc/loadavg)"
}

campaign 2>&1 | tee "$log"
uv run --no-sync python harness/tables.py --json "$log"
git status --porcelain --untracked-files=normal -- results
