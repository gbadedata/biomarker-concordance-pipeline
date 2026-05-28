#!/usr/bin/env python3
"""
Samplesheet validator for the biomarker concordance pipeline.

Columns: sample, fastq_1, fastq_2, sex, replicate
Writes validated CSV to stdout. Exits non-zero on any validation failure.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

REQUIRED_COLUMNS = {"sample", "fastq_1", "fastq_2", "sex", "replicate"}
VALID_SEX        = {"M", "F", "unknown"}
FASTQ_PATTERN    = re.compile(r"\.f(ast)?q(\.gz)?$", re.IGNORECASE)
S3_PATTERN       = re.compile(r"^s3://")
HTTP_PATTERN     = re.compile(r"^https?://")


def error(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def is_valid_file(p: str) -> bool:
    if S3_PATTERN.match(p) or HTTP_PATTERN.match(p):
        return True
    return Path(p).exists()


def validate(path: str) -> list[dict]:
    rows: list[dict] = []

    with open(path, newline="") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            error("Samplesheet is empty.")

        missing = REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            error(f"Missing columns: {', '.join(sorted(missing))}")

        seen: set[tuple] = set()

        for i, row in enumerate(reader, start=2):
            sample    = row["sample"].strip()
            fastq_1   = row["fastq_1"].strip()
            fastq_2   = row["fastq_2"].strip()
            sex       = row["sex"].strip()
            replicate = row["replicate"].strip()

            if not sample:
                error(f"Row {i}: sample is empty.")
            if not re.match(r"^[A-Za-z0-9_\-]+$", sample):
                error(f"Row {i}: sample '{sample}' contains invalid characters.")
            if not fastq_1:
                error(f"Row {i} ({sample}): fastq_1 is empty.")
            if not FASTQ_PATTERN.search(fastq_1):
                error(f"Row {i} ({sample}): fastq_1 does not look like a FASTQ: {fastq_1}")

            single_end = fastq_2 == ""
            if not single_end and not FASTQ_PATTERN.search(fastq_2):
                error(f"Row {i} ({sample}): fastq_2 does not look like a FASTQ: {fastq_2}")
            if fastq_1 == fastq_2 and not single_end:
                error(f"Row {i} ({sample}): fastq_1 and fastq_2 are identical.")
            if sex not in VALID_SEX:
                error(f"Row {i} ({sample}): invalid sex '{sex}'. Use M, F, or unknown.")

            try:
                rep = int(replicate)
                if rep < 1:
                    raise ValueError
            except ValueError:
                error(f"Row {i} ({sample}): replicate must be a positive integer.")

            pair = (sample, rep)
            if pair in seen:
                error(f"Row {i}: duplicate (sample, replicate): ({sample}, {rep}).")
            seen.add(pair)

            rows.append({
                "sample":     sample,
                "fastq_1":    fastq_1,
                "fastq_2":    fastq_2,
                "sex":        sex,
                "replicate":  rep,
                "single_end": str(single_end).upper(),
            })

    if not rows:
        error("Samplesheet has no data rows.")
    return rows


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.csv> <validated.csv>", file=sys.stderr)
        sys.exit(1)

    rows = validate(sys.argv[1])
    fields = ["sample", "fastq_1", "fastq_2", "sex", "replicate", "single_end"]

    with open(sys.argv[2], "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Validation passed: {len(rows)} row(s).", file=sys.stderr)


if __name__ == "__main__":
    main()
