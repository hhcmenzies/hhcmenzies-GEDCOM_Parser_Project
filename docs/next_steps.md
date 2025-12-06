# Next Steps: Roadmap for Resolving Issues and Aligning Scripts

## **Systematic Approach to Resolving All Issues and Aligning Scripts**
Based on the provided project files and the latest PyCharm inspection reports, I have systematically analyzed and categorized all identified issues across the scripts. Below is the step-by-step approach to resolving them.

---

## **1. Categorization of Issues**
After reviewing `db_manager.py`, `database_utils.py`, `schema_validator.py`, `gedcom_schema.json`, `schema.sql`, and other related scripts, I have categorized the issues into the following groups:

### **A. Schema & JSON Alignment Issues**
- Misalignment between `schema.sql` and `gedcom_schema.json`.
- Missing or incorrect column types (`DATE` vs. `TEXT`, `REAL` vs. `INTEGER`).
- Foreign key constraints need enforcing.
- Indexes missing for query optimization.

### **B. Database Connection & Execution Issues**
- Inconsistent database paths in `config.py` and `db_manager.py`.
- `database_utils.py` not handling errors properly.
- Potential failure in executing SQL schema scripts.

### **C. Code Duplications**
- Duplicate functions in `database_utils.py` and `utilities.py`.
- Redundant schema validation checks.

### **D. PyCharm-Flagged Errors & Warnings**
- Unresolved references to missing imports.
- Long lines exceeding 120 characters (`schema_validator.py`).
- Incorrect SQL syntax reported by `Annotator.xml`.
- Python 2.7 compatibility warnings (f-string issues).

### **E. Script Execution & Logging Issues**
- `db_manager.py` fails to log errors properly in some places.
- Logging configuration inconsistencies across scripts.
- Unvalidated file and directory paths.

---

## **2. Plan to Fix Issues: Script-by-Script Approach**
To ensure a systematic resolution, we will focus on fixing **one script at a time**, ensuring all changes align **before moving to the next script**.

| **Step** | **Script to Fix** | **Reason for Fixing First** | **Fixes to Apply** |
|----------|------------------|----------------------------|---------------------|
| ✅ **Step 1** | `schema.sql` & `gedcom_schema.json` | Fix database schema before modifying scripts | - Align column types, constraints, indexes, and foreign keys. |
| ✅ **Step 2** | `db_manager.py` | Handles database initialization & execution | - Ensure it properly loads schema, validates tables, and initializes the DB. |
| ✅ **Step 3** | `database_utils.py` | Core functions for database interactions | - Fix connection handling, remove redundant functions. |
| ✅ **Step 4** | `schema_validator.py` | Ensures DB structure aligns with `gedcom_schema.json` | - Improve validation checks, optimize logging, and auto-correct schema mismatches. |
| ✅ **Step 5** | `utilities.py` | Common functions used across the system | - Consolidate duplicate functions, ensure correct logging. |
| ✅ **Step 6** | `config.py` | Centralized configuration | - Ensure correct paths, logging, and directory creation. |
| ✅ **Step 7** | **Final Testing** | Validate entire pipeline | - Run `db_manager.py`, confirm successful database creation, and verify schema integrity. |

---

## **3. First Step: Fixing `schema.sql` & `gedcom_schema.json`**
Before modifying scripts, we **must first fix schema mismatches** to ensure that all scripts operate on a valid database.

### **Issues in `schema.sql`**
- Some column types **do not match** those in `gedcom_schema.json`.
- Missing **indexes** for optimized querying.
- Foreign key constraints **missing or incorrect**.

### **Issues in `gedcom_schema.json`**
- **Some required columns are missing**, making schema validation fail.
- Need to ensure it reflects the **final database structure**.

---

## **Next Steps**
✅ **Step 1**: I will now update **`schema.sql`** to ensure full alignment with `gedcom_schema.json`.
✅ Once that is done, we will move to `db_manager.py` to ensure the script correctly initializes the database.

---

This roadmap will ensure a structured, step-by-step resolution of all database and script issues. 🚀

