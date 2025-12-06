Step-by-Step Analysis of Each Script
I will check schema alignment, missing fields, and any inconsistencies before we refactor anything.

1️⃣ parser.py - GEDCOM Parsing Orchestration
✅ What Works

Correctly initializes the database.
Validates the GEDCOM file before parsing.
Calls process_individuals() and normalize_individual_names() in the correct sequence.
⚠️ Issues

Missing Call to enrich_individual_names()

It normalizes individuals but does not enrich names.
Fix: Call enrich_individual_names(conn) after normalization.
Foreign Key Enforcement

The script enables foreign keys via PRAGMA foreign_keys = ON, but does not check if foreign key integrity holds.
Fix: Run PRAGMA foreign_key_check; before inserting individuals.
2️⃣ individuals.py - Extracting Raw Names from GEDCOM
✅ What Works

Extracts NAME, NICK, SEX fields from GEDCOM.
Uses batch insertion for efficiency.
⚠️ Issues

Missing GEDCOM 5.5.5 Name Tags
Currently only extracts NAME, NICK, and SEX.
GEDCOM 5.5.5 allows:
NPFX (Prefix)
GIVN (Given Name)
SPFX (Surname Prefix)
SURN (Surname)
NSFX (Suffix)
Fix: Update parse_individual_record() to extract these name components.
3️⃣ individuals_normalization.py - Normalizing Names
✅ What Works

Converts raw names into structured fields in the individuals table.
Removes duplicates.
Maps GEDCOM tags to database fields correctly.
⚠️ Issues

No Handling for Name Variations

It currently assumes each individual has only one primary name.
GEDCOM 5.5.5 allows multiple name variations (e.g., birth name, married name).
Fix: Support multiple names per individual in the individuals table.
No Handling of ALIA (Alias) Tag

If an individual has an alias, it should be stored.
Fix: Extract ALIA names into a separate row or field.
4️⃣ individuals_enrich.py - Enriching Names
✅ What Works

Pulls normalized names from individuals.
Inserts phonetic & Romanized variations into enriched_names.
⚠️ Issues

No Option for Selective Enrichment

It enriches all names indiscriminately, but some names may already be phonetic (e.g., English names).
Fix: Check if enrichment is necessary before inserting.
Hardcoded Enrichment Methods

The script assumes all phonetic methods should be applied, but some GEDCOM files may only require specific methods.
Fix: Use config_name.json to specify which enrichment methods to use.
5️⃣ db_manager.py - Database Setup
✅ What Works

Correctly creates the SQLite database.
Executes the new schema correctly.
Runs VACUUM; for database optimization.
⚠️ Issues

Does Not Automatically Drop Existing Database
The schema drops tables, but not the entire database.
Fix: Before initializing, delete the existing .db file if it exists.
6️⃣ validation.py - GEDCOM Validation
✅ What Works

Ensures the file is in proper GEDCOM format.
Checks for malformed records.
⚠️ Issues

Does Not Validate Against Schema
It checks the file but does not check the database structure.
Fix: Use validate_database_schema() before parsing starts.
7️⃣ utilities.py - Helper Functions
✅ What Works

batch_insert() improves performance.
validate_table_and_columns() ensures tables exist.
⚠️ Issues

Does Not Handle Missing Columns
It logs errors but does not attempt to fix schema issues.
Fix: If columns are missing, prompt to re-run db_manager.py.
8️⃣ main.py - Full Workflow Execution
✅ What Works

Calls all scripts in the correct order.
Handles logging properly.
⚠️ Issues

Does Not Log Foreign Key Integrity Errors

Fix: Run PRAGMA foreign_key_check; before inserting normalized names.
Runs Enrichment Even if Schema is Invalid

If parsing fails, it still tries to enrich.
Fix: Only run enrichment if previous steps were successful.
🛠 Next Steps
Now that we've fully assessed the scripts, we can systematically refactor them in the following order:

Step	Script to Fix	Fixes Needed
✅ 1	db_manager.py	Ensure database is deleted before recreation
✅ 2	parser.py	Call enrichment step & validate foreign keys
✅ 3	individuals.py	Extract missing name components (GIVN, NPFX, etc.)
✅ 4	individuals_normalization.py	Handle multiple name variations & alias names
✅ 5	individuals_enrich.py	Optimize selective enrichment & use config_name.json
✅ 6	validation.py	Ensure database schema matches schema.sql
✅ 7	utilities.py	Fix missing columns instead of just logging errors
✅ 8	main.py	Ensure proper sequence & check schema before enrichment
🔹 How We’ll Proceed
Now that we have a structured roadmap, we will:

Work on one script at a time, ensuring it aligns with the new schema.
Test each script after refactoring to verify correctness.
Ensure all scripts work seamlessly together.