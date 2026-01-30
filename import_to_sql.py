#!/usr/bin/env python3
import sys, json, sqlite3

if len(sys.argv) != 3:
    print("Usage: python import_to_sql.py <parsed_data.json> <output.db>")
    sys.exit(1)

json_path = sys.argv[1]
db_path = sys.argv[2]

# Load parsed JSON data (output from Phase 5)
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Connect to SQLite database (will create if not exists)
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Define schema: People, Families, and a junction table for family-child links
cur.executescript("""
DROP TABLE IF EXISTS People;
DROP TABLE IF EXISTS Families;
DROP TABLE IF EXISTS FamilyChildren;
CREATE TABLE People (
    id TEXT PRIMARY KEY,
    name TEXT,
    sex TEXT
);
CREATE TABLE Families (
    id TEXT PRIMARY KEY,
    husband_id TEXT,
    wife_id TEXT
);
CREATE TABLE FamilyChildren (
    family_id TEXT,
    child_id TEXT
);
""")

# Populate People table with Individual records
for rec in data:
    if rec.get("tag") == "INDI":
        person_id = rec.get("id")               # Individual's @ID@
        # Default values in case fields are missing
        name_value = None
        sex_value = None
        # Iterate through children to find NAME and SEX
        for child in rec.get("children", []):
            if child["tag"] == "NAME":
                name_value = child.get("value", "")
            elif child["tag"] == "SEX":
                sex_value = child.get("value", "")
        # Insert into People table
        cur.execute(
            "INSERT OR IGNORE INTO People(id, name, sex) VALUES (?, ?, ?);",
            (person_id, name_value, sex_value)
        )

# Populate Families table with Family records and collect child links
child_links = []  # to collect (family_id, child_id) pairs for FamilyChildren
for rec in data:
    if rec.get("tag") == "FAM":
        family_id = rec.get("id")
        husband_id = None
        wife_id = None
        # For each substructure of the family, capture husband, wife, and children
        for child in rec.get("children", []):
            tag = child["tag"]
            val = child.get("value", "")
            if tag == "HUSB" and val:
                husband_id = val.strip('@')  # remove '@' to get person ID
            elif tag == "WIFE" and val:
                wife_id = val.strip('@')
            elif tag == "CHIL" and val:
                child_id = val.strip('@')
                child_links.append((family_id, child_id))
        # Insert into Families table
        cur.execute(
            "INSERT OR IGNORE INTO Families(id, husband_id, wife_id) VALUES (?, ?, ?);",
            (family_id, husband_id, wife_id)
        )
# Some GEDCOM files might not list children under FAM; also use individuals' FAMC links
for rec in data:
    if rec.get("tag") == "INDI":
        person_id = rec.get("id")
        for child in rec.get("children", []):
            if child["tag"] == "FAMC":
                fam_val = child.get("value", "")
                if fam_val:
                    fam_id = fam_val.strip('@')
                    child_links.append((fam_id, person_id))

# Remove duplicate child links and insert into FamilyChildren
seen = set()
for fam_id, indi_id in child_links:
    if fam_id and indi_id:
        key = (fam_id, indi_id)
        if key not in seen:
            cur.execute(
                "INSERT INTO FamilyChildren(family_id, child_id) VALUES (?, ?);",
                (fam_id, indi_id)
            )
            seen.add(key)

conn.commit()
cur.close()
conn.close()
