// RearCodedArray (Vinciguerra) under the campaign's protocol, for
// `harness/run.sh --baselines`: read one key a line, sort and deduplicate,
// build one layout at one block size, then time it as xcdat_frontier times
// XCDAT 15. `rank` (a key to its id) looks every key up once in one
// `std::mt19937{2}` shuffle -- a single timed pass with no warm-up, through a
// non-inlined loop -- then three chained passes, each query's slot waiting on
// the answer before it. `access` (an id to its key) then does the same over the
// same shuffle of the ids, into one buffer.
//
// The size is `size_in_bytes()`, as in rca_baselines: the library writes no
// file.
//
// A key that does not come back from `access` stops the run before a time is
// printed. A wrong `rank` does not, as it does not in rca_baselines: the pinned
// `block_rank` compares bytes as signed `char` against keys sorted as unsigned
// bytes, so keys past ASCII can rank wrong, and the source is not patched. The
// run counts them outside every timed pass and prints the count, and a chained
// pass has to give the same answers as the cold one.
//
// `rca_frontier <keys.txt> <inside|apart> <block bytes>` prints
// `probes: <n> of <n>`, then `build_ms,size_mib,latency_ns` with the cold
// `rank` pass, `chained mean / min` for the chained ones, `extract cold <ns>,
// chained mean <ns> / min <ns>` for `access`, and `rank wrong: <count> of
// <keys>` where any is.
#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <new>
#include <random>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

// The library allocates its decoding buffer one byte short of the longest key
// and its NUL, and `rank` fills it; see rca_baselines.cpp.
void *operator new[](std::size_t bytes) {
  void *memory = std::malloc(bytes + 1);
  if (memory == nullptr) {
    throw std::bad_alloc();
  }
  return memory;
}
void operator delete[](void *memory) noexcept { std::free(memory); }
void operator delete[](void *memory, std::size_t) noexcept {
  std::free(memory);
}
void operator delete(void *memory) noexcept { std::free(memory); }
void operator delete(void *memory, std::size_t) noexcept { std::free(memory); }

// Each of the two headers defines the same names, so each gets a namespace.
namespace inside {
#include "rear_coded_array.hpp"
}
namespace apart {
#include "rear_coded_array.separate_headers.hpp"
}

namespace {

using Clock = std::chrono::high_resolution_clock;

double ns_per_query(Clock::time_point start, std::size_t queries) {
  return std::chrono::duration<double, std::nano>(Clock::now() - start)
             .count() /
         static_cast<double>(queries);
}

// `rank` counts the keys at or before a string, so a pass over every key sums
// to n(n + 1)/2 where every rank is right.
template <class Array>
std::uint64_t __attribute__((noinline))
rank_all(const Array &array, const std::vector<std::string> &queries) {
  std::uint64_t sum = 0;
  for (const auto &key : queries) {
    sum += array.rank(key);
  }
  return sum;
}

// Each query's slot chained through the answer before it (`& zero`, `zero`
// opaque): no two lookups overlap.
template <class Array>
std::uint64_t __attribute__((noinline))
rank_chained(const Array &array, const std::vector<std::string> &queries,
             std::size_t zero) {
  std::uint64_t sum = 0;
  std::size_t prev = 0;
  for (std::size_t i = 0; i < queries.size(); i++) {
    prev = array.rank(queries[i + (prev & zero)]);
    sum += prev;
  }
  return sum;
}

// The lengths of the strings given back, and their first bytes: over every id,
// the same sums as over the keys. `access` returns one past the NUL it writes.
template <class Array>
std::uint64_t __attribute__((noinline))
access_all(const Array &array, const std::vector<std::size_t> &ids,
           char *buffer) {
  std::uint64_t sum = 0;
  for (const auto id : ids) {
    const char *end = array.access(id, buffer);
    sum += static_cast<std::size_t>(end - buffer - 1) +
           static_cast<unsigned char>(buffer[0]);
  }
  return sum;
}

template <class Array>
std::uint64_t __attribute__((noinline))
access_chained(const Array &array, const std::vector<std::size_t> &ids,
               char *buffer, std::size_t zero) {
  std::uint64_t sum = 0;
  std::size_t length = 0;
  for (std::size_t i = 0; i < ids.size(); i++) {
    const char *end = array.access(ids[i + (length & zero)], buffer);
    length = static_cast<std::size_t>(end - buffer - 1);
    sum += length + static_cast<unsigned char>(buffer[0]);
  }
  return sum;
}

template <class Array>
int run(const std::vector<std::string> &keys, const char *name,
        std::size_t block_bytes) {
  // The constructor prints its statistics to stdout, which is this program's
  // output.
  std::cout.setstate(std::ios::failbit);
  auto start = Clock::now();
  const Array array(keys.begin(), keys.end(), block_bytes);
  const double build_ms =
      std::chrono::duration<double, std::milli>(Clock::now() - start).count();
  std::cout.clear();
  const std::size_t bytes = array.size_in_bytes();
  const double size_mib = static_cast<double>(bytes) / (1024.0 * 1024.0);
  std::printf("build time: %f ms\n", build_ms);
  std::printf("space cost: %zu bytes, %f B/key\n", bytes,
              static_cast<double>(bytes) / static_cast<double>(keys.size()));
  std::fflush(stdout);

  const std::uint64_t n = keys.size();
  std::size_t longest = 0;
  std::uint64_t returned = 0;
  for (const auto &key : keys) {
    longest = std::max(longest, key.size());
    returned += key.size() + static_cast<unsigned char>(key[0]);
  }
  std::vector<char> buffer(longest + 1);
  std::vector<std::string> queries = keys;
  std::shuffle(queries.begin(), queries.end(), std::mt19937{2});
  std::vector<std::size_t> ids(keys.size());
  for (std::size_t i = 0; i < ids.size(); i++) {
    ids[i] = i;
  }
  std::shuffle(ids.begin(), ids.end(), std::mt19937{2});
  std::printf("probes: %zu of %zu\n", ids.size(), keys.size());
  std::fflush(stdout);
  volatile std::size_t opaque_zero = 0;
  const std::size_t zero = opaque_zero;

  start = Clock::now();
  const std::uint64_t ranked = rank_all(array, queries);
  const double rank_ns = ns_per_query(start, queries.size());
  double chained_sum = 0, chained_least = 0;
  for (int pass = 0; pass < 3; pass++) {
    start = Clock::now();
    const std::uint64_t again = rank_chained(array, queries, zero);
    const double ns = ns_per_query(start, queries.size());
    if (again != ranked) {
      std::printf("%s block %zu bytes wrong answer: a chained rank pass "
                  "differs from the cold one\n",
                  name, block_bytes);
      return 3;
    }
    chained_sum += ns;
    chained_least = pass == 0 ? ns : std::min(chained_least, ns);
  }

  start = Clock::now();
  std::uint64_t sum = access_all(array, ids, buffer.data());
  const double access_ns = ns_per_query(start, ids.size());
  double access_sum = 0, access_least = 0;
  for (int pass = 0; pass < 3; pass++) {
    start = Clock::now();
    sum += access_chained(array, ids, buffer.data(), zero);
    const double ns = ns_per_query(start, ids.size());
    access_sum += ns;
    access_least = pass == 0 ? ns : std::min(access_least, ns);
  }
  if (sum != 4 * returned) {
    for (std::size_t i = 0; i < keys.size(); ++i) {
      array.access(i, buffer.data());
      if (keys[i] != buffer.data()) {
        std::printf("%s block %zu bytes wrong answer: access gave another "
                    "string for key %zu\n",
                    name, block_bytes, i + 1);
        return 3;
      }
    }
    std::printf("%s block %zu bytes wrong answer: an access pass gave back "
                "other strings\n",
                name, block_bytes);
    return 3;
  }

  std::printf("avg latency: %f ns\n", rank_ns);
  // `tables.py` reads the size back as MiB x 2^20: nine decimals keep it to the
  // byte.
  std::printf("%.3f,%.9f,%.3f\n", build_ms, size_mib, rank_ns);
  std::printf("chained mean %f / min %f ns\n", chained_sum / 3, chained_least);
  std::printf("extract cold %f ns, chained mean %f / min %f ns\n", access_ns,
              access_sum / 3, access_least);
  if (ranked != n * (n + 1) / 2) {
    std::size_t rank_wrong = 0;
    for (std::size_t i = 0; i < keys.size(); ++i) {
      rank_wrong += array.rank(keys[i]) != i + 1;
    }
    std::printf("rank wrong: %zu of %zu\n", rank_wrong, keys.size());
  }
  return 0;
}

} // namespace

int main(int argc, char **argv) {
  const std::string_view layout = argc == 4 ? argv[2] : "";
  const long block_bytes = argc == 4 ? std::atol(argv[3]) : 0;
  if ((layout != "inside" && layout != "apart") || block_bytes < 1) {
    std::fprintf(
        stderr,
        "usage: rca_frontier <keys.txt> <inside|apart> <block bytes>\n");
    return 2;
  }
  std::ifstream file(argv[1]);
  if (!file) {
    std::fprintf(stderr, "cannot open %s\n", argv[1]);
    return 1;
  }
  std::vector<std::string> keys;
  for (std::string key; std::getline(file, key);) {
    if (!key.empty()) {
      keys.push_back(std::move(key));
    }
  }
  std::sort(keys.begin(), keys.end());
  keys.erase(std::unique(keys.begin(), keys.end()), keys.end());
  const auto block = static_cast<std::size_t>(block_bytes);
  if (layout == "inside") {
    return run<inside::RearCodedArray>(keys, "RearCodedArray", block);
  }
  return run<apart::RearCodedArray>(keys, "RearCodedArray (headers apart)",
                                    block);
}
