# Roadmap for GEDCOM Parsing and Processing Software System

## **Overview**
This document outlines the comprehensive next steps for the **GEDCOM parsing and processing software system**. It consolidates previous roadmap versions and integrates new recommendations for **enhancements, refactoring, performance optimizations, and full compliance with GEDCOM 5.5.5 specifications**. This roadmap ensures all scripts are systematically improved **without loss of detail**, while optimizing for **scalability, maintainability, and robustness**.

---

## **Current Strengths of the System**
The GEDCOM processing system is **well-structured and modular**, adhering to **best practices** in software development. Its key strengths include:

### **1. Modular Structure**
- **Separation of Concerns:**
  - **Parsing:** `parser.py` extracts and processes raw GEDCOM data.
  - **Validation:** `validation.py` ensures compliance with GEDCOM 5.5.5.
  - **Normalization:** `individuals_normalization.py` standardizes name components.
  - **Enrichment:** `individuals_enrich.py` (moved to `enrichments/`) enhances phonetic and Romanized fields.
- **Logging Standardization:** All scripts will log to `GEDCOM_Parser/logs/` for centralized debugging.

### **2. Database Schema Alignment**
- Fully aligns with **GEDCOM 5.5.5 specifications**.
- Optimized indexing for **query performance and batch processing**.
- **Schema Enhancements:**
  - **New enriched names table** separates parsed individual names from their phonetic and Romanized versions.
  - **Reinstated `valid_tags`, `places`, `associations`, `custom_tags`, `citations`, and `media` tables** to maintain full functionality.
  - **Expanded constraints for GEDCOM structures (`EVEN`, `SOUR`, `REPO`)**.
  - **Error tracking in `parsing_errors` table**.

### **3. Data Processing Enhancements**
- Supports **phonetic transformations** (**Soundex, Double Metaphone, IPA**).
- **Romanization methods:** **ASCII, Pinyin, Hepburn, Wade-Giles, ISO-9**, etc.
- **Batch processing improvements** for handling large GEDCOM files.
- **Progress tracking and structured console printouts**.

---

## **Key Challenges & Areas for Improvement**
Several key areas require refactoring, enhancements, and optimizations:

### **1. Normalization & Name Processing**
- Ensure **consistent formatting** for `nickname`, `prefix`, and `suffix` fields.
- Implement **Levenshtein distance** for improved name similarity detection.
- **Normalize middle names** using a defined logic to enhance accuracy.

### **2. Enrichment Enhancements**
- **Move `individuals_enrich.py` to `enrichments/`** for improved modularity.
- Expand phonetic and Romanized support dynamically via `config.py`.
- Improve phonetic transformations with additional language handling.
- Ensure **all Romanized & phonetic fields are validated** before processing.
- Improve logging to **identify and debug missing fields**.
- Handle **missing `config.json` gracefully with defaults**.
- Preserve **diacritics in `clean_name()`** to avoid breaking name accuracy.
- **New enriched names table** to store phonetic and Romanized names separately from core `individuals` data.

### **3. Schema Refinements & Performance Optimizations**
- **Restore all omitted tables (`valid_tags`, `places`, `associations`, `custom_tags`, `citations`, `media`)**.
- Introduce **default values for optional fields** to prevent NULL issues.
- Create **indexes on frequently queried columns** for efficiency.
- **Enhance schema constraints:**
  - **Split `individuals` table into core and enriched names tables**.
  - **Expand `EVEN`, `SOUR`, and `REPO` schema support**.
  - **Ensure UTF-8/UTF-16 encoding enforcement** per GEDCOM 5.5.5.

### **4. GEDCOM 5.5.5 Compliance Enhancements**
- **Strict enforcement of GEDCOM tag validation**.
- Enforce **line length restrictions (≤255 characters)**.
- Validate **file encoding consistency (UTF-8 or UTF-16 only)**.
- Ensure **one terminator per file (CR, LF, or CRLF)**.
- Implement **strict whitespace compliance for CONT & CONC handling**.
- Expand parsing for **events (`EVEN`), sources (`SOUR`), repositories (`REPO`), and notes (`NOTE`)**.

### **5. Performance & Debugging**
- Implement **progress tracking and console printouts** across all scripts.
- **Enable structured logging** for enriched names processing.
- Introduce **log rotation and error tracking** to avoid log bloating.
- Utilize **multiprocessing** for handling large GEDCOM files.

---

## **Action Items Per Script**

### **1. `config.py` (Configuration Management)**
✅ **Enhancements:**
- Support **multiple environments (dev/prod)**.
- Wrap `json.load(file)` with **try-except** for error handling.
- Ensure **configurations are dynamically modifiable**.

---

### **2. `schema.sql` (Database Schema)**
✅ **Immediate Refactoring:**
- **Restore all omitted tables while incorporating upgrades**.
- **Split `individuals` table into two:**
  - One for **core individual data**.
  - One for **phonetic and Romanized enriched names**.
- **Ensure compliance with GEDCOM 5.5.5 structured data**.
- Optimize **indexes and constraints** for better performance.

---

### **3. `individuals.py` (Individual Record Processing)**
✅ **Enhancements:**
- **Improve duplicate checking logic** before inserting records.
- **Fix nickname regex to include brackets `[]`** in `NICKNAME_PATTERN`.
- **Ensure proper handling of new enriched names schema**.

---

### **4. `individuals_enrich.py` (Enrichment Process)**
✅ **Major Refactoring:**
- Move to `GEDCOM_Parser/enrichments/` and update **import paths**.
- Allow **dynamic phonetic transformation selection** via `config.py`.
- Improve **bulk database insert performance**.
- **Ensure enriched names are stored in the new enriched names table**.

---

## **Immediate Next Steps (Systematic Refactoring Order)**
✅ **Step 1:** Update `schema.sql` to **restore omitted functionality and apply upgrades**.
✅ **Step 2:** Modify `individuals.py` and `individuals_enrich.py` to reflect schema changes.
✅ **Step 3:** Implement **structured console printouts and log metrics** across all scripts.
✅ **Step 4:** Validate **database schema integrity and parsing workflow**.
✅ **Step 5:** Expand `validation.py` to enforce **GEDCOM 5.5.5 rules**.
✅ **Step 6:** Optimize `parser.py` for **correct handling of `EVEN`, `SOUR`, `REPO`, and NOTE tags**.

---

## **Final Summary**
By implementing these structured upgrades, the GEDCOM parsing system will be:
✅ **Efficient, scalable, and optimized for large-scale processing**.
✅ **Fully compliant with GEDCOM 5.5.5 standards**.
✅ **Capable of modular and extensible enrichment**.
✅ **Prepared for future integration with genealogy APIs and visualization tools**.

This roadmap ensures that each script is methodically refactored to **achieve full GEDCOM compliance, data integrity, and performance excellence**.