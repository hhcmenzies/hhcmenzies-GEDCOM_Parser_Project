#!/usr/bin/env python3
import json
import csv
import re
import logging
import sys
from pathlib import Path

# Try to import PyMuPDF for PDF text extraction
try:
    import fitz  # PyMuPDF
except ImportError:
    logging.error("PyMuPDF (fitz) is not installed. Please install it to parse PDF content.")
    sys.exit(1)

import psycopg2

# Configure logging for console output
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Define file paths relative to script location
script_dir = Path(__file__).resolve().parent
root_dir = script_dir.parent
TAG_DICT_PATH = root_dir / "datasets" / "gedcom" / "canonical" / "canonical_tag_dictionary_gedcom551.patched.json"
GED551_PDF = root_dir / "docs" / "ged551.pdf"
GED555_PDF = root_dir / "docs" / "GEDCOM 5.5.5.pdf"
GED7_PDF   = root_dir / "docs" / "gedcom7-rc.pdf"
CSV_OUT_PATH = root_dir / "inventory" / "latest" / "tag_version_support_matrix.csv"

def norm_tag(tag: str) -> str:
    """Normalize tag name to uppercase with no surrounding whitespace."""
    return str(tag).strip().upper()

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract all text from a PDF file using PyMuPDF."""
    logging.info(f"Extracting text from PDF: {pdf_path.name}")
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logging.error(f"Failed to open {pdf_path.name}: {e}")
        sys.exit(1)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text

def main():
    logging.info(f"Loading canonical tag dictionary from {TAG_DICT_PATH}")
    try:
        with TAG_DICT_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
            # The JSON might have tags under a key or as top-level dict
            tag_dict = data["tags"] if "tags" in data else data
    except Exception as e:
        logging.error(f"Error reading tag dictionary JSON: {e}")
        sys.exit(1)
    logging.info(f"Canonical tag dictionary loaded ({len(tag_dict)} tags).")

    # Extract text from each GEDCOM specification PDF
    text_551 = extract_pdf_text(GED551_PDF)
    text_555 = extract_pdf_text(GED555_PDF)
    text_7   = extract_pdf_text(GED7_PDF)
    logging.info("PDF text extraction complete.")

    # Connect to PostgreSQL
    logging.info("Connecting to PostgreSQL database...")
    try:
        conn = psycopg2.connect(
            dbname="gedcom_db", user="gedcom_user", password="icecream",
            host="localhost", options="-c client_encoding=UTF8"
        )
    except Exception as e:
        logging.error(f"Database connection failed: {e}")
        sys.exit(1)
    cur = conn.cursor()
    logging.info("Database connection established.")

    # Prepare regex patterns for each spec for efficient reuse
    patterns = {}
    # Use case-sensitive word-boundary search for each tag
    for tag in tag_dict.keys():
        tag_upper = norm_tag(tag)
        patterns[tag_upper] = re.compile(rf"\b{re.escape(tag_upper)}\b")

    # Lists to track insert/update counts for diagnostics
    inserted_count = 0
    updated_count = 0

    logging.info("Processing tags and updating database...")
    for tag, info in tag_dict.items():
        tag_clean = norm_tag(tag)
        desc = info.get("description", "")
        # Determine presence in each specification text
        in_5_5_1 = bool(patterns[tag_clean].search(text_551))
        in_5_5_5 = bool(patterns[tag_clean].search(text_555))
        in_7     = bool(patterns[tag_clean].search(text_7))
        # Insert or update the tag definition in the database
        try:
            cur.execute(
                """
                INSERT INTO gedcom_tag_definitions (tag, in_5_5_1, in_5_5_5, in_7, description)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (tag)
                DO UPDATE SET 
                    in_5_5_1 = EXCLUDED.in_5_5_1,
                    in_5_5_5 = EXCLUDED.in_5_5_5,
                    in_7     = EXCLUDED.in_7,
                    description = EXCLUDED.description;
                """,
                (tag_clean, in_5_5_1, in_5_5_5, in_7, desc)
            )
            if cur.rowcount == 1:
                # rowcount 1 on insert (ON CONFLICT DO UPDATE returns 0 for no insert)
                inserted_count += 1
            elif cur.rowcount == 0:
                # If no new row inserted, we assume an update happened
                updated_count += 1
        except Exception as e:
            logging.error(f"Failed to insert/update tag '{tag_clean}': {e}")
            conn.rollback()
            cur.close()
            conn.close()
            sys.exit(1)
    # Commit all changes to the database
    conn.commit()
    logging.info(f"Database update complete. Inserted {inserted_count} new rows, updated {updated_count} existing rows.")

    # Export tag version support matrix to CSV
    logging.info(f"Writing CSV report to {CSV_OUT_PATH}")
    # Ensure the output directory exists
    CSV_OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with CSV_OUT_PATH.open("w", encoding="utf-8", newline="") as csvfile:
            writer = csv.writer(csvfile)
            # Header row
            writer.writerow(["Tag", "GEDCOM 5.5.1", "GEDCOM 5.5.5", "GEDCOM 7.x"])
            # Iterate in sorted order of tag for consistency
            for tag, info in sorted(tag_dict.items(), key=lambda x: norm_tag(x[0])):
                tag_clean = norm_tag(tag)
                in_5_5_1 = bool(patterns[tag_clean].search(text_551))
                in_5_5_5 = bool(patterns[tag_clean].search(text_555))
                in_7     = bool(patterns[tag_clean].search(text_7))
                # Mark presence as True/False (or 1/0 or Yes/No as needed)
                writer.writerow([tag_clean, "YES" if in_5_5_1 else "NO",
                                              "YES" if in_5_5_5 else "NO",
                                              "YES" if in_7 else "NO"])
    except Exception as e:
        logging.error(f"Failed to write CSV output: {e}")
    else:
        logging.info("CSV export successful.")
    # Clean up database connection
    cur.close()
    conn.close()
    logging.info("✅ All tasks completed successfully.")
    
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.exception("An unexpected error occurred during execution.")
        sys.exit(1)
