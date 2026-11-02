// RearCodedArray (Vinciguerra) for harness/baselines.py: read one key a line,
// sort and deduplicate as harness/baselines does, then build each configuration
// of the library's two layouts, headers inside the blocks or in an area of their
// own, check every key both ways, and print its size. Nothing is timed. The grid
// is the block sizes the library's own example builds, in bytes and not in keys
// (a block ends when it has reached that many), and one step past them, 8192,
// where a block holds about the 1024 keys of the campaign's largest lexindex block.
//
// The size is `size_in_bytes()`, its arrays and its object: the library writes
// no file, so, like sux's in harness/baselines, it holds no framing.
//
// A key that does not come back from `access` stops the run: a size of that
// would not be a size of the keys. A wrong `rank` is counted and printed, not
// fatal, because the library has one: `block_rank` compares bytes as `char`,
// signed on x86-64, against keys sorted as unsigned bytes, so keys that hold
// bytes past ASCII can rank wrong. The array still holds them, and an unsigned
// `char` is no way round it, since the other layout's `decode_int` needs a signed one.
//
// `rca_baselines <keys.txt>` prints `<keys> keys, <raw> raw bytes`, then a CSV
// row a configuration: `structure,parameter,bytes,rank_wrong`.
#include <algorithm>
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
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

// The library allocates its decoding buffer one byte short of the longest key
// and its NUL, and `rank` fills it. Every array-new here gets that byte, and no
// size moves: `size_in_bytes()` counts the vectors and strings, and not the buffer.
void *operator new[](std::size_t bytes) {
  void *memory = std::malloc(bytes + 1);
  if (memory == nullptr) {
    throw std::bad_alloc();
  }
  return memory;
}
void operator delete[](void *memory) noexcept { std::free(memory); }
void operator delete[](void *memory, std::size_t) noexcept { std::free(memory); }
void operator delete(void *memory) noexcept { std::free(memory); }
void operator delete(void *memory, std::size_t) noexcept { std::free(memory); }

// Each of the two headers defines the same names, so each gets a namespace. The
// headers they include are above, and their guards keep them there.
namespace inside {
#include "rear_coded_array.hpp"
}
namespace apart {
#include "rear_coded_array.separate_headers.hpp"
}

namespace {

template <typename Array>
void measure(const std::vector<std::string> &keys, const char *name,
             std::size_t block_bytes) {
  // The constructor prints its statistics to stdout, which is this program's CSV.
  std::cout.setstate(std::ios::failbit);
  const Array array(keys.begin(), keys.end(), block_bytes);
  std::cout.clear();
  std::size_t longest = 0;
  for (const auto &key : keys) {
    longest = std::max(longest, key.size());
  }
  std::vector<char> buffer(longest + 1);
  std::size_t rank_wrong = 0;
  for (std::size_t i = 0; i < keys.size(); ++i) {
    array.access(i, buffer.data());
    if (keys[i] != buffer.data()) {
      std::fprintf(stderr, "%s, %zu bytes: key %zu, %s: access gave %s\n", name,
                   block_bytes, i, keys[i].c_str(), buffer.data());
      std::exit(1);
    }
    // `rank` counts the keys at or before a string, so the i-th key's is i + 1.
    rank_wrong += array.rank(keys[i]) != i + 1;
  }
  std::printf("%s,block %zu bytes,%zu,%zu\n", name, block_bytes, array.size_in_bytes(),
              rank_wrong);
  std::fflush(stdout);
}

} // namespace

int main(int argc, char **argv) {
  if (argc != 2) {
    std::fprintf(stderr, "usage: rca_baselines <keys.txt>\n");
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
  std::size_t raw_bytes = 0;
  for (const auto &key : keys) {
    raw_bytes += key.size();
  }

  std::printf("%zu keys, %zu raw bytes\n", keys.size(), raw_bytes);
  std::printf("structure,parameter,bytes,rank_wrong\n");
  for (const std::size_t block_bytes : {32, 128, 512, 2048, 8192}) {
    measure<inside::RearCodedArray>(keys, "RearCodedArray", block_bytes);
    measure<apart::RearCodedArray>(keys, "RearCodedArray (headers apart)", block_bytes);
  }
  return 0;
}
