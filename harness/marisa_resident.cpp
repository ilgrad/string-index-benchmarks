// What a loaded marisa::Trie holds, for harness/resident.py: read one key a
// line, sort and deduplicate as marisa_floor.cpp does, and for each
// configuration named on the command line build the trie, save it, then count
// the heap two loads keep -- `mmap()`, which leaves the file to the page cache,
// and `load()`, which reads all of it onto the heap -- the first after a pass
// of lookups. Nothing is timed.
//
// marisa allocates through operator new alone (`new (std::nothrow)` and its own
// vectors' `new[]`), so replacing the global operators sees all of it. The
// count is `malloc_usable_size` of every live allocation, as resident.rs counts
// lexindex's: the allocator's rounding on both sides, its chunk headers on
// neither.
//
//   marisa_resident <keys.txt> <tiny|default>:<tries>...
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <new>
#include <string>
#include <vector>

#include <malloc.h>
#include <unistd.h>

#include <marisa.h>

namespace {

long long live = 0;

void *counted(std::size_t size) noexcept {
  void *ptr = std::malloc(size ? size : 1);
  if (ptr != nullptr) {
    live += static_cast<long long>(malloc_usable_size(ptr));
  }
  return ptr;
}

void release(void *ptr) noexcept {
  if (ptr != nullptr) {
    live -= static_cast<long long>(malloc_usable_size(ptr));
    std::free(ptr);
  }
}

} // namespace

void *operator new(std::size_t size) {
  void *ptr = counted(size);
  if (ptr == nullptr) {
    throw std::bad_alloc();
  }
  return ptr;
}
void *operator new[](std::size_t size) { return operator new(size); }
void *operator new(std::size_t size, const std::nothrow_t &) noexcept {
  return counted(size);
}
void *operator new[](std::size_t size, const std::nothrow_t &) noexcept {
  return counted(size);
}
void operator delete(void *ptr) noexcept { release(ptr); }
void operator delete[](void *ptr) noexcept { release(ptr); }
void operator delete(void *ptr, std::size_t) noexcept { release(ptr); }
void operator delete[](void *ptr, std::size_t) noexcept { release(ptr); }
void operator delete(void *ptr, const std::nothrow_t &) noexcept {
  release(ptr);
}
void operator delete[](void *ptr, const std::nothrow_t &) noexcept {
  release(ptr);
}

int main(int argc, char **argv) {
  if (argc < 3) {
    std::fprintf(
        stderr,
        "usage: marisa_resident <keys.txt> <tiny|default>:<tries>...\n");
    return 2;
  }
  std::ifstream file(argv[1]);
  if (!file) {
    std::fprintf(stderr, "cannot open %s\n", argv[1]);
    return 1;
  }
  std::vector<std::string> keys;
  for (std::string key; std::getline(file, key);) {
    keys.push_back(std::move(key));
  }
  std::sort(keys.begin(), keys.end());
  keys.erase(std::unique(keys.begin(), keys.end()), keys.end());
  const std::string path = "/tmp/sib-marisa-resident-" +
                           std::to_string(static_cast<long>(getpid())) + ".bin";

  std::printf("%zu keys\n", keys.size());
  std::printf(
      "cache,tries,tries_built,bytes_io,bytes_total,mmap_heap,load_heap\n");
  for (int arg = 2; arg < argc; ++arg) {
    const char *colon = std::strchr(argv[arg], ':');
    if (colon == nullptr) {
      std::fprintf(stderr,
                   "a configuration is <tiny|default>:<tries>, not %s\n",
                   argv[arg]);
      return 2;
    }
    const std::string cache_name(argv[arg],
                                 static_cast<std::size_t>(colon - argv[arg]));
    const int tries = std::atoi(colon + 1);
    int cache = 0;
    if (cache_name == "tiny") {
      cache = MARISA_TINY_CACHE;
    } else if (cache_name == "default") {
      cache = MARISA_DEFAULT_CACHE;
    } else {
      std::fprintf(stderr, "unknown cache %s\n", cache_name.c_str());
      return 2;
    }

    std::size_t io = 0, total = 0, built = 0;
    {
      // A fresh Keyset a build, as marisa_floor.cpp makes one.
      marisa::Keyset keyset;
      for (const auto &key : keys) {
        keyset.push_back(key.c_str());
      }
      marisa::Trie trie;
      trie.build(keyset, tries | cache);
      io = trie.io_size();
      total = trie.total_size();
      built = trie.num_tries();
      trie.save(path.c_str());
    }
    long long mapped = 0, loaded = 0;
    {
      const long long before = live;
      marisa::Trie trie;
      trie.mmap(path.c_str());
      {
        // Every 97th key, as resident.rs probes; the agent's own state is gone
        // before the count is read.
        marisa::Agent agent;
        for (std::size_t i = 0; i < keys.size(); i += 97) {
          agent.set_query(keys[i].c_str(), keys[i].size());
          if (!trie.lookup(agent)) {
            std::fprintf(stderr, "a key is missing: %s\n", keys[i].c_str());
            return 1;
          }
        }
      }
      mapped = live - before;
    }
    {
      const long long before = live;
      marisa::Trie trie;
      trie.load(path.c_str());
      loaded = live - before;
    }
    std::printf("%s,%d,%zu,%zu,%zu,%lld,%lld\n", cache_name.c_str(), tries,
                built, io, total, mapped, loaded);
  }
  std::remove(path.c_str());
  return 0;
}
