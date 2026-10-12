//! Front-coded string lists the frontier campaign does not run, sized over one corpus file: sux's
//! rear-coded list at three block ratios and fcsd's front-coded set at three bucket sizes, each up
//! to 256 keys a block. The keys are read, sorted and deduplicated as `frontier_lex`
//! reads them. Before its size is printed, every structure answers every key both ways, id to key
//! and key to id, so no size is one of a structure that does not hold the keys. Nothing is timed.
//!
//! `baselines <corpus.txt>` prints `<keys> keys, <raw> raw bytes`, then a CSV row a
//! configuration: `structure,parameter,bytes`. fcsd's bytes are `size_in_bytes()`, exactly what
//! `serialize_into` writes; the rear-coded list's are its `mem_size`, its arrays and fields
//! without a file's framing.
use std::io::BufRead;

use mem_dbg::{MemSize, SizeFlags};
use sux::dict::{RearCodedListBuilder, RearCodedListStr};
use sux::traits::{IndexedDict, IndexedSeq};

fn main() {
    let path = std::env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: baselines <keys.txt>");
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
    let raw: usize = keys.iter().map(String::len).sum();
    println!("{} keys, {raw} raw bytes", keys.len());
    println!("structure,parameter,bytes");

    for ratio in [16, 64, 256] {
        let mut builder = RearCodedListBuilder::<str, true>::new(ratio);
        for key in &keys {
            builder
                .try_push(key.as_str())
                .expect("sorted, distinct keys");
        }
        let list: RearCodedListStr = builder.build();
        for (id, key) in keys.iter().enumerate() {
            assert_eq!(
                list.get(id),
                *key,
                "rear-coded list, ratio {ratio}: id {id}"
            );
            assert_eq!(
                list.index_of(key.as_str()),
                Some(id),
                "rear-coded list, ratio {ratio}: {key:?}"
            );
        }
        println!(
            "sux RearCodedListStr,ratio {ratio},{}",
            list.mem_size(SizeFlags::default())
        );
    }

    for bucket in [8, 64, 256] {
        let set = fcsd::Set::with_bucket_size(&keys, bucket).expect("sorted, distinct keys");
        let (mut locator, mut decoder) = (set.locator(), set.decoder());
        for (id, key) in keys.iter().enumerate() {
            assert_eq!(
                decoder.run(id),
                key.as_bytes(),
                "fcsd, bucket {bucket}: id {id}"
            );
            assert_eq!(locator.run(key), Some(id), "fcsd, bucket {bucket}: {key:?}");
        }
        println!("fcsd Set,bucket {bucket},{}", set.size_in_bytes());
    }
}
