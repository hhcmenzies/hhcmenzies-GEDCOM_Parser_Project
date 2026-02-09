# CLI Modules & Command Surface (Generated Snapshot)

_Last updated: 2026-02-09_


This snapshot is generated from the current source tree and CLI help output. Regenerate after any CLI change.

## A) CLI help output

### gedcom --help
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

### gedcom doctor --help
~~~
                                                                                                                                                                                                              
 Usage: gedcom doctor [OPTIONS]                                                                                                                                                                               
                                                                                                                                                                                                              
 Validate environment and basic project wiring. Keep this lightweight and deterministic.                                                                                                                      
                                                                                                                                                                                                              
+- Options --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| --help          Show this message and exit.                                                                                                                                                                |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
~~~

### gedcom version --help
~~~
                                                                                                                                                                                                              
 Usage: gedcom version [OPTIONS]                                                                                                                                                                              
                                                                                                                                                                                                              
 Print application + environment version details.                                                                                                                                                             
                                                                                                                                                                                                              
+- Options --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| --help          Show this message and exit.                                                                                                                                                                |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
~~~

### gedcom stats --help
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

### gedcom export --help
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

## B) CLI implementation file inventory

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

## C) Command registration (Typer wiring references)

~~~

~~~

## D) Config entrypoints referenced by parser/CLI

~~~
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\enrichment\event_scoring.py:21: from gedcom_parser.config import get_config
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\enrichment\event_scoring.py:27: def get_config():
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\enrichment\event_scoring.py:60: cfg = get_config()
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\enrichment\place_version_builder.py:62: - Optional YAML config file (config/gedcom_parser.yml) if PyYAML is installed
H:\Projects\GEDCOM_Parser_Project\src\gedcom_parser\enrichment\place_version_builder.py:505: p.add_argument("--config", default="config/gedcom_parser.yml", help="Optional YAML config path")
~~~

