#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

# Loadable datasets (can replace with external JSONs if preferred)
COMMON_PREFIXES = {"mr", "mrs", "ms", "miss", "dr", "rev", "fr", "prof", "sir", "sr", "madam", "capt", "lt", "lt.", "cmndr", "cmndr."}
COMMON_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "md", "phd"}
PLACE_ABBREVIATIONS = {
    "USA": "United States of America", "U.S.A.": "United States of America",
    "UK": "United Kingdom", "U.K.": "United Kingdom"
}
DATE_PREFIXES = {
    "ABT": "about", "CAL": "calculated", "EST": "estimated", "BEF": "before",
    "AFT": "after", "BET": "between", "FROM": "from", "TO": "to", "AND": "and"
}
DATE_REGEX = re.compile(r'^(?:(ABT|CAL|EST|BEF|AFT|BET|FROM|TO)\s+)?(.+)$', re.IGNORECASE)

def parse_name(full_name):
    prefix = given = surname = suffix = ""
    name = full_name.strip()

    if "/" in name:
        first, last = name.find("/"), name.rfind("/")
        surname = name[first+1:last].strip()
        before, after = name[:first].strip(), name[last+1:].strip(",. ")
        suffix = after if after.lower().rstrip(".") in COMMON_SUFFIXES else ""
        parts = before.split()
        prefix_tokens = []
        while parts:
            token = parts[0]
            if token.lower().rstrip(".") in COMMON_PREFIXES or token.endswith("."):
                prefix_tokens.append(token.rstrip("."))
                parts.pop(0)
            else:
                break
        prefix = " ".join(prefix_tokens)
        given = " ".join(parts)
    else:
        parts = name.split()
        if len(parts) > 1:
            surname = parts[-1]
            given_parts = parts[:-1]
            if surname.lower().rstrip(".") in COMMON_SUFFIXES:
                suffix = surname.rstrip(".")
                surname = given_parts[-1]
                given_parts = given_parts[:-1]
            prefix_tokens = []
            while given_parts:
                token = given_parts[0]
                if token.lower().rstrip(".") in COMMON_PREFIXES or token.endswith("."):
                    prefix_tokens.append(token.rstrip("."))
                    given_parts.pop(0)
                else:
                    break
            prefix = " ".join(prefix_tokens)
            given = " ".join(given_parts)
        else:
            given = name
    return prefix, given, surname, suffix

def normalize_date(date_str):
    date_str = date_str.strip()
    m = DATE_REGEX.match(date_str)
    if not m:
        return date_str
    prefix, core_date = m.groups()
    core = core_date.strip()
    if prefix:
        return f"{DATE_PREFIXES.get(prefix.upper(), prefix.lower())} {core}"
    return core

def standardize_place(place_str):
    if not isinstance(place_str, str):
        return place_str
    parts = [p.strip() for p in place_str.split(",")]
    standardized_parts = []
    for part in parts:
        if part in PLACE_ABBREVIATIONS:
            standardized_parts.append(PLACE_ABBREVIATIONS[part])
        elif part.isupper() and len(part) > 3:
            standardized_parts.append(part)
        else:
            standardized_parts.append(part.title())
    return ", ".join(standardized_parts)

def enrich_record(node):
    tag, value = node.get("tag"), node.get("value")
    children = node.get("children", [])
    existing_tags = {child.get("tag") for child in children}

    if tag == "NAME" and value:
        prefix, given, surname, suffix = parse_name(value)
        if prefix and "NPFX" not in existing_tags:
            children.append({"tag": "NPFX", "value": prefix, "children": []})
        if given and "GIVN" not in existing_tags:
            children.append({"tag": "GIVN", "value": given, "children": []})
        if surname and "SURN" not in existing_tags:
            children.append({"tag": "SURN", "value": surname, "children": []})
        if suffix and "NSFX" not in existing_tags:
            children.append({"tag": "NSFX", "value": suffix, "children": []})

    if tag == "DATE" and value:
        normalized = normalize_date(value)
        if normalized != value:
            node["value_normalized"] = normalized

    if tag == "PLAC" and value:
        standardized = standardize_place(value)
        if standardized != value:
            node["value_standardized"] = standardized

    for child in children:
        enrich_record(child)

def main():
    parser = argparse.ArgumentParser(description="Enrich GEDCOM structured records")
    parser.add_argument("--in", dest="input_file", required=True, type=Path)
    parser.add_argument("--out", dest="output_file", required=True, type=Path)
    args = parser.parse_args()

    with args.input_file.open("r", encoding="utf-8") as f:
        records = json.load(f)

    name_count = date_count = place_count = 0
    for rec in records:
        stack = [rec]
        while stack:
            node = stack.pop()
            tag, val = node.get("tag"), node.get("value")
            if tag == "NAME" and val:
                name_count += 1
            if tag == "DATE" and val and DATE_REGEX.match(val):
                date_count += 1
            if tag == "PLAC" and val:
                parts = [p.strip() for p in val.split(",")]
                if any(p in PLACE_ABBREVIATIONS or (p.isupper() and len(p) > 3) for p in parts):
                    place_count += 1
            enrich_record(node)
            stack.extend(node.get("children", []))

    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    with args.output_file.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)

    print(f"✅ Enriched {len(records)} records — NAMEs: {name_count}, DATEs: {date_count}, PLACs: {place_count}")

if __name__ == "__main__":
    main()
