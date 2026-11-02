"""Every summary table in README.md, re-derived from the committed artifacts.

    uv run --no-project --python 3.11 python harness/readme_tables.py

The README promises that a table is a rendering of an artifact and that where the two disagree the
table is the bug. This keeps the promise: it renders each table from the JSON files it names, every
cell and every bold mark as "What gets bold" in the README's protocol section writes them, compares
line by line and exits 1 on the first run with any difference. A table in one of `SECTIONS` that
nothing here renders is a difference too. The prose around the tables is not checked, nor are the
tables that hold no measurement (the corpora, the entrants, the layout).
"""

from __future__ import annotations

import itertools
import json
import re
import sys
from pathlib import Path

from tables import REFERENCE

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

# A time wins only under this share of the other's, on the artifact's medians and not on the two
# printed digits: one process's memory placement alone moves a lookup 4-7 % on the machine behind
# the artifacts. A size is deterministic and takes no such band.
TIME_WIN = 0.95

CAMPAIGN = {
    "1m": "frontier-1m-2026-09-26-arz-be75a38.json",
    "10m": "frontier-10m-2026-09-26-arz-be75a38.json",
    "full": "frontier-full-2026-09-26-arz-be75a38.json",
    "100m": "frontier-100m-2026-09-21-arz-a6c13d0.json",
}
FLOOR = {
    scale: f"marisa-floor-{scale}-2026-10-31-arz-c36150a.json" for scale in ("1m", "10m", "full")
}
RESIDENT = {
    scale: f"resident-{scale}-2026-10-31-arz-c36150a.json" for scale in ("1m", "10m", "full")
}
FRONT = {scale: f"baselines-{scale}-2026-10-31-arz-c36150a.json" for scale in ("1m", "10m", "full")}
MAPS = {scale: f"maps-{scale}-2026-11-01-arz-15d2a8d.json" for scale in ("1m", "10m", "full")}

# The 100 M artifact records numeric's StringIndex as 0.000401 MiB, 420 or 421 bytes, and no
# resident artifact runs at that scale; README.md gives lexindex 4.0.0's serialized_len(). So this
# one cell is checked against the artifact's resolution, not re-derived to the byte.
NUMERIC_100M_BYTES = 421
MIB_RESOLUTION_BYTES = 0.5e-6 * 2**20

GAP_ORDER = ("titles-en", "urls", "uuid", "opaque", "dna", "numeric")


def load(name: str) -> dict:
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def bold(text: str, won: bool) -> str:
    return f"**{text}**" if won else text


def percent(fraction: float, decimals: int) -> str:
    """Signed. Where it would print a round hundred, as many more digits as show it is not one."""
    value = 100 * fraction
    while round(abs(value), decimals) >= 100:
        decimals += 1
    return f"{value:+.{decimals}f} %"


def short(stem: str) -> str:
    """A corpus file's stem as a row names it: `words-full`, `dna-1000000` to `words`, `dna`."""
    return re.sub(r"-(?:full|\d+)$", "", stem)


def label(cell: dict) -> str:
    return cell["structure"].removeprefix("lexindex ")


def tries(configuration: dict) -> str:
    count = configuration["tries"]
    return "1 try" if count == 1 else f"{count} tries"


class Campaign:
    """One frontier artifact: its comparable cells a corpus, in the order it ran them."""

    def __init__(self, scale: str) -> None:
        self.scale = scale
        self.corpora: dict[str, list[dict]] = {}
        for cell in load(CAMPAIGN[scale])["cells"]:
            comparable = "id_ns" in cell and cell["structure"] not in REFERENCE
            self.corpora.setdefault(cell["corpus"], []).extend([cell] if comparable else [])

    def lexindex(self, stem: str) -> list[dict]:
        return [c for c in self.corpora[stem] if c["structure"].startswith("lexindex ")]

    def others(self, stem: str) -> list[dict]:
        return [c for c in self.corpora[stem] if not c["structure"].startswith("lexindex ")]

    def smallest(self, stem: str) -> dict:
        return min(self.lexindex(stem), key=lambda c: c["bytes_per_key"])

    def exact(self, stem: str) -> dict:
        """lexindex's fastest structure that turns every stranger away."""
        turning_away = (c for c in self.lexindex(stem) if "HashedDict" not in c["structure"])
        return min(turning_away, key=lambda c: c["id_ns"])

    def xcdat(self, stem: str) -> dict:
        return next(c for c in self.others(stem) if c["structure"] == "XCDAT 15")


def whole_bytes(stem: str, scale: str) -> int:
    """The blob's own count, for a size that bytes a key would print as 0.00."""
    if scale == "100m":
        return NUMERIC_100M_BYTES
    corpus = next(c for c in load(RESIDENT[scale])["corpora"] if c["corpus"] == stem)
    return min(entry["blob"] for entry in corpus["lexindex"])


def lexindex_size(campaign: Campaign, stem: str, decimals: int, won: bool = True) -> str:
    """lexindex's smallest as a size column prints it; bold, where it is the smaller of the row."""
    cell = campaign.smallest(stem)
    bytes_per_key = cell["bytes_per_key"]
    if bytes_per_key < 0.01:
        text = f"{whole_bytes(stem, campaign.scale)} B total"
    else:
        text = f"{bytes_per_key:.{decimals}f}"
    return f"{bold(text, won)} ({label(cell)})"


def campaign_table(scale: str) -> list[str]:
    campaign = Campaign(scale)
    rows = [
        "| corpus | keys | raw B/key | lexindex, smallest | smallest other | margin | fastest "
        "other | `HashedDict` closed | lexindex's fastest exact search |",
        "|---|---:|---:|---|---|---:|---|---:|---|",
    ]
    for stem, cells in campaign.corpora.items():
        others = campaign.others(stem)
        ours = campaign.smallest(stem)
        other = min(others, key=lambda c: c["bytes_per_key"])
        faster = min(others, key=lambda c: c["id_ns"])
        hashed = next(c for c in cells if c["structure"] == "lexindex HashedDict closed")
        exact = campaign.exact(stem)
        ratio = exact["id_ns"] / faster["id_ns"]
        won = ours["bytes_per_key"] < other["bytes_per_key"]
        margin = percent(1 - ours["bytes_per_key"] / other["bytes_per_key"], 1)
        closed = f"{hashed['id_ns']:.0f} ns"
        rival = f"{other['bytes_per_key']:.2f}"
        quickest = f"{faster['structure']} {faster['id_ns']:.0f} ns"
        rows.append(
            f"| `{short(stem)}` | {cells[0]['keys']:,} | {cells[0]['raw_bytes_per_key']:.1f} "
            f"| {lexindex_size(campaign, stem, 2, won)} "
            f"| {bold(rival, not won)} ({other['structure']}) "
            f"| {bold(margin, won)} "
            f"| {bold(quickest, faster['id_ns'] < TIME_WIN * hashed['id_ns'])} "
            f"| {bold(closed, hashed['id_ns'] < TIME_WIN * faster['id_ns'])} "
            f"| {exact['id_ns']:.0f} ns ({label(exact)}), "
            f"{bold(f'{ratio:.2f}×', ratio < TIME_WIN)} |"  # noqa: RUF001 -- the README's sign
        )
    return rows


def gap_table() -> list[str]:
    columns = [Campaign(scale) for scale in ("1m", "10m", "full")]
    rows = ["| corpus | 1 M | 10 M | 19.2 M |", "|---|---:|---:|---:|"]
    for name in GAP_ORDER:
        cells = []
        for campaign in columns:
            stem = next((s for s in campaign.corpora if short(s) == name), None)
            if stem is None:
                cells.append("")
                continue
            ratio = campaign.exact(stem)["id_ns"] / campaign.xcdat(stem)["id_ns"]
            cells.append(bold(f"{ratio:.2f}", ratio < TIME_WIN))
        rows.append(f"| `{name}` |" + "".join(f" {cell} |" if cell else " |" for cell in cells))
    return rows


def hundred_million_table() -> list[str]:
    campaign = Campaign("100m")

    def fastest(stem: str) -> dict:
        return min(campaign.lexindex(stem), key=lambda c: c["id_ns"])

    def ratio(stem: str) -> float:
        return fastest(stem)["id_ns"] / campaign.xcdat(stem)["id_ns"]

    rows = [
        "| corpus | lexindex, smallest | XCDAT 15 | lexindex, fastest | XCDAT 15 |",
        "|---|---|---:|---|---:|",
    ]
    for stem in sorted(campaign.corpora, key=ratio):
        ours, theirs = fastest(stem), campaign.xcdat(stem)
        # The size is named only where the fastest row is not the smallest one.
        beside = "" if ours is campaign.smallest(stem) else f", {ours['bytes_per_key']:.2f}"
        won = campaign.smallest(stem)["bytes_per_key"] < theirs["bytes_per_key"]
        time = f"{ours['id_ns']:.0f} ns"
        rival = f"{theirs['id_ns']:.0f} ns"
        rival_size = f"{theirs['bytes_per_key']:.2f}"
        rows.append(
            f"| `{short(stem)}` | {lexindex_size(campaign, stem, 2, won)} "
            f"| {bold(rival_size, not won)} "
            f"| {bold(time, ratio(stem) < TIME_WIN)} ({label(ours)}{beside}) "
            f"| {bold(rival, theirs['id_ns'] < TIME_WIN * ours['id_ns'])} |"
        )
    return rows


def floor_table() -> list[str]:
    rows = [
        "| corpus | keys | MARISA, the campaign's best | MARISA, smallest | lexindex, smallest "
        "| margin |",
        "|---|---:|---:|---|---|---:|",
    ]
    for scale, name in FLOOR.items():
        campaign = Campaign(scale)
        for corpus in load(name)["corpora"]:
            stem, keys = corpus["corpus"], corpus["keys"]
            default = [c for c in corpus["configurations"] if c["cache"] == "default"]
            best = min(default, key=lambda c: c["bytes_io"])
            floor = corpus["smallest_io"]
            ours = campaign.smallest(stem)["bytes_per_key"]
            margin = 1 - ours / (floor["bytes_io"] / keys)
            won = ours * keys < floor["bytes_io"]
            smallest = f"{floor['bytes_io'] / keys:.3f}"
            rows.append(
                f"| `{short(stem)}` | {keys:,} | {best['bytes_io'] / keys:.3f} ({tries(best)}) "
                f"| {bold(smallest, not won)} ({tries(floor)}, {floor['cache']}) "
                f"| {lexindex_size(campaign, stem, 3, won)} "
                f"| {percent(margin, 3 if short(stem) == 'numeric' else 2)} |"
            )
    return rows


def resident_table() -> list[str]:
    rows = [
        "| corpus | lexindex, smallest | its file | + `load_mmap` heap | MARISA, smallest "
        "| its file | + `mmap` heap | margin, files | margin, mapped |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for name in RESIDENT.values():
        for corpus in load(name)["corpora"]:
            ours = min(corpus["lexindex"], key=lambda e: e["blob"])
            floor = next(e for e in corpus["marisa"] if "smallest_io" in e["roles"])
            files = 1 - ours["blob"] / floor["bytes_io"]
            mapped = 1 - (ours["blob"] + ours["mmap_heap"]) / (
                floor["bytes_io"] + floor["mmap_heap"]
            )
            rows.append(
                f"| `{corpus['corpus']}` | {ours['structure']} | {ours['blob']:,} "
                f"| {ours['mmap_heap']:,} | {tries(floor)}, {floor['cache']} "
                f"| {floor['bytes_io']:,} | {floor['mmap_heap']:,} "
                f"| {percent(files, 2)} | {percent(mapped, 2)} |"
            )
    return rows


def front_table() -> list[str]:
    rows = [
        "| corpus | keys | raw B/key | front coding (fcsd, 256) | lexindex, smallest | margin |",
        "|---|---:|---:|---:|---|---:|",
    ]
    for scale, name in FRONT.items():
        campaign = Campaign(scale)
        for corpus in load(name)["corpora"]:
            stem, keys = corpus["corpus"], corpus["keys"]
            fcsd = next(
                c
                for c in corpus["configurations"]
                if (c["structure"], c["parameter"]) == ("fcsd Set", "bucket 256")
            )
            ours = campaign.smallest(stem)["bytes_per_key"]
            won = ours * keys < fcsd["bytes"]
            coded = f"{fcsd['bytes'] / keys:.3f}"
            margin = percent(
                1 - ours / (fcsd["bytes"] / keys), 3 if short(stem) == "numeric" else 2
            )
            rows.append(
                f"| `{short(stem)}` | {keys:,} | {corpus['raw_bytes_per_key']:.1f} "
                f"| {bold(coded, not won)} | {lexindex_size(campaign, stem, 3, won)} "
                f"| {margin} |"
            )
    return rows


def spread(values: list[float], decimals: int, suffix: str = "") -> str:
    """A range over the corpora, or one number where they agree at the printed digits."""
    low, high = f"{min(values):.{decimals}f}", f"{max(values):.{decimals}f}"
    return (low if low == high else f"{low}–{high}") + suffix  # noqa: RUF001 -- the README's dash


def maps_table() -> list[str]:
    artifacts = {scale: load(name)["corpora"] for scale, name in MAPS.items()}

    def picked(corpus: dict, structure: str, parameter: str | None) -> dict:
        return next(
            c
            for c in corpus["configurations"]
            if c["structure"] == structure and parameter in (None, c["parameter"])
        )

    def sizes(structure: str, parameter: str | None = None) -> list[list[float]]:
        """Bytes a key at each scale, over that scale's corpora."""
        return [
            [picked(c, structure, parameter)["bytes"] / c["keys"] for c in corpora]
            for corpora in artifacts.values()
        ]

    def accepted(structure: str, parameter: str | None = None) -> list[float]:
        """The share of the non-keys let through at a million keys, as a percentage."""
        return [
            100 * picked(c, structure, parameter)["absent_accepted"] / c["keys"]
            for c in artifacts["1m"]
        ]

    def cells(ours: list[list[float]], rival: list[list[float]] | None = None) -> str:
        """The three scales, bold where the row has a rival of its guarantee and is the smaller."""
        return " | ".join(
            bold(spread(at, 3), rival is not None and max(at) < min(theirs))
            for at, theirs in zip(ours, rival or ours, strict=True)
        )

    fingerprints = ("32", "16", "8")
    narrow = [sizes("lexindex CompactHashIndex", f"fingerprint {b} bits") for b in fingerprints]
    narrow_cells = " | ".join(
        " / ".join(spread(by_width[scale], 3) for by_width in narrow) for scale in range(3)
    )
    never = {
        structure: max(accepted(structure, parameter))
        for structure, parameter in (
            ("constmap VerifiedConstMap", None),
            ("lexindex PerfectHashIndex", None),
        )
    }
    if any(never.values()):
        raise SystemExit(f"a structure that rejects every non-key accepted some: {never}")
    wide = accepted("lexindex CompactHashIndex", "fingerprint 64 bits")
    of_32 = accepted("lexindex CompactHashIndex", "fingerprint 32 bits")
    of_16 = accepted("lexindex CompactHashIndex", "fingerprint 16 bits")
    of_8 = accepted("lexindex CompactHashIndex", "fingerprint 8 bits")
    if any(wide) or any(of_32):
        raise SystemExit("a 32- or 64-bit fingerprint accepted a non-key; the table says none")
    plain, closed = sizes("constmap ConstMap"), sizes("lexindex ClosedHashIndex")
    verified = sizes("constmap VerifiedConstMap")
    compact = sizes("lexindex CompactHashIndex", "fingerprint 64 bits")
    return [
        "| structure | a key gives | a string that is not a key gives | 1 M | 10 M | 19.2 M |",
        "|---|---|---|---:|---:|---:|",
        "| constmap `ConstMap` | the 64-bit value it was built with | an undefined value "
        f"| {cells(plain, closed)} |",
        "| lexindex `ClosedHashIndex` | its id, dense in [0, n), in an order the hash picks "
        f"| some id | {cells(closed, plain)} |",
        "| constmap `VerifiedConstMap` | the value | `NOT_FOUND`; a 64-bit check, accepted 0 times "
        f"| {cells(verified, compact)} |",
        "| lexindex `CompactHashIndex`, 64-bit fingerprint | its id | `None`; accepted 0 times "
        f"| {cells(compact, verified)} |",
        "| lexindex `CompactHashIndex`, 32 / 16 / 8 bits | its id | `None`, but for about 2⁻³² / "
        f"2⁻¹⁶ / 2⁻⁸ of them; accepted at 1 M 0 times, {spread(of_16, 4, ' %')}, "
        f"{spread(of_8, 3, ' %')} (1/256 is {100 / 256:.3f} %) | {narrow_cells} |",
        "| lexindex `PerfectHashIndex` | its id, and the key back from the id | `None`: it "
        f"compares the stored key | {cells(sizes('lexindex PerfectHashIndex'))} |",
    ]


def check_numeric_100m() -> list[str]:
    """The one size no artifact holds to the byte has to lie inside what the artifact does say."""
    stem = "numeric-100000000"
    recorded = Campaign("100m").smallest(stem)
    measured = recorded["bytes_per_key"] * recorded["keys"]
    if abs(measured - NUMERIC_100M_BYTES) > MIB_RESOLUTION_BYTES:
        return [f"{stem}: {NUMERIC_100M_BYTES} B is outside the artifact's {measured:.1f} B"]
    return []


# Section heading -> the tables it holds, in order, each with the artifacts it renders. A file cited
# in a section's prose has to be the file its table is checked against.
SECTIONS = {
    "Results: a million keys": ((lambda: campaign_table("1m"), (CAMPAIGN["1m"],)),),
    "Results: ten million keys": ((lambda: campaign_table("10m"), (CAMPAIGN["10m"],)),),
    "Results: past ten million keys": (
        (lambda: campaign_table("full"), (CAMPAIGN["full"],)),
        (gap_table, ()),
        (hundred_million_table, (CAMPAIGN["100m"],)),
    ),
    "MARISA at its smallest": ((floor_table, tuple(FLOOR.values())),),
    "What a loaded index holds": ((resident_table, tuple(RESIDENT.values())),),
    "Plain front coding": ((front_table, tuple(FRONT.values())),),
    "Static maps that do not store their keys": ((maps_table, tuple(MAPS.values())),),
}


def sections(readme: str) -> dict[str, str]:
    """The text under each `## ` heading."""
    parts = re.split(r"^## (.+)$", readme, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2], strict=True))


def tables_in(text: str) -> list[list[str]]:
    """Each run of lines that start with a `|`."""
    runs = itertools.groupby(text.splitlines(), key=lambda line: line.startswith("|"))
    return [list(lines) for is_table, lines in runs if is_table]


def cited(text: str) -> set[str]:
    """The `results/` files a section names, its brace forms expanded."""
    files: set[str] = set()
    for citation in re.findall(r"results/([A-Za-z0-9._{},-]+\.[a-z]+)", text):
        parts = re.split(r"\{([^{}]*)\}", citation)
        choices = [p.split(",") if i % 2 else [p] for i, p in enumerate(parts)]
        files.update(map("".join, itertools.product(*choices)))
    return files


def differences(section: str, found: list[str], want: list[str]) -> list[str]:
    """Line by line and, in a row of the same shape, cell by cell."""
    out = []
    if len(found) != len(want):
        out.append(f"{section}: {len(found)} rows, the artifacts give {len(want)}")
    for at, (mine, theirs) in enumerate(zip(found, want, strict=False)):
        if mine == theirs:
            continue
        a, b = mine.split("|"), theirs.split("|")
        if len(a) != len(b):
            out.append(f"{section}, row {at}: README {mine!r}, artifacts {theirs!r}")
            continue
        for column, (x, y) in enumerate(zip(a, b, strict=True)):
            if x != y:
                out.append(
                    f"{section}, row {at} ({a[1].strip()}), column {column}: "
                    f"README {x.strip()!r}, artifacts {y.strip()!r}"
                )
    return out


def main() -> int:
    text = sections((ROOT / "README.md").read_text(encoding="utf-8"))
    problems = check_numeric_100m()
    checked = 0
    for section, renderers in SECTIONS.items():
        if section not in text:
            problems.append(f"README.md has no section {section!r}")
            continue
        found = tables_in(text[section])
        if len(found) != len(renderers):
            problems.append(f"{section}: {len(found)} tables, {len(renderers)} checked here")
        for table, (render, names) in zip(found, renderers, strict=False):
            want = render()
            problems += differences(section, table, want)
            checked += len(want) - 2
            for name in names:
                if name not in cited(text[section]):
                    problems.append(f"{section}: checked against {name}, which it does not cite")
    for problem in problems:
        print(f"::error::{problem}")
    print(f"{checked} rows checked, {len(problems)} differences")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
