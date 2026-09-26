//! What a loaded lexindex index holds, for `harness/resident.py`: build each kind from a
//! one-key-per-line file as `frontier_lex` does, write its blob, then count the heap two loads keep
//! -- `from_bytes`, which copies the blob in, and `load_mmap`, which leaves the blob to the page
//! cache and allocates only what it derives beside it -- each measured after a pass of lookups, so
//! nothing derived lazily is missed. Prints `kind,keys,blob,from_bytes_heap,mmap_heap` a kind.
//!
//! The count is `malloc_usable_size` of every live allocation, as `harness/marisa_resident.cpp`
//! counts marisa's, so both sides include the allocator's rounding and neither its chunk headers.
//! Its own binary, so that `frontier_lex`'s timings never pay for a counting allocator. Nothing
//! is timed; a size is deterministic.
use std::alloc::{GlobalAlloc, Layout, System};
use std::io::BufRead;
use std::os::raw::c_void;
use std::sync::atomic::{AtomicUsize, Ordering::Relaxed};

use lexindex::{DictIndex, StringIndex};

unsafe extern "C" {
    fn malloc_usable_size(ptr: *mut c_void) -> usize;
}

struct Counting;
static LIVE: AtomicUsize = AtomicUsize::new(0);

// SAFETY: every call is forwarded to `System` unchanged; the counter only reads the pointers it
// returns, and `System` allocates through glibc's malloc family, which `malloc_usable_size` reads.
unsafe impl GlobalAlloc for Counting {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let ptr = unsafe { System.alloc(layout) };
        if !ptr.is_null() {
            LIVE.fetch_add(unsafe { malloc_usable_size(ptr.cast()) }, Relaxed);
        }
        ptr
    }
    unsafe fn alloc_zeroed(&self, layout: Layout) -> *mut u8 {
        let ptr = unsafe { System.alloc_zeroed(layout) };
        if !ptr.is_null() {
            LIVE.fetch_add(unsafe { malloc_usable_size(ptr.cast()) }, Relaxed);
        }
        ptr
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        LIVE.fetch_sub(unsafe { malloc_usable_size(ptr.cast()) }, Relaxed);
        unsafe { System.dealloc(ptr, layout) }
    }
    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        let old = unsafe { malloc_usable_size(ptr.cast()) };
        let moved = unsafe { System.realloc(ptr, layout, new_size) };
        if !moved.is_null() {
            LIVE.fetch_sub(old, Relaxed);
            LIVE.fetch_add(unsafe { malloc_usable_size(moved.cast()) }, Relaxed);
        }
        moved
    }
}

#[global_allocator]
static ALLOCATOR: Counting = Counting;

/// The heap `load` leaves behind once `probe` has run over what it returned.
fn kept<T>(load: impl FnOnce() -> T, probe: impl Fn(&T)) -> usize {
    let before = LIVE.load(Relaxed);
    let index = load();
    probe(&index);
    let after = LIVE.load(Relaxed);
    drop(index);
    after - before
}

trait Resident: Sized {
    fn build(keys: &[String], block: usize) -> Self;
    fn blob(&self) -> Vec<u8>;
    fn from_bytes(bytes: &[u8]) -> Self;
    /// # Safety
    /// Nothing may modify the file while the index maps it.
    unsafe fn load_mmap(path: &std::path::Path) -> Self;
    fn id(&self, key: &str) -> Option<u64>;
}

impl Resident for DictIndex {
    fn build(keys: &[String], block: usize) -> Self {
        DictIndex::build_with_block(keys, block).expect("dict build")
    }
    fn blob(&self) -> Vec<u8> {
        self.to_bytes()
    }
    fn from_bytes(bytes: &[u8]) -> Self {
        DictIndex::from_bytes(bytes).expect("dict from_bytes")
    }
    unsafe fn load_mmap(path: &std::path::Path) -> Self {
        unsafe { DictIndex::load_mmap(path) }.expect("dict load_mmap")
    }
    fn id(&self, key: &str) -> Option<u64> {
        DictIndex::id(self, key)
    }
}

impl Resident for StringIndex {
    fn build(keys: &[String], _: usize) -> Self {
        StringIndex::build(keys).expect("string build")
    }
    fn blob(&self) -> Vec<u8> {
        self.to_bytes()
    }
    fn from_bytes(bytes: &[u8]) -> Self {
        StringIndex::from_bytes(bytes).expect("string from_bytes")
    }
    unsafe fn load_mmap(path: &std::path::Path) -> Self {
        unsafe { StringIndex::load_mmap(path) }.expect("string load_mmap")
    }
    fn id(&self, key: &str) -> Option<u64> {
        StringIndex::id(self, key)
    }
}

fn measure<T: Resident>(keys: &[String], block: usize, kind: &str, file: &std::path::Path) {
    let blob = T::build(keys, block).blob();
    std::fs::write(file, &blob).expect("write the blob");
    // Every 97th key, so a load that derives anything on first use has derived it.
    let probe = |index: &T| {
        for (id, key) in keys.iter().enumerate().step_by(97) {
            assert_eq!(
                index.id(key),
                Some(id as u64),
                "{kind} answered a wrong id for {key:?}"
            );
        }
    };
    let owned = kept(|| T::from_bytes(&blob), probe);
    // SAFETY: the file is this process's own, written above, and nothing writes it while mapped.
    let mapped = kept(|| unsafe { T::load_mmap(file) }, probe);
    println!("{kind},{},{},{owned},{mapped}", keys.len(), blob.len());
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 3 {
        eprintln!("usage: resident <keys.txt> <dict32|dict256|dict1024|string>...");
        std::process::exit(2);
    }
    // Read, sorted and deduplicated exactly as `frontier_lex` reads a corpus, so a blob here is
    // the blob the campaign sized, byte for byte.
    let file = std::fs::File::open(&args[1]).expect("open");
    let mut keys: Vec<String> = std::io::BufReader::new(file)
        .lines()
        .map(|line| line.expect("read"))
        .filter(|line| !line.is_empty())
        .collect();
    keys.sort_unstable();
    keys.dedup();
    let blob = std::env::temp_dir().join(format!("sib-resident-{}.bin", std::process::id()));
    println!("kind,keys,blob,from_bytes_heap,mmap_heap");
    for kind in &args[2..] {
        match kind.as_str() {
            "dict32" => measure::<DictIndex>(&keys, 32, kind, &blob),
            "dict256" => measure::<DictIndex>(&keys, 256, kind, &blob),
            "dict1024" => measure::<DictIndex>(&keys, 1024, kind, &blob),
            "string" => measure::<StringIndex>(&keys, 0, kind, &blob),
            other => {
                eprintln!("unknown kind {other}");
                std::process::exit(2);
            }
        }
    }
    std::fs::remove_file(&blob).ok();
}
