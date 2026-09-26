// MARISA at every configuration that could make it smaller, for
// harness/marisa_floor.py: read one key a line, sort and deduplicate as
// xcdat_frontier.cpp does, then build a `marisa::Trie` from a `marisa::Keyset`,
// as C²'s MarisaWrapper does, once for each configuration of a fixed grid, and
// print its size. Nothing is timed. The campaign builds marisa at C²'s three
// configurations -- 1, 2 and 3 tries at the default cache -- and they come
// first, as the control; marisa's smallest trie takes the tiny cache and, on
// most corpora, more tries, so the grid then runs 1 to 32 tries at
// MARISA_TINY_CACHE. Tail mode and node order stay at marisa's defaults, text
// tails and weight order: at a million keys, label order builds the same bytes
// on every corpus of the set, and binary tails save at most 160 bytes where
// they save any.
//
// Two sizes a configuration. `io_size()` is what `save()` writes, the size a
// file costs; `total_size()` is what C²'s `space_cost()` counts, and so what
// the campaign's MARISA rows are. It leaves out a 16-byte header and every
// vector's length, padding and counts, 220 to 270 bytes a trie, and on some
// corpora that moves the smallest configuration by several tries.
#include <algorithm>
#include <cstddef>
#include <cstdio>
#include <fstream>
#include <string>
#include <utility>
#include <vector>

#include <marisa.h>

namespace {

// A fresh Keyset a build, as MarisaWrapper makes one: a key's id and its weight
// share a union, and a build writes ids over the weights the next build would
// order its nodes by.
void build(const std::vector<std::string> &keys, int tries, int cache,
           const char *cache_name) {
  marisa::Keyset keyset;
  for (const auto &key : keys) {
    keyset.push_back(key.c_str());
  }
  marisa::Trie trie;
  trie.build(keyset, tries | cache);
  std::printf("%s,%d,%zu,%zu,%zu\n", cache_name, tries, trie.num_tries(),
              trie.io_size(), trie.total_size());
}

} // namespace

int main(int argc, char **argv) {
  if (argc != 2) {
    std::fprintf(stderr, "usage: marisa_floor <keys.txt>\n");
    return 2;
  }
  std::ifstream file(argv[1]);
  if (!file) {
    std::fprintf(stderr, "cannot open %s\n", argv[1]);
    return 1;
  }
  std::vector<std::string> keys;
  std::size_t raw_bytes = 0;
  for (std::string key; std::getline(file, key);) {
    raw_bytes += key.size();
    keys.push_back(std::move(key));
  }
  std::sort(keys.begin(), keys.end());
  keys.erase(std::unique(keys.begin(), keys.end()), keys.end());

  std::printf("%zu keys, %zu raw bytes\n", keys.size(), raw_bytes);
  std::printf("cache,tries,tries_built,bytes_io,bytes_total\n");
  for (int tries = 1; tries <= 3; ++tries) {
    build(keys, tries, MARISA_DEFAULT_CACHE, "default");
  }
  for (int tries = 1; tries <= 32; ++tries) {
    build(keys, tries, MARISA_TINY_CACHE, "tiny");
  }
  return 0;
}
