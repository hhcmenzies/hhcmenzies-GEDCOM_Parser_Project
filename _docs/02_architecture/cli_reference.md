# CLI Reference (End-User)

_Last updated: 2026-02-09_

Source git commit: 3166192

End-user reference for the gedcom CLI.

## Global conventions
- **Input paths**: commands that accept GEDCOM take a filesystem path.
- **Output behavior**:
  - stats prints a summary to stdout.
  - export writes JSON to stdout by default; use --out/-o to write a file.
- **Exit codes**: non-zero on failure (missing file, parse error, config error).
- **Config loading and precedence**:
  - processing_config.yml is the active config (see gedcom doctor output).
  - If config behavior changes, update this section to match src/gedcom_parser/config.py.

## Commands

### gedcom (top-level)
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

### doctor
Validates environment wiring (imports, config path, expected project directories).
~~~
                                                                                                                                                                                                              
 Usage: gedcom doctor [OPTIONS]                                                                                                                                                                               
                                                                                                                                                                                                              
 Validate environment and basic project wiring. Keep this lightweight and deterministic.                                                                                                                      
                                                                                                                                                                                                              
+- Options --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| --help          Show this message and exit.                                                                                                                                                                |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
~~~

**Examples**
- gedcom doctor

### version
Prints package version, git commit, and project root.
~~~
                                                                                                                                                                                                              
 Usage: gedcom version [OPTIONS]                                                                                                                                                                              
                                                                                                                                                                                                              
 Print application + environment version details.                                                                                                                                                             
                                                                                                                                                                                                              
+- Options --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
| --help          Show this message and exit.                                                                                                                                                                |
+------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------+
~~~

**Examples**
- gedcom version

### stats
Reads a GEDCOM file and prints summary statistics.
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

**Examples**
- gedcom stats tests/data/gedcom_1.ged
- gedcom stats -v tests/data/gedcom_1.ged

### export
Exports GEDCOM data to JSON (stdout by default).
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

**Examples**
- gedcom export tests/data/gedcom_1.ged > _runtime/out.json
- gedcom export -o _runtime/out.json --pretty tests/data/gedcom_1.ged

## Troubleshooting
- **Import/module errors**: ensure the package is installed editable: pip install -e .
- **Config path issues**: run gedcom doctor and confirm the reported config_path exists.
- **Encoding issues**: if a GEDCOM file fails parsing, capture the error output and record the exporter/source.

