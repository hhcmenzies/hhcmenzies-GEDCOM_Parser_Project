# SQL Schema Review and Upgrade Roadmap

## **1. Overview**
This document outlines the SQL schema review, its evolution, and our current objectives for developing a robust, optimized, and normalized database structure compliant with **GEDCOM 5.5.5**. It also details the planned refactoring of related Python scripts to support dynamic database management per GEDCOM file.

---
## **2. Where We Were**
Previously, the database schema contained inconsistencies, redundancies, and structural inefficiencies that hindered the smooth parsing, storage, and retrieval of GEDCOM data.

### **Identified Issues:**
- **Foreign Key Constraints:** Some constraints were missing or incorrectly configured.
- **FTS5 Virtual Table Issues:** Attempts to drop and recreate `fts_enriched_names` and related tables led to errors due to SQLite restrictions.
- **Schema Compliance:** Some tables and columns were non-standard per **GEDCOM 5.5.5**.
- **Indexes & Performance:** Some indexes were redundant or missing on key fields.
- **Database Naming Convention:** All parsed GEDCOM files were stored in the same `gedcom_database.db` instead of dynamically creating **one per file** (e.g., `gedcom_19.ged` → `gedcom_19.db`).
- **Script Dependencies:** Existing scripts (e.g., `manage_db.py`, `config.py`) were hardcoded to work with a single database file, lacking the ability to manage multiple databases dynamically.

---
## **3. What We’re Accomplishing**
The goal is to implement a **fully normalized, scalable, and efficient schema** that aligns with GEDCOM 5.5.5, while improving database management and performance.

### **Objectives:**
✅ **Schema Review & Correction:** Ensure compliance with GEDCOM 5.5.5 and fix outstanding issues.
✅ **Full-Text Search (FTS5) Handling:** Properly structure `fts_enriched_names` without corruption.
✅ **Dynamic Database Creation:** Implement database naming based on parsed GEDCOM file.
✅ **Index Optimization:** Remove redundant indexes and add missing ones.
✅ **Foreign Key Integrity:** Validate and enforce proper relationships.
✅ **Script Refactoring:** Update `manage_db.py` and `config.py` to handle dynamic databases.
✅ **Schema Export & Validation:** Finalize schema and confirm with test GEDCOM files.

---
## **4. Where We Are Now**
### **Current Status:**
- The schema is being analyzed for compliance with GEDCOM 5.5.5.
- Attempts to delete and recreate FTS5 tables have caused structural issues.
- The `.schema` export was initiated to preserve the existing structure for review.
- A roadmap for refactoring the Python scripts is in place.

### **Pending Fixes:**
- Validate all foreign key relationships.
- Ensure **proper handling of virtual tables (FTS5)** in SQLite.
- Confirm that schema changes don’t break existing data.
- Implement **dynamic database naming** within all related scripts.

---
## **5. Immediate Next Steps**
### **Step 1: Save and Share Schema**
➡️ **Run the following in CLI to save the schema:**
```sql
.output current_schema.sql
.schema
.output
```
➡️ **Share `current_schema.sql` for analysis.**

### **Step 2: Schema Review & Corrections**
➡️ I will analyze and provide **corrective SQL commands** to:
   - Fix any missing constraints.
   - Normalize structure for GEDCOM 5.5.5 compliance.
   - Resolve FTS5 issues correctly.
   - Optimize indexing and relationships.

### **Step 3: Implement Dynamic Database Naming**
➡️ Modify `manage_db.py` and `config.py` to:
   - Create a **new database per GEDCOM file.**
   - Delete any existing database before creating a fresh one.
   - Ensure all queries and scripts adapt to the new structure.

### **Step 4: Validation & Testing**
➡️ Run schema and integrity checks:
```sql
PRAGMA integrity_check;
PRAGMA foreign_key_check;
```
➡️ Test against multiple GEDCOM files and validate parsing.

---
## **6. Future Milestones**
- **Full Testing:** Validate GEDCOM parsing across multiple databases.
- **Performance Optimizations:** Ensure query efficiency with real-world GEDCOM data.
- **Backup & Migration Strategy:** Develop a system for safe migrations and backups.
- **Comprehensive Documentation:** Provide clear documentation on database usage and script interactions.

---
## **7. Conclusion**
This roadmap ensures that the database structure is:
✅ **Fully compliant with GEDCOM 5.5.5.**  
✅ **Efficient and optimized for performance.**  
✅ **Dynamically scalable to handle multiple GEDCOM files.**  
✅ **Integrated seamlessly with the Python scripts.**

By following these steps, we will establish a **practical, robust, and maintainable** database system that supports flexible and efficient GEDCOM parsing.

**Next Step: Share the exported schema for detailed SQL corrections.**

