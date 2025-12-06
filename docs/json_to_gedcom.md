# JSON to GEDCOM Conversion Guide

## Overview
This document explains how to convert the JSON output from `gedcom_to_json.py` back into standard GEDCOM lines. It also outlines validation steps to confirm that the regenerated file matches the original.

## Expected JSON Format
The parser produces a list of records where each record is a dictionary with the following keys:

- `level` – numeric level value from the GEDCOM line.
- `tag` – the GEDCOM tag or cross‑reference identifier.
- `value` – optional value string following the tag.
- `children` – list of child records forming the nested hierarchy.

Example structure:

```json
[
  {
    "level": 0,
    "tag": "@I1@",
    "value": "INDI",
    "children": [
      {"level": 1, "tag": "NAME", "value": "John /Doe/", "children": []}
    ]
  }
]
```

## Proposed `json_to_gedcom.py`
The companion script would reverse the process by walking the JSON tree and writing lines in `level TAG value` format.
A simplified outline:

1. Load the JSON file path from `config.yaml` using `GEDCOM_Parser/config/config.py`.
2. Recursively iterate through each record:
   - Compose a line using the node's `level`, `tag` and optional `value`.
   - Append the line to a list and process its `children`.
3. Write the collected lines to an output `.ged` file.

This mirrors the parsing logic in `GEDCOM_Parser/parsers/gedcom_to_json.py` and should re‑create the original hierarchy.

## Round‑Trip Validation
To verify correctness:

1. Run `gedcom_to_json.py` to produce the JSON representation of a GEDCOM file.
2. Execute the proposed `json_to_gedcom.py` to reconstruct the GEDCOM text from that JSON.
3. Compare the original and regenerated `.ged` files using a diff tool. Identical output confirms that the conversion is lossless.

