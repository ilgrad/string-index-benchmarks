// The front-coded dictionaries of libCSD (Martinez-Prieto et al., Information
// Systems 2016) for harness/baselines.py: read one key a line, sort and
// deduplicate as harness/baselines does, then build each configuration, write
// the file its `save()` writes, load that file back, check that the loaded one
// answers every key both ways, and print the file's size. Nothing is timed. The
// check runs on the loaded dictionary because HTFC's constructor leaves it
// unable to `extract`: the library's own tools only ever query a loaded file.
//
// The grid is the bucket sizes harness/baselines gives fcsd and one more, 1024,
// the largest block the campaign gives lexindex, over each coding the library
// has of the internal strings: PFC stores them plain, RPFC by Re-Pair; HTFC codes
// its headers by Hu-Tucker and its internal strings by Hu-Tucker, Huffman or
// Re-Pair (`Build 4 t|h|r`, the classes HTFC, HHTFC and RPHTFC).
//
// `libcsd_baselines <keys.txt>` prints `<keys> keys, <raw> raw bytes`, then a
// CSV row a configuration: `structure,parameter,bytes`.
#include <algorithm>
#include <cstddef>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <functional>
#include <string>
#include <unistd.h>
#include <utility>
#include <vector>

#include "StringDictionary.h"
#include "iterators/IteratorDictStringPlain.h"

namespace {

using Make = std::function<StringDictionary *(IteratorDictString *, uint)>;

// libCSD's input: the sorted keys, each ended by a NUL, in one array that the
// iterator owns and the constructors free.
IteratorDictString *iterator(const std::vector<std::string> &keys) {
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

// Ids count from 1. A key that does not come back is a broken structure, and a
// size of one would not be a size of the keys, so the run stops.
void check(StringDictionary &dict, const std::vector<std::string> &keys,
           const char *name, uint bucket) {
  for (std::size_t i = 0; i < keys.size(); ++i) {
    auto *key = reinterpret_cast<uchar *>(const_cast<char *>(keys[i].c_str()));
    const uint id = dict.locate(key, keys[i].size());
    uint length = 0;
    uchar *back = dict.extract(i + 1, &length);
    const bool same = back != nullptr &&
                      std::strcmp(reinterpret_cast<char *>(back), keys[i].c_str()) == 0;
    delete[] back;
    if (id != i + 1 || !same) {
      std::fprintf(stderr, "%s, bucket %u: key %zu, %s: locate gave %u%s\n", name,
                   bucket, i + 1, keys[i].c_str(), id,
                   same ? "" : ", and extract another string");
      std::exit(1);
    }
  }
}

// `getSize()` counts the arrays and leaves out the framing a file costs, so the
// size is the file's.
void measure(const std::vector<std::string> &keys, const char *name, uint bucket,
             const Make &make) {
  char path[] = "/tmp/libcsd_baselines.XXXXXX";
  const int descriptor = mkstemp(path);
  if (descriptor < 0) {
    std::perror("mkstemp");
    std::exit(1);
  }
  close(descriptor);
  StringDictionary *built = make(iterator(keys), bucket);
  std::ofstream out(path, std::ios::binary);
  built->save(out);
  out.close();
  delete built;

  std::ifstream in(path, std::ios::binary);
  StringDictionary *loaded = StringDictionary::load(in, 0);
  const auto bytes = static_cast<std::size_t>(in.seekg(0, std::ios::end).tellg());
  in.close();
  std::remove(path);
  if (loaded == nullptr) {
    std::fprintf(stderr, "%s, bucket %u: its own file does not load\n", name, bucket);
    std::exit(1);
  }
  check(*loaded, keys, name, bucket);
  std::printf("%s,bucket %u,%zu\n", name, bucket, bytes);
  std::fflush(stdout);
  delete loaded;
}

} // namespace

int main(int argc, char **argv) {
  if (argc != 2) {
    std::fprintf(stderr, "usage: libcsd_baselines <keys.txt>\n");
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
  std::printf("structure,parameter,bytes\n");
  const std::vector<std::pair<const char *, Make>> structures = {
      {"libCSD PFC",
       [](IteratorDictString *it, uint b) -> StringDictionary * {
         return new StringDictionaryPFC(it, b);
       }},
      {"libCSD RPFC",
       [](IteratorDictString *it, uint b) -> StringDictionary * {
         return new StringDictionaryRPFC(it, b);
       }},
      {"libCSD HTFC",
       [](IteratorDictString *it, uint b) -> StringDictionary * {
         return new StringDictionaryHTFC(it, b);
       }},
      {"libCSD HHTFC",
       [](IteratorDictString *it, uint b) -> StringDictionary * {
         return new StringDictionaryHHTFC(it, b);
       }},
      {"libCSD RPHTFC",
       [](IteratorDictString *it, uint b) -> StringDictionary * {
         return new StringDictionaryRPHTFC(it, b);
       }},
  };
  for (const auto &[name, make] : structures) {
    for (const uint bucket : {8u, 64u, 256u, 1024u}) {
      measure(keys, name, bucket, make);
    }
  }
  return 0;
}
