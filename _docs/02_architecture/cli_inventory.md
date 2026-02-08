# CLI Inventory (Current Surface)

_Last updated: 2026-02-08_

This document is the authoritative snapshot of the current CLI surface and its module mapping.

## A) CLI help (generated)

Source git commit: e6bff98

~~~
                                                                                                                                                                                                              
 Usage: gedcom [OPTIONS] COMMAND [ARGS]...                                                                                                                                                                    
                                                                                                                                                                                                              
 GEDCOM parser, inspector, and exporter                                                                                                                                                                       
                                                                                                                                                                                                              
+- Options --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| --help          Show this message and exit.                                                                                                                                                                |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
+- Commands -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| doctor   Validate environment and basic project wiring.                                                                                                                                                    |
|          Keep this lightweight and deterministic.                                                                                                                                                          |
| version  Print application + environment version details.                                                                                                                                                  |
| export   Export GEDCOM data to JSON (stdout by default).                                                                                                                                                   |
| stats    Show summary statistics for a GEDCOM file.                                                                                                                                                        |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
~~~

## Command: stats

~~~
                                                                                                                                                                                                              
 Usage: gedcom stats [OPTIONS] GEDCOM                                                                                                                                                                         
                                                                                                                                                                                                              
 Show summary statistics for a GEDCOM file.                                                                                                                                                                   
                                                                                                                                                                                                              
+- Arguments ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| *    gedcom      PATH  [required]                                                                                                                                                                          |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
+- Options --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| --verbose  -v        Enable rich logging                                                                                                                                                                   |
| --help               Show this message and exit.                                                                                                                                                           |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
~~~

## Command: export

~~~
                                                                                                                                                                                                              
 Usage: gedcom export [OPTIONS] GEDCOM                                                                                                                                                                        
                                                                                                                                                                                                              
 Export GEDCOM data to JSON (stdout by default).                                                                                                                                                              
                                                                                                                                                                                                              
+- Arguments ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| *    gedcom      PATH  [required]                                                                                                                                                                          |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
+- Options --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| --out      -o      PATH  Write output to file instead of stdout                                                                                                                                            |
| --pretty                 Pretty-print JSON                                                                                                                                                                 |
| --verbose  -v            Enable rich logging                                                                                                                                                               |
| --help                   Show this message and exit.                                                                                                                                                       |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
~~~

## Command: doctor

~~~
                                                                                                                                                                                                              
 Usage: gedcom doctor [OPTIONS]                                                                                                                                                                               
                                                                                                                                                                                                              
 Validate environment and basic project wiring. Keep this lightweight and deterministic.                                                                                                                      
                                                                                                                                                                                                              
+- Options --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| --help          Show this message and exit.                                                                                                                                                                |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
~~~

## Command: version

~~~
                                                                                                                                                                                                              
 Usage: gedcom version [OPTIONS]                                                                                                                                                                              
                                                                                                                                                                                                              
 Print application + environment version details.                                                                                                                                                             
                                                                                                                                                                                                              
+- Options --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| --help          Show this message and exit.                                                                                                                                                                |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
~~~

## B) Module map (implementation)

~~~
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\__init__.py
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\__pycache__\__init__.cpython-314.pyc
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\__pycache__\app.cpython-314.pyc
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\__pycache__\utils.cpython-314.pyc
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\app.py
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\commands\__init__.py
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\commands\__pycache__\__init__.cpython-314.pyc
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\commands\__pycache__\doctor.cpython-314.pyc
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\commands\__pycache__\export.cpython-314.pyc
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\commands\__pycache__\stats.cpython-314.pyc
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\commands\__pycache__\version.cpython-314.pyc
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\commands\doctor.py
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\commands\export.py
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\commands\stats.py
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\commands\version.py
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\cli\utils.py
~~~

