//! Static maps from a string to a number that do not store the strings, sized over one corpus file:
//! constmap's `ConstMap` and `VerifiedConstMap` (binary fuse construction), and lexindex's
//! `ClosedHashIndex` and `CompactHashIndex` (a minimal perfect hash, with and without a
//! fingerprint a key), with lexindex's `PerfectHashIndex`, which stores the keys, as the exact
//! reference. The keys are read, sorted and deduplicated as `frontier_lex` reads them. Nothing is
//! timed.
//!
//! Before its size is printed, every structure answers every key: constmap's maps return the
//! key's rank, the value they were built with, and lexindex's indexes give the keys distinct ids
//! in `[0, n)`. Then each structure that can reject a key is asked once for each of `n` strings
//! that are not keys, and the count it accepts is printed beside its size: a fingerprint of `b`
//! bits accepts about `n / 2^b` of them.
//!
//! `maps <corpus.txt>` prints `<keys> keys, <raw> raw bytes`, then a CSV row a configuration:
//! `structure,parameter,bytes,absent_accepted`, the last empty for a structure that cannot reject
//! a key. Bytes are a file's: what `write_to` writes for constmap, `serialized_len()` for lexindex.
use std::io::BufRead;

use constmap::{ConstMap, NOT_FOUND, VerifiedConstMap};
use lexindex::{ClosedHashIndex, CompactHashIndex, PerfectHashIndex};

/// `n` strings that are not keys: each key with a byte appended, kept where the result is absent.
fn absent(keys: &[String]) -> Vec<String> {
    let mut out = Vec::with_capacity(keys.len());
    for suffix in ['\u{1}', '\u{2}', '\u{3}'] {
        for key in keys {
            if out.len() == keys.len() {
                return out;
            }
            let probe = format!("{key}{suffix}");
            if keys.binary_search(&probe).is_err() {
                out.push(probe);
            }
        }
    }
    out
}

/// Every id in `[0, n)` exactly once.
fn dense(ids: impl Iterator<Item = u32>, n: usize, what: &str) {
    let mut seen = vec![false; n];
    for id in ids {
        let slot = seen
            .get_mut(id as usize)
            .unwrap_or_else(|| panic!("{what}: id {id} outside [0, {n})"));
        assert!(!*slot, "{what}: id {id} given twice");
        *slot = true;
    }
}

fn main() {
    let path = std::env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: maps <keys.txt>");
        std::process::exit(2);
    });
    let file = std::fs::File::open(&path).expect("open");
    let mut keys: Vec<String> = std::io::BufReader::new(file)
        .lines()
        .map(|line| line.expect("read"))
        .filter(|line| !line.is_empty())
        .collect();
    keys.sort_unstable();
    keys.dedup();
    let n = keys.len();
    let raw: usize = keys.iter().map(String::len).sum();
    let strs: Vec<&str> = keys.iter().map(String::as_str).collect();
    let ranks: Vec<u64> = (0..n as u64).collect();
    let probes = absent(&keys);
    assert_eq!(probes.len(), n, "too few strings that are not keys");
    println!("{n} keys, {raw} raw bytes");
    println!("structure,parameter,bytes,absent_accepted");

    let map = ConstMap::new(&strs, &ranks).expect("constmap build");
    for (rank, key) in strs.iter().enumerate() {
        assert_eq!(map.map(key), rank as u64, "ConstMap: {key:?}");
    }
    let bytes = map.write_to(&mut std::io::sink()).expect("write");
    println!("constmap ConstMap,u64 value,{bytes},");
    drop(map);

    let map = VerifiedConstMap::new(&strs, &ranks).expect("constmap build");
    for (rank, key) in strs.iter().enumerate() {
        assert_eq!(map.map(key), rank as u64, "VerifiedConstMap: {key:?}");
    }
    let accepted = probes.iter().filter(|p| map.map(p) != NOT_FOUND).count();
    let bytes = map.write_to(&mut std::io::sink()).expect("write");
    println!("constmap VerifiedConstMap,u64 value + 64-bit check,{bytes},{accepted}");
    drop(map);

    let index = ClosedHashIndex::build(strs.iter().copied()).expect("lexindex build");
    dense(strs.iter().map(|k| index.id(k)), n, "ClosedHashIndex");
    println!("lexindex ClosedHashIndex,,{},", index.serialized_len());
    drop(index);

    for bits in [8, 16, 32, 64] {
        let index =
            CompactHashIndex::build_bits(strs.iter().copied(), bits).expect("lexindex build");
        let what = format!("CompactHashIndex, {bits} bits");
        dense(
            strs.iter().map(|k| {
                index
                    .id(k)
                    .unwrap_or_else(|| panic!("{what}: {k:?} missing"))
            }),
            n,
            &what,
        );
        let accepted = probes.iter().filter(|p| index.id(p).is_some()).count();
        let bytes = index.serialized_len().expect("size");
        println!("lexindex CompactHashIndex,fingerprint {bits} bits,{bytes},{accepted}");
    }

    let index = PerfectHashIndex::build(strs.iter().copied()).expect("lexindex build");
    for key in &strs {
        let id = index
            .id(key)
            .unwrap_or_else(|| panic!("PerfectHashIndex: {key:?} missing"));
        assert_eq!(index.key(id), Some(*key), "PerfectHashIndex: id {id}");
    }
    let accepted = probes.iter().filter(|p| index.id(p).is_some()).count();
    assert_eq!(
        accepted, 0,
        "PerfectHashIndex accepted a string that is not a key"
    );
    let bytes = index.serialized_len().expect("size");
    println!("lexindex PerfectHashIndex,stores the keys,{bytes},{accepted}");
}
