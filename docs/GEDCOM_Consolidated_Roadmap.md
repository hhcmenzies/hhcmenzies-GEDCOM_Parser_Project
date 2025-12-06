# GEDCOM Parsing & Processing System - Consolidated Roadmap

## **Overview**
This document consolidates all roadmap versions into a **single comprehensive plan** for enhancing, refactoring, 
and optimizing the **GEDCOM Parsing and Processing Software System**. It ensures alignment with **GEDCOM 5.5.5 specifications**, 
improves **performance and maintainability**, and **systematically upgrades scripts and database structure**.

---

## **1. Database & Schema Refinements**
- ✅ Ensure **full GEDCOM 5.5.5 schema compliance**.
- ✅ Restore omitted tables: **valid_tags, places, associations, citations, media**.
- ✅ Implement **foreign key integrity enforcement**.
- ✅ Introduce **dynamic database naming** (e.g., `gedcom_<filename>.db`).
- ✅ Validate schema before inserting data using `schema_validator.py`.

---

## **2. Parsing & Data Processing Enhancements**
- ✅ Ensure **missing GEDCOM 5.5.5 name components** (GIVN, NPFX, NSFX, SPFX, etc.) are parsed.
- ✅ Extract **multiple name variations** per individual (birth name, married name, aliases).
- ✅ Implement **nickname extraction and proper formatting**.
- ✅ Handle **missing data gracefully** by marking placeholders as "Unknown".
- ✅ Standardize GEDCOM event handling (`EVEN`, `SOUR`, `REPO`, `NOTE`).

---

## **3. Normalization & Enrichment**
- ✅ Expand phonetic and **Romanized name enrichment dynamically** (configurable via `config_name.json`).
- ✅ Move **enrichment processing to `enrichments/` module** for better organization.
- ✅ Ensure **diacritics are preserved** while normalizing names.
- ✅ Optimize **batch processing for large GEDCOM files**.
- ✅ Enable **selective enrichment** (only apply phonetic/Romanized transformations as needed).

---

## **4. Validation & Debugging**
- ✅ Enforce strict **GEDCOM tag validation** before processing.
- ✅ Validate **file encoding consistency (UTF-8/UTF-16 only)**.
- ✅ Implement **structured logging** across all modules.
- ✅ Enable **database schema validation before insertion**.
- ✅ Ensure **foreign key integrity validation before processing records**.

---

## **5. Performance Optimization**
- ✅ Implement **threading/multiprocessing** for parallelized parsing.
- ✅ Optimize **indexing for frequently queried fields**.
- ✅ Improve **progress tracking and console printouts**.
- ✅ Implement **log rotation** to prevent bloated log files.
- ✅ Enhance **batch processing efficiency**.

---

## **6. Refactoring & Code Cleanup**
- ✅ Reduce duplicate functions (`database_utils.py` and `utilities.py`).
- ✅ Refactor scripts for better **modularization and maintainability**.
- ✅ Use configuration files (`config.py`, `config_name.json`) to enable dynamic control.
- ✅ Ensure **Python 3.x compatibility** by removing outdated code.
- ✅ Improve **error handling and exception logging**.

---

## **7. Action Plan (Systematic Refactoring Order)**
| Step | Script | Enhancements & Fixes |
|------|--------|----------------------|
| ✅ 1 | `db_manager.py` | Ensure **database resets before recreation** and enforces **foreign key integrity**. |
| ✅ 2 | `parser.py` | Call **enrichment step**, validate **foreign keys**, and enable **structured debugging logs**. |
| ✅ 3 | `parse_individuals.py` | Extract **missing name components** (GIVN, NPFX, etc.). |
| ✅ 4 | `normalize_individuals.py` | Handle **multiple name variations** & alias names. |
| ✅ 5 | `enrich_individuals.py` | Enable **selective enrichment** & load settings from `config_name.json`. |
| ✅ 6 | `validation.py` | Ensure **GEDCOM compliance & schema validation** before processing. |
| ✅ 7 | `utilities.py` | Improve **error handling and automatic schema correction**. |
| ✅ 8 | `main.py` | Ensure **correct sequence execution**, **logging**, and **schema validation** before enrichment. |

---

## **8. Next Steps**
1. **Finalize all refactoring changes**.
2. **Conduct rigorous testing** with various GEDCOM files.
3. **Optimize performance (threading, multiprocessing, indexing)**.
4. **Run static analysis and profiling to eliminate bottlenecks**.
5. **Expand documentation for future development**.

---

## **Conclusion**
Upon completion, this roadmap will ensure a **robust, scalable, and fully compliant GEDCOM processing system** ready for broader use and expansion. 🚀
