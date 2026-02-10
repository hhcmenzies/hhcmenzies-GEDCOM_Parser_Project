# Database Roadmap for GEDCOM Parsing System

## **1. Schema and Database Structure Refinements**

### **Outstanding Issues:**
- **Foreign Key Constraints:** Some are missing or incorrectly enforced (`schema.sql` does not fully validate relationships).
- **FTS5 Virtual Table Issues:** Full-text search (`fts_enriched_names`) has issues being dropped/recreated due to SQLite constraints.
- **Schema Compliance:** Certain tables/columns are non-standard per **GEDCOM 5.5.5**.
- **Indexes & Performance:** Missing indexes on frequently queried fields.
- **Schema & JSON Alignment Issues:** `schema.sql` and `gedcom_schema.json` are misaligned in column types (`DATE` vs `TEXT`, `REAL` vs `INTEGER`).

### **Action Items:**
✅ Validate **foreign key relationships** and ensure integrity with `PRAGMA foreign_key_check;`.
✅ Fix `fts_enriched_names` handling to **avoid SQLite restrictions on dropping virtual tables**.
✅ Align `schema.sql` with `gedcom_schema.json`, ensuring correct data types and **GEDCOM 5.5.5 compliance**.
✅ Optimize indexing strategy—**remove redundant indexes** and **add missing ones** for query speed.
✅ Implement **dynamic database naming** (`gedcom_<filename>.db` instead of a single static `gedcom_database.db`).

---

## **2. Database Management and Execution**

### **Outstanding Issues:**
- **Dynamic Database Management:** Scripts (`db_manager.py`, `config.py`) are **hardcoded to a single database file** instead of handling multiple databases dynamically.
- **Database Reset Behavior:** `db_manager.py` does not delete/reset the existing database before recreating it.
- **Schema Validation Before Insertion:** Some inserts **run before schema validation**, leading to errors.
- **Error Logging in `db_manager.py`:** Errors are logged inconsistently.

### **Action Items:**
✅ Modify `db_manager.py` and `config.py` to **handle multiple GEDCOM databases dynamically**.
✅ Implement **proper database reset** logic before schema re-initialization.
✅ Ensure **`validate_schema()` is executed before inserting data**.
✅ Improve error handling/logging—**ensure structured logging across all scripts**.

---

## **3. Parsing and Data Processing Enhancements**

### **Outstanding Issues:**
- **Missing GEDCOM 5.5.5 Name Components:** `parse_individuals.py` does **not extract all GEDCOM name components** (`GIVN`, `NPFX`, `SPFX`, `NSFX`).
- **Multiple Name Variations Not Handled:** **Birth name, married name, aliases (`ALIA`) are not stored correctly**.
- **Incorrect Nickname Extraction:** **Nicknames** are **not stored properly** in the `individuals` table.
- **Special Character Handling in Surnames:** Some surnames with `/slashes/` are **mishandled**.

### **Action Items:**
✅ Update `parse_individuals.py` to **extract ALL name components** (`GIVN`, `NPFX`, `SPFX`, etc.).
✅ Implement support for **multiple name variations per individual** (birth name, married name, alias).
✅ Ensure nicknames (`NICK`) are correctly stored in the `individuals` table.
✅ Fix **surname handling** to correctly extract names within `/slashes/`.

---

## **4. Data Enrichment and Normalization Improvements**

### **Outstanding Issues:**
- **Phonetic & Romanized Names:** Some names **don’t require phonetic enrichment**, but the script processes them anyway.
- **Hardcoded Enrichment Methods:** `individuals_enrich.py` **blindly applies all phonetic methods** instead of allowing configuration.
- **Diacritics Handling:** Some **name transformations remove accents incorrectly**.

### **Action Items:**
✅ Implement **selective enrichment** to **skip unnecessary phonetic transformations**.
✅ Modify `individuals_enrich.py` to **dynamically load settings from `config_name.json`**.
✅ Ensure **diacritics are preserved** when normalizing names.

---

## **5. Validation and Debugging Enhancements**

### **Outstanding Issues:**
- **Schema Validation Redundancies:** `schema_validator.py` and `utilities.py` contain **duplicate schema validation functions**.
- **GEDCOM Validation Gaps:** `validation.py` does **not fully validate all GEDCOM 5.5.5 tags**.
- **Foreign Key Integrity Not Checked Before Inserts:** Some records fail due to **missing references**.
- **File Encoding Handling:** Need to enforce **UTF-8/UTF-16 compliance**.

### **Action Items:**
✅ Consolidate **schema validation functions** to a single location (`schema_validator.py`).
✅ Expand `validation.py` to **validate all GEDCOM 5.5.5 tags**.
✅ Ensure `PRAGMA foreign_key_check;` **runs before inserts** to catch missing references early.
✅ Enforce **UTF-8/UTF-16 file encoding compliance** in `parser.py`.

---

## **6. Performance & Logging Enhancements**

### **Outstanding Issues:**
- **Parsing Logs Not Structured Properly:** Some logs are **printed** instead of being logged.
- **Foreign Key Integrity Errors Not Logged:** If foreign key constraints fail, **errors are not logged**.
- **Batch Insert Performance Issues:** `utilities.py` **does not use optimal batch sizes**, causing **memory issues on large GEDCOM files**.

### **Action Items:**
✅ Standardize **structured logging** in all scripts (`main.py`, `db_manager.py`, `validation.py`).
✅ Ensure **foreign key integrity errors are properly logged**.
✅ Optimize `batch_insert()` in `utilities.py` to **improve performance on large GEDCOM files**.

---

## **7. Refactoring and Code Cleanup**

### **Outstanding Issues:**
- **Duplicate Functions:** `database_utils.py` and `utilities.py` **have redundant functions**.
- **Incorrect Use of `Pathlib`:** `config.py` uses `Pathlib`, but `os.path` should be used for compatibility.
- **Python 2.7 Compatibility Warnings:** Some f-string usage is **not compatible with Python 2.7**.

### **Action Items:**
✅ **Remove duplicate functions** from `database_utils.py` and `utilities.py`.  
✅ Standardize file path handling (**replace `Pathlib` with `os.path` where needed**).  
✅ Ensure **Python 3.x compatibility** by **removing outdated code**.  

---

## **📌 Prioritized Execution Plan**

| Step | Task | Script Affected |
|------|------|----------------|
| ✅ **1** | Fix `schema.sql` & `gedcom_schema.json` misalignment | `schema.sql`, `gedcom_schema.json` |
| ✅ **2** | Implement dynamic database creation | `db_manager.py`, `config.py` |
| ✅ **3** | Validate foreign key integrity before inserts | `db_manager.py`, `parser.py` |
| ✅ **4** | Extract missing name components | `parse_individuals.py` |
| ✅ **5** | Support multiple name variations | `normalize_individuals.py` |
| ✅ **6** | Implement selective phonetic enrichment | `individuals_enrich.py` |
| ✅ **7** | Expand GEDCOM validation | `validation.py` |
| ✅ **8** | Optimize batch processing for large GEDCOM files | `utilities.py` |
| ✅ **9** | Final testing & performance optimization | All scripts |

---

## **🔹 Conclusion**
Once the **schema and database structure are fully aligned**, the focus will be on **parsing improvements**, **enrichment refinements**, and **performance optimizations**. This **step-by-step execution** ensures a **robust, scalable, and fully GEDCOM 5.5.5-compliant system**.

