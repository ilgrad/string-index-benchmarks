// libCSD's front-coded dictionaries under the campaign's protocol, for
// `harness/run.sh --baselines`: read one key a line, sort and deduplicate,
// build one configuration, write the file its `save()` writes and load that
// file back, then time the loaded dictionary as xcdat_frontier times XCDAT 15.
// HTFC's constructor leaves it unable to `extract`, and the library's own tools
// only ever query a loaded file, so the build is timed and the queries run on
// the load.
//
// `locate` (a key to its id) looks every key up once in one `std::mt19937{2}`
// shuffle -- a single timed pass with no warm-up, through a non-inlined loop --
// then three chained passes, each query's slot waiting on the answer before it.
// `extract` (an id to its key) then does the same over the same shuffle of the
// ids, each string the library allocates freed inside the loop, as its own
// `Test` tool frees it. Given a probe count, every pass takes that many from
// the front of the same shuffle instead of every key. A wrong answer stops the
// run before a time is printed: a time of that would not be a time of the keys.
//
// The pinned source is not patched. The defect that corrupts memory in every
// run is padded as libcsd_baselines pads it; the others are cells.
//
// `libcsd_frontier <keys.txt> <PFC|RPFC|HTFC|HHTFC|RPHTFC> <bucket> [probes]`
// prints `probes: <p> of <n>`, then `build_ms,size_mib,latency_ns` with the
// cold `locate` pass, `chained mean / min` for the chained ones, and
// `extract cold <ns>, chained mean <ns> / min <ns>`.
#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <new>
#include <random>
#include <string>
#include <unistd.h>
#include <utility>
#include <vector>

// RPFC's and RPHTFC's constructors write one `size_t` past `beginnings` where
// the number of keys is a multiple of the bucket size; see
// libcsd_baselines.cpp. Every allocation here gets the eight bytes it lands in.
void *operator new(std::size_t bytes) {
  void *memory = std::malloc(bytes + sizeof(std::size_t));
  if (memory == nullptr) {
    throw std::bad_alloc();
  }
  return memory;
}
void operator delete(void *memory) noexcept { std::free(memory); }
void operator delete(void *memory, std::size_t) noexcept { std::free(memory); }

#include "StringDictionary.h"
#include "iterators/IteratorDictStringPlain.h"

namespace {

using Clock = std::chrono::high_resolution_clock;

// What the process exits with where an answer is wrong.
constexpr int WRONG_ANSWER = 3;

// libCSD's input: the sorted keys, each ended by a NUL, in one array that the
// iterator owns and the constructors free.
IteratorDictString *input_of(const std::vector<std::string> &keys) {
  std::size_t bytes = 0;
  for (const auto &key : keys) {
    bytes += key.size() + 1;
  }
  auto *text = new uchar[bytes];
  std::size_t at = 0;
  for (const auto &key : keys) {
    std::memcpy(text + at, key.c_str(), key.size() + 1);
    at += key.size() + 1;
  }
  return new IteratorDictStringPlain(text, bytes);
}

StringDictionary *make(const std::string &coding, IteratorDictString *it,
                       uint bucket) {
  if (coding == "PFC")
    return new StringDictionaryPFC(it, bucket);
  if (coding == "RPFC")
    return new StringDictionaryRPFC(it, bucket);
  if (coding == "HTFC")
    return new StringDictionaryHTFC(it, bucket);
  if (coding == "HHTFC")
    return new StringDictionaryHHTFC(it, bucket);
  return new StringDictionaryRPHTFC(it, bucket);
}

uchar *bytes_of(const std::string &key) {
  return reinterpret_cast<uchar *>(const_cast<char *>(key.data()));
}

double ns_per_query(Clock::time_point start, std::size_t queries) {
  return std::chrono::duration<double, std::nano>(Clock::now() - start)
             .count() /
         static_cast<double>(queries);
}

// Ids count from 1, so a pass over every key sums to n(n + 1)/2.
std::uint64_t __attribute__((noinline))
locate_all(StringDictionary &dict, const std::vector<std::string> &queries) {
  std::uint64_t sum = 0;
  for (const auto &key : queries) {
    sum += dict.locate(bytes_of(key), key.size());
  }
  return sum;
}

// Each query's slot chained through the answer before it (`& zero`, `zero`
// opaque): no two lookups overlap.
std::uint64_t __attribute__((noinline))
locate_chained(StringDictionary &dict, const std::vector<std::string> &queries,
               std::size_t zero) {
  std::uint64_t sum = 0;
  uint prev = 0;
  for (std::size_t i = 0; i < queries.size(); i++) {
    const auto &key = queries[i + (prev & zero)];
    prev = dict.locate(bytes_of(key), key.size());
    sum += prev;
  }
  return sum;
}

// The lengths of the strings given back, and their first bytes: over every id,
// the same sums as over the keys.
std::uint64_t __attribute__((noinline))
extract_all(StringDictionary &dict, const std::vector<std::size_t> &ids) {
  std::uint64_t sum = 0;
  for (const auto id : ids) {
    uint length = 0;
    uchar *back = dict.extract(id, &length);
    sum += length + (back == nullptr ? 0 : back[0]);
    delete[] back;
  }
  return sum;
}

std::uint64_t __attribute__((noinline))
extract_chained(StringDictionary &dict, const std::vector<std::size_t> &ids,
                std::size_t zero) {
  std::uint64_t sum = 0;
  uint length = 0;
  for (std::size_t i = 0; i < ids.size(); i++) {
    uchar *back = dict.extract(ids[i + (length & zero)], &length);
    sum += length + (back == nullptr ? 0 : back[0]);
    delete[] back;
  }
  return sum;
}

// Where a sum is off, the first key that does not come back, found outside
// every timed pass.
int wrong(StringDictionary &dict, const std::vector<std::string> &keys,
          const char *label, const char *what) {
  for (std::size_t i = 0; i < keys.size(); ++i) {
    const uint id = dict.locate(bytes_of(keys[i]), keys[i].size());
    uint length = 0;
    uchar *back = dict.extract(i + 1, &length);
    const bool same =
        back != nullptr &&
        keys[i].compare(0, std::string::npos, reinterpret_cast<char *>(back),
                        length) == 0;
    delete[] back;
    if (id != i + 1 || !same) {
      std::printf("%s wrong answer: %s, first at key %zu: locate gave %u%s\n",
                  label, what, i + 1, id,
                  same ? "" : ", extract another string");
      return WRONG_ANSWER;
    }
  }
  std::printf(
      "%s wrong answer: %s, though every key comes back one at a time\n", label,
      what);
  return WRONG_ANSWER;
}

} // namespace

int main(int argc, char **argv) {
  const std::vector<std::string> codings = {"PFC", "RPFC", "HTFC", "HHTFC",
                                            "RPHTFC"};
  if ((argc != 4 && argc != 5) ||
      std::find(codings.begin(), codings.end(), argv[2]) == codings.end() ||
      std::atoi(argv[3]) < 2 || (argc == 5 && std::atol(argv[4]) < 1)) {
    std::fprintf(stderr, "usage: libcsd_frontier <keys.txt> "
                         "<PFC|RPFC|HTFC|HHTFC|RPHTFC> <bucket> [probes]\n");
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
  const auto bucket = static_cast<uint>(std::atoi(argv[3]));
  const std::string label =
      std::string("libCSD ") + argv[2] + " bucket " + argv[3];

  auto start = Clock::now();
  StringDictionary *built = make(argv[2], input_of(keys), bucket);
  const double build_ms =
      std::chrono::duration<double, std::milli>(Clock::now() - start).count();

  // Made here and removed as soon as it is read back.
  char path[] = "/tmp/libcsd_frontier.XXXXXX";
  const int descriptor = mkstemp(path);
  if (descriptor < 0) {
    std::perror("mkstemp");
    return 1;
  }
  close(descriptor);
  std::ofstream out(path, std::ios::binary);
  built->save(out);
  out.close();
  delete built;
  std::ifstream in(path, std::ios::binary);
  StringDictionary *dict = StringDictionary::load(in, 0);
  const auto bytes =
      static_cast<std::size_t>(in.seekg(0, std::ios::end).tellg());
  in.close();
  std::remove(path);
  if (dict == nullptr) {
    std::printf("%s wrong answer: its own file does not load\n", label.c_str());
    return WRONG_ANSWER;
  }
  const double size_mib = static_cast<double>(bytes) / (1024.0 * 1024.0);
  std::printf("build time: %f ms\n", build_ms);
  std::printf("space cost: %zu bytes, %f B/key\n", bytes,
              static_cast<double>(bytes) / static_cast<double>(keys.size()));
  std::fflush(stdout);

  // The shuffle is of every key, and a run given fewer probes takes the first
  // of it. The same seed shuffles the ids, so the i-th id is the i-th query's.
  const std::size_t probes =
      argc == 5 ? std::min<std::size_t>(std::atol(argv[4]), keys.size())
                : keys.size();
  std::vector<std::string> queries = keys;
  std::shuffle(queries.begin(), queries.end(), std::mt19937{2});
  queries.resize(probes);
  std::vector<std::size_t> ids(keys.size());
  for (std::size_t i = 0; i < ids.size(); i++) {
    ids[i] = i + 1;
  }
  std::shuffle(ids.begin(), ids.end(), std::mt19937{2});
  ids.resize(probes);
  std::uint64_t located = 0, returned = 0;
  for (const auto id : ids) {
    located += id;
    returned +=
        keys[id - 1].size() + static_cast<unsigned char>(keys[id - 1][0]);
  }
  std::printf("probes: %zu of %zu\n", probes, keys.size());
  std::fflush(stdout);
  volatile std::size_t opaque_zero = 0;
  const std::size_t zero = opaque_zero;

  start = Clock::now();
  std::uint64_t sum = locate_all(*dict, queries);
  const double locate_ns = ns_per_query(start, queries.size());
  double chained_sum = 0, chained_least = 0;
  for (int pass = 0; pass < 3; pass++) {
    start = Clock::now();
    sum += locate_chained(*dict, queries, zero);
    const double ns = ns_per_query(start, queries.size());
    chained_sum += ns;
    chained_least = pass == 0 ? ns : std::min(chained_least, ns);
  }
  if (sum != 4 * located) {
    return wrong(*dict, keys, label.c_str(),
                 "a locate pass summed to another id total");
  }

  start = Clock::now();
  sum = extract_all(*dict, ids);
  const double extract_ns = ns_per_query(start, ids.size());
  double extract_sum = 0, extract_least = 0;
  for (int pass = 0; pass < 3; pass++) {
    start = Clock::now();
    sum += extract_chained(*dict, ids, zero);
    const double ns = ns_per_query(start, ids.size());
    extract_sum += ns;
    extract_least = pass == 0 ? ns : std::min(extract_least, ns);
  }
  if (sum != 4 * returned) {
    return wrong(*dict, keys, label.c_str(),
                 "an extract pass gave back other strings");
  }

  std::printf("avg latency: %f ns\n", locate_ns);
  // `tables.py` reads the size back as MiB x 2^20: nine decimals keep it to the
  // byte.
  std::printf("%.3f,%.9f,%.3f\n", build_ms, size_mib, locate_ns);
  std::printf("chained mean %f / min %f ns\n", chained_sum / 3, chained_least);
  std::printf("extract cold %f ns, chained mean %f / min %f ns\n", extract_ns,
              extract_sum / 3, extract_least);
  delete dict;
  return 0;
}
