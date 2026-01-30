#!/usr/bin/env python3
import sys, json, sqlite3

if len(sys.argv) != 3:
    print("Usage: python validate_results.py <parsed_data.json> <gedcom.db>")
    sys.exit(1)

json_path = sys.argv[1]
db_path = sys.argv[2]

# Load parsed JSON data
with open(json_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Connect to the database
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Prepare an index of record IDs and their types from JSON data
id_to_tag = {}
for rec in data:
    if "id" in rec:
        rec_id = rec["id"]
        rec_tag = rec["tag"]
        id_to_tag[rec_id] = rec_tag

# 1. Check for HEAD and TRLR records
head_count = sum(1 for rec in data if rec.get("tag") == "HEAD")
trlr_count = sum(1 for rec in data if rec.get("tag") == "TRLR")

# 2. Count consistency between JSON and DB
num_individuals_json = sum(1 for rec in data if rec.get("tag") == "INDI")
num_families_json = sum(1 for rec in data if rec.get("tag") == "FAM")
# Fetch counts from database
num_individuals_db = cur.execute("SELECT COUNT(*) FROM People;").fetchone()[0]
num_families_db = cur.execute("SELECT COUNT(*) FROM Families;").fetchone()[0]

# 3. Pointer referential integrity and type checks
missing_pointers = []   # pointers that reference an ID not in id_to_tag
wrong_type_pointers = []  # pointers that point to an existing ID but of wrong record type
# Also track bidirectional consistency for family links
spouse_mismatches = []  # spouse pointers not reciprocated
child_mismatches = []   # child pointers not reciprocated

for rec in data:
    # Traverse all children recursively to find pointer values
    stack = [rec]
    while stack:
        node = stack.pop()
        # Check if this node's value looks like a pointer (e.g., "@I1@" etc.)
        val = node.get("value")
        tag = node.get("tag")
        if val and val.startswith('@') and val.endswith('@'):
            target_id = val.strip('@')
            # Pointer must reference an existing record:
            if target_id not in id_to_tag:
                missing_pointers.append(f"{tag} -> {target_id}")
            else:
                # Check that the target record type matches the context
                target_type = id_to_tag[target_id]
                # Define expected target type based on pointer tag context
                expected_type = None
                if tag in ("HUSB", "WIFE", "CHIL", "ASSO"):  # pointers to individuals
                    expected_type = "INDI"
                elif tag in ("FAMC", "FAMS"):  # pointers to families
                    expected_type = "FAM"
                elif tag == "SOUR":  # source citation pointer
                    expected_type = "SOUR"
                elif tag == "REPO":  # repository pointer
                    expected_type = "REPO"
                elif tag == "NOTE":  # note record pointer
                    expected_type = "NOTE"
                elif tag == "SUBM":  # submitter pointer
                    expected_type = "SUBM"
                elif tag == "OBJE":  # multimedia object pointer
                    expected_type = "OBJE"
                # (Add other tags as needed based on GEDCOM grammar)
                if expected_type and target_type != expected_type:
                    wrong_type_pointers.append(f"{tag} -> {target_id} (expected {expected_type}, found {target_type})")
                # Check reciprocal links for families and individuals:
                if tag == "FAMS":
                    # Individual points to family as a spouse; ensure family has this individual as HUSB or WIFE
                    fam_id = target_id
                    spouse_role = id_to_tag.get(rec.get("id"))  # rec is the individual here
                    # spouse_role is just "INDI", we need to check family record content
                    fam_rec = next((x for x in data if x.get("id") == fam_id and x.get("tag") == "FAM"), None)
                    if fam_rec:
                        # if individual not listed as HUSB or WIFE in the family, record mismatch
                        roles = [child.get("value","") for child in fam_rec.get("children", []) if child["tag"] in ("HUSB","WIFE")]
                        if f"@{rec.get('id')}@" not in roles:
                            spouse_mismatches.append(f"Family {fam_id} missing spouse {rec.get('id')}")
                if tag in ("HUSB", "WIFE"):
                    # Family record points to spouse individual; ensure individual has FAMS pointing back
                    indi_id = target_id
                    indi_rec = next((x for x in data if x.get("id") == indi_id and x.get("tag") == "INDI"), None)
                    if indi_rec:
                        # if individual record has no FAMS pointing to this family, record mismatch
                        spouse_refs = [child.get("value","") for child in indi_rec.get("children", []) if child["tag"] == "FAMS"]
                        if f"@{rec.get('id')}@" not in spouse_refs:  # rec here is the family record
                            spouse_mismatches.append(f"Individual {indi_id} missing FAMS for family {rec.get('id')}")
                if tag == "FAMC":
                    # Individual points to family as child; ensure family lists this child
                    fam_id = target_id
                    fam_rec = next((x for x in data if x.get("id") == fam_id and x.get("tag") == "FAM"), None)
                    if fam_rec:
                        child_list = [child.get("value","") for child in fam_rec.get("children", []) if child["tag"] == "CHIL"]
                        if f"@{rec.get('id')}@" not in child_list:
                            child_mismatches.append(f"Family {fam_id} missing CHIL for individual {rec.get('id')}")
                if tag == "CHIL":
                    # Family points to child; ensure child has FAMC pointer back
                    indi_id = target_id
                    indi_rec = next((x for x in data if x.get("id") == indi_id and x.get("tag") == "INDI"), None)
                    if indi_rec:
                        fam_refs = [child.get("value","") for child in indi_rec.get("children", []) if child["tag"] == "FAMC"]
                        if f"@{rec.get('id')}@" not in fam_refs:  # rec is the family record
                            child_mismatches.append(f"Individual {indi_id} missing FAMC for family {rec.get('id')}")
        # Add children of this node to stack to traverse deeper
        for child in node.get("children", []):
            stack.append(child)

# 4. Essential field checks (e.g., NAME and SEX for individuals)
individuals_missing_name = [rec.get("id") for rec in data 
                             if rec.get("tag") == "INDI" 
                             and not any(child["tag"] == "NAME" for child in rec.get("children", []))]
individuals_missing_sex = [rec.get("id") for rec in data 
                            if rec.get("tag") == "INDI" 
                            and not any(child["tag"] == "SEX" for child in rec.get("children", []))]

# Close DB cursor
cur.close()
conn.close()

# Output a summary report
print("Validation Summary:")
print("-------------------")
# Top-level record checks
print(f"HEAD records found: {head_count} (expected 1)")
print(f"TRLR records found: {trlr_count} (expected 1)")
# Count checks
print(f"Individuals in JSON: {num_individuals_json}, in DB: {num_individuals_db}")
print(f"Families in JSON:    {num_families_json}, in DB: {num_families_db}")
# Pointer integrity checks
if missing_pointers:
    print(f"Missing target records for {len(missing_pointers)} pointer(s): {missing_pointers}")
if wrong_type_pointers:
    print(f"Pointer type mismatches ({len(wrong_type_pointers)}): {wrong_type_pointers}")
# Reciprocal consistency checks
if spouse_mismatches:
    print(f"Spouse link mismatches ({len(spouse_mismatches)}): {spouse_mismatches}")
if child_mismatches:
    print(f"Child link mismatches ({len(child_mismatches)}): {child_mismatches}")
# Essential field checks
if individuals_missing_name:
    print(f"Individuals missing NAME: {individuals_missing_name}")
if individuals_missing_sex:
    print(f"Individuals missing SEX: {individuals_missing_sex}")

# If no issues found, indicate success
if (head_count == 1 and trlr_count == 1 and num_individuals_json == num_individuals_db 
      and num_families_json == num_families_db and not missing_pointers 
      and not wrong_type_pointers and not spouse_mismatches 
      and not child_mismatches and not individuals_missing_name and not individuals_missing_sex):
    print("All checks passed. The parsed data and database appear consistent and valid.")
