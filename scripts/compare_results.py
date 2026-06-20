from __future__ import annotations

import argparse
import csv
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


NON_NUMERIC_VALUES = {"", "N/A", "Timeout", "RunError", "FutureError"}


@dataclass
class ResultSummary:
    path: Path
    total_rows: int
    bfnd_values: list[int]
    find_values: list[int]
    paired_bfnd_find: list[tuple[int, int]]
    bfnd_missing: int
    find_missing: int

    @property
    def ours_values(self): return self.bfnd_values
    @property
    def baseline_values(self): return self.find_values
    @property
    def paired_values(self): return self.paired_bfnd_find
    @property
    def ours_missing(self): return self.bfnd_missing
    @property
    def baseline_missing(self): return self.find_missing


    @property
    def bfnd_mean(self) -> float | None:
        return statistics.fmean(self.bfnd_values) if self.bfnd_values else None

    @property
    def find_mean(self) -> float | None:
        return statistics.fmean(self.find_values) if self.find_values else None

    @property
    def bfnd_median(self) -> float | None:
        return statistics.median(self.bfnd_values) if self.bfnd_values else None

    @property
    def find_median(self) -> float | None:
        return statistics.median(self.find_values) if self.find_values else None

    @property
    def ours_mean(self) -> float | None:
        return self.bfnd_mean

    @property
    def baseline_mean(self) -> float | None:
        return self.find_mean

    @property
    def ours_median(self) -> float | None:
        return self.bfnd_median

    @property
    def baseline_median(self) -> float | None:
        return self.find_median

    @property
    def ours_min(self) -> int | None:
        return min(self.bfnd_values) if self.bfnd_values else None

    @property
    def ours_max(self) -> int | None:
        return max(self.bfnd_values) if self.bfnd_values else None

    @property
    def baseline_min(self) -> int | None:
        return min(self.find_values) if self.find_values else None

    @property
    def baseline_max(self) -> int | None:
        return max(self.find_values) if self.find_values else None

    @property
    def paired_count(self) -> int:
        return len(self.paired_values)

    @property
    def ours_wins(self) -> int:
        return sum(1 for ours, baseline in self.paired_values if ours < baseline)

    @property
    def baseline_wins(self) -> int:
        return sum(1 for ours, baseline in self.paired_values if baseline < ours)

    @property
    def ties(self) -> int:
        return sum(1 for ours, baseline in self.paired_values if ours == baseline)

    @property
    def mean_delta(self) -> float | None:
        if not self.paired_values:
            return None
        deltas = [baseline - ours for ours, baseline in self.paired_values]
        return statistics.fmean(deltas)


def parse_result_value(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None

    value = raw_value.strip()
    if value in NON_NUMERIC_VALUES:
        return None

    try:
        return int(value)
    except ValueError:
        try:
            return int(float(value))
        except ValueError:
            return None


def load_summary(path: Path) -> ResultSummary:
    with path.open("r", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames is None:
            raise ValueError(f"{path} has no header row")

        asn_cols = [c for c in reader.fieldnames if c.startswith("ASN_")]
        if len(asn_cols) < 2:
            raise ValueError(f"{path} must have at least 2 ASN_ columns, found: {asn_cols}")

        bfnd_col = next((c for c in asn_cols if "bfnd" in c.lower() and "ble" not in c.lower()), None)
        find_col = next((c for c in asn_cols if "find" in c.lower() or "baseline" in c.lower()), None)

        # Fallbacks for backward compatibility
        if not bfnd_col:
            bfnd_col = next((c for c in asn_cols if "bfnd" in c.lower() or "ours" in c.lower()), asn_cols[0])
        if not find_col:
            find_col = next((c for c in asn_cols if c != bfnd_col), asn_cols[-1])

        total_rows = 0
        bfnd_values: list[int] = []
        find_values: list[int] = []
        
        paired_bfnd_find: list[tuple[int, int]] = []
        
        bfnd_missing = 0
        find_missing = 0

        for row in reader:
            total_rows += 1
            bfnd = parse_result_value(row.get(bfnd_col)) if bfnd_col else None
            find = parse_result_value(row.get(find_col)) if find_col else None

            if bfnd is None:
                bfnd_missing += 1
            else:
                bfnd_values.append(bfnd)

            if find is None:
                find_missing += 1
            else:
                find_values.append(find)

            if bfnd is not None and find is not None:
                paired_bfnd_find.append((bfnd, find))

    return ResultSummary(
        path=path,
        total_rows=total_rows,
        bfnd_values=bfnd_values,
        find_values=find_values,
        paired_bfnd_find=paired_bfnd_find,
        bfnd_missing=bfnd_missing,
        find_missing=find_missing,
    )


def collect_input_paths(items: Iterable[str]) -> list[Path]:
    collected: list[Path] = []
    for item in items:
        path = Path(item)
        if path.is_dir():
            collected.extend(sorted(path.glob("*.tsv")))
        else:
            collected.append(path)

    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in collected:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_paths.append(path)

    return unique_paths


def format_number(value: float | int | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def print_summary_table(summaries: list[ResultSummary]) -> None:
    headers = [
        "File",
        "Runs",
        "Ours mean",
        "Baseline mean",
        "Mean delta",
        "Ours median",
        "Baseline median",
        "Ours wins",
        "Baseline wins",
        "Ties",
        "Ours missing",
        "Baseline missing",
    ]

    rows = []
    for summary in summaries:
        rows.append(
            [
                summary.path.name,
                summary.total_rows,
                format_number(summary.ours_mean),
                format_number(summary.baseline_mean),
                format_number(summary.mean_delta),
                format_number(summary.ours_median),
                format_number(summary.baseline_median),
                summary.ours_wins,
                summary.baseline_wins,
                summary.ties,
                summary.ours_missing,
                summary.baseline_missing,
            ]
        )

    widths = [len(header) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))

    def render_row(row: list[object]) -> str:
        return "  ".join(str(cell).ljust(widths[index]) for index, cell in enumerate(row))

    print(render_row(headers))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print(render_row(row))


def print_file_details(summary: ResultSummary) -> None:
    print(f"\n{summary.path}")
    print(f"  Total rows: {summary.total_rows}")
    print(f"  Ours valid: {len(summary.ours_values)}")
    print(f"  Baseline valid: {len(summary.baseline_values)}")
    print(f"  Paired valid: {summary.paired_count}")
    print(f"  Ours mean/median: {format_number(summary.ours_mean)} / {format_number(summary.ours_median)}")
    print(f"  Baseline mean/median: {format_number(summary.baseline_mean)} / {format_number(summary.baseline_median)}")
    print(f"  Mean delta (baseline - ours): {format_number(summary.mean_delta)}")
    print(f"  Ours wins / Baseline wins / Ties: {summary.ours_wins} / {summary.baseline_wins} / {summary.ties}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare BFND result TSV files such as results_node0.tsv. Lower ASN is better."
    )
    parser.add_argument(
        "paths",
        nargs="+",
        help="One or more .tsv result files, or directories containing .tsv files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_paths = collect_input_paths(args.paths)

    if not input_paths:
        print("No TSV files found.")
        return 1

    summaries: list[ResultSummary] = []
    for path in input_paths:
        if not path.exists():
            print(f"Skipping missing file: {path}")
            continue
        summaries.append(load_summary(path))

    if not summaries:
        print("No valid TSV files could be loaded.")
        return 1

    print_summary_table(summaries)

    if len(summaries) > 1:
        best_ours = min((summary for summary in summaries if summary.ours_mean is not None), key=lambda item: item.ours_mean, default=None)
        best_baseline = min((summary for summary in summaries if summary.baseline_mean is not None), key=lambda item: item.baseline_mean, default=None)

        if best_ours is not None:
            print(f"\nBest mean Ours: {best_ours.path.name} ({format_number(best_ours.ours_mean)})")
        if best_baseline is not None:
            print(f"Best mean Baseline: {best_baseline.path.name} ({format_number(best_baseline.baseline_mean)})")

    for summary in summaries:
        print_file_details(summary)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())