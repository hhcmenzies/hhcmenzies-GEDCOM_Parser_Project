import argparse
import csv
import uuid
from pathlib import Path
from typing import Iterable, Optional


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_REPORTS_DIR = BASE_DIR / "reports"


def iter_gedcom_files(input_path: Path, pattern: str, recursive: bool) -> Iterable[Path]:
    if input_path.is_file():
        yield input_path
        return

    if not input_path.exists():
        raise FileNotFoundError(f"--input not found: {input_path}")

    if not input_path.is_dir():
        raise ValueError(f"--input must be a .ged file or a directory: {input_path}")

    globber = input_path.rglob(pattern) if recursive else input_path.glob(pattern)
    for p in globber:
        if p.is_file():
            yield p


def extract_places_to_csv(
    input_path: Path,
    out_csv: Path,
    pattern: str,
    recursive: bool,
    run_id: str,
) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    files = list(iter_gedcom_files(input_path, pattern, recursive))
    if not files:
        raise FileNotFoundError(f"No GEDCOM files found in {input_path} (pattern={pattern}, recursive={recursive})")

    wrote_rows = 0

    with out_csv.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow([
            "run_id",
            "source_file_id",
            "source_path",
            "record_xref",
            "record_type",
            "event_type",
            "event_date",
            "plac_raw",
            "form_raw",
            "lati_raw",
            "long_raw",
        ])

        for ged_path in files:
            current_xref: Optional[str] = None
            current_record_type: Optional[str] = None
            current_event: Optional[str] = None
            current_date: Optional[str] = None

            with ged_path.open("r", encoding="utf-8", errors="ignore") as f:
                for raw_line in f:
                    line = raw_line.rstrip("\n")

                    # Record header example:
                    # 0 @I123@ INDI
                    # 0 @F45@ FAM
                    if line.startswith("0 @"):
                        parts = line.split()
                        current_xref = parts[1] if len(parts) > 1 else None
                        current_record_type = parts[2] if len(parts) > 2 else None
                        current_event = None
                        current_date = None
                        continue

                    # Event start example:
                    # 1 BIRT
                    # 1 DEAT
                    # 1 MARR
                    if line.startswith("1 "):
                        parts = line.split(maxsplit=2)
                        tag = parts[1] if len(parts) > 1 else None
                        if tag in {"BIRT", "DEAT", "MARR", "RESI", "EVEN"}:
                            current_event = tag
                            current_date = None
                        continue

                    # Date line example:
                    # 2 DATE 12 JAN 1901
                    if line.startswith("2 DATE"):
                        current_date = line[7:].strip()
                        continue

                    # Place line example:
                    # 2 PLAC Salem, Essex, Massachusetts, USA
                    if line.startswith("2 PLAC"):
                        plac = line[7:].strip()
                        writer.writerow([
                            run_id,
                            ged_path.name,
                            str(ged_path),
                            current_xref,
                            current_record_type,
                            current_event,
                            current_date,
                            plac,
                            None,
                            None,
                            None,
                        ])
                        wrote_rows += 1
                        continue

    print(f"Run ID: {run_id}")
    print(f"Processed {len(files)} GEDCOM file(s)")
    print(f"Wrote {wrote_rows} row(s) to {out_csv}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract GEDCOM PLAC occurrences to CSV (supports file or folder)")
    ap.add_argument("--input", required=True, help="Path to a .ged file or a directory containing .ged files")
    ap.add_argument("--pattern", default="*.ged", help="Glob pattern when --input is a directory (default: *.ged)")
    ap.add_argument("--recursive", action="store_true", help="Recurse into subdirectories when --input is a directory")
    ap.add_argument("--out", default=str(DEFAULT_REPORTS_DIR / "place_occurrence.csv"), help="Output CSV path")
    ap.add_argument("--run-id", default=str(uuid.uuid4()), help="Run ID for provenance (default: UUID)")
    args = ap.parse_args()

    extract_places_to_csv(
        input_path=Path(args.input),
        out_csv=Path(args.out),
        pattern=args.pattern,
        recursive=args.recursive,
        run_id=args.run_id,
    )


if __name__ == "__main__":
    main()
