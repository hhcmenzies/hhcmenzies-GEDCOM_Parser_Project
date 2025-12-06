# GEDCOM Parsing Project Analysis and Refactoring Approach

Based on the provided project files, PyCharm inspection reports, and directory structure, I have identified multiple areas for improvement and necessary refactoring. Below is a systematic and detailed approach to address issues, improve performance, resolve duplication, and ensure compliance with GEDCOM 5.5.5.

## 1️⃣ Immediate Fixes in `schema.sql`

### Issues Identified (Annotator.xml)
- Several SQL syntax errors at multiple lines (lines 10, 11, 35, 36, 45, 46, 70).
- Errors related to incorrect or incomplete statements.
- Expected syntax (`GLOB, LIKE, MATCH, REGEXP`) was missing or improperly used.

### Solution Approach
1. **Manually validate SQL syntax** and ensure:
   - All table definitions follow proper `CREATE TABLE` syntax.
   - Constraints (`FOREIGN KEY`, `UNIQUE`, `INDEX`) are correctly applied.
   - Column data types are aligned with GEDCOM 5.5.5 standard.
   - `MATCH`, `LIKE`, `REGEXP` are correctly placed in `WHERE` clauses.
2. **Run the `schema.sql` independently** in SQLite3 or PostgreSQL to catch structural errors before integration.
3. **Cross-check the schema with `gedcom_schema.json`** (to be created next) to ensure consistency.

---

## 2️⃣ Refactor `database_utils.py` and `utilities.py` (Duplicated Code)

### Issues Identified (DuplicatedCode.xml & DuplicatedCode_aggregate.xml)
- **`database_utils.py` has duplicate code** in:
  - Lines **97-121** (duplicate utility function for database queries).
  - Lines **144-154** (column validation logic duplicated).
- **`utilities.py` has duplication** in:
  - Lines **116-123** (batch insert logic duplicated).
  - Lines **171-195** (log message formatting duplicated).

### Solution Approach
1. **Extract common functions into `utilities.py`**:
   - Move redundant batch insertion logic into a single function (`batch_insert`).
   - Move schema validation checks into `schema_validator.py`.
2. **Refactor `database_utils.py`**:
   - Remove duplicate validation code and instead call `validate_table_and_columns()` from `utilities.py`.
   - Ensure `execute_query()` is optimized to reduce redundancy.
3. **Reduce repeated error logging**:
   - Standardize exception handling to avoid redundant logging.
   - Centralize exception handling in `utilities.py` for reuse across scripts.

---

## 3️⃣ Improve `config.py` and Fix Compatibility Issues

### Issues Identified (PyCompatibilityInspection.xml)
- **Use of f-strings (`f"string"`) in Python 2.7 incompatible code.**
- **Usage of `pathlib` which is not available in Python 2.7.**

### Solution Approach
1. **Ensure compatibility with Python 3.x**:
   ```python
   import sys
   if sys.version_info < (3, 7):
       raise RuntimeError("Python 3.7+ is required for this project.")
   ```
2. **Replace `pathlib` with `os.path` where necessary**:
   ```python
   from pathlib import Path  # REPLACE with:
   import os
   ```
3. **Review all f-strings (`f"..."`) and replace with `.format()`** where needed for compatibility.

---

## 4️⃣ Enhance `validation.py` for GEDCOM Compliance

### Issues Identified (validation.py)
- Validation does not fully support all GEDCOM 5.5.5 standard tags.
- Lacks robust error reporting when encountering malformed GEDCOM entries.

### Solution Approach
1. **Expand the `VALID_TAGS` dictionary** to ensure **full support for GEDCOM 5.5.5**.
2. **Improve error handling and reporting**:
   - Add a `validate_dates()` function to check for properly formatted dates.
   - Check for missing required GEDCOM tags.
3. **Log validation errors to a separate file (`logs/gedcom_validation.log`)**:
   ```python
   logging.basicConfig(filename='logs/gedcom_validation.log', level=logging.INFO)
   ```

---

## 5️⃣ Optimize `parser.py` for Efficiency

### Issues Identified (parser.py)
- **Database connections (`conn`) are not always closed properly**.
- **Foreign key constraints might not be enforced**.

### Solution Approach
1. **Ensure proper database connection handling**:
   ```python
   try:
       conn = get_db_connection(db_path)
       cursor = conn.cursor()
       conn.execute("PRAGMA foreign_keys = ON")
   finally:
       if conn:
           conn.close()
   ```
2. **Refactor `parse_gedcom_file()`** to:
   - Validate schema **before** inserting data.
   - Log **successful** parsing progress after each major step.

---

## 6️⃣ Improve `parse_individuals.py` and `normalize_individuals.py`

### Issues Identified
- **Handles nicknames but does not store them properly** in the `individuals` table.
- **Might misplace surnames due to special character handling**.

### Solution Approach
1. **Ensure nickname extraction is properly stored**:
   ```python
   if nickname:
       raw_data.append(create_raw_data(indi_id, "NICK", None, nickname))
   ```
2. **Improve surname handling**:
   - Ensure surnames **inside slashes (`/Surname/`)** are properly extracted.
3. **Refactor `normalize_individual_names()` to remove duplicate name normalization logic**.

---

## 7️⃣ Implement Data Enrichment Enhancements

### Issues Identified in `enrich_individuals.py`
- **Phonetic and Romanized names are inconsistently stored**.
- **`soundex()` and `metaphone()` functions could be optimized**.

### Solution Approach
1. **Ensure phonetic & Romanized names are correctly stored**:
   - Validate that `enriched_names` table contains **all expected phonetic columns**.
2. **Refactor `soundex()` function**:
   - Optimize by **removing redundant character checks**.
3. **Add fallback logic for missing phonetic processing libraries**:
   ```python
   try:
       from epitran import Epitran
   except ImportError:
       logging.warning("Missing `epitran` module. Phonetic transcription will be disabled.")
   ```

---

## 8️⃣ Address Miscellaneous Issues

### Warnings from `ReassignedToPlainText.xml`
- **GEDCOM files (`.ged`) have been reassigned as plain text**.
- Ensure proper encoding detection for **UTF-8, UTF-16, ASCII**.

### Warnings from `PyCoverageInspection.xml`
- Some scripts lack **unit tests**.
- Consider writing unit tests for:
  - `parse_individuals.py`
  - `normalize_individuals.py`
  - `enrich_individuals.py`

### Warnings from `PyUnusedLocalInspection.xml`
- **Some functions declare variables but never use them**.
- Consider removing unused local variables after running `pylint`.

---

## ✅ Final Refactoring Plan (Step-by-Step Execution)
1. **Fix `schema.sql` syntax issues** and ensure consistency with `gedcom_schema.json`.
2. **Remove duplicated code in `database_utils.py` and `utilities.py`**.
3. **Fix compatibility issues in `config.py` (Python 3.7+ requirement, f-string fixes)**.
4. **Expand validation logic in `validation.py` (handle all GEDCOM 5.5.5 tags, validate dates, better error logging)**.
5. **Refactor `parser.py` to ensure structured database connections, logging, and schema validation**.
6. **Enhance `parse_individuals.py` to properly handle nicknames and surnames**.
7. **Optimize phonetic and Romanization logic in `enrich_individuals.py`**.
8. **Write unit tests to cover GEDCOM parsing logic**.

