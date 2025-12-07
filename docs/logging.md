# Logging Guide

## Configuration inventory
- `config/gedcom_parser.yml`
  - `paths.logs_dir`: directory for all log files (defaults to `logs/`).
  - `logging.level`: base level (e.g., `INFO`, `DEBUG`).
  - `logging.file`: master log filename (defaults to `gedcom_parser.log`).
  - `logging.rotate`: enable 5 MB rotating files with 5 backups when `true`.
  - `debug`: when `true`, forces DEBUG output across handlers.
- `src/gedcom_parser/config.py`: loader for the YAML configuration used by the logger.

## Entry point
- Centralized in `src/gedcom_parser/logging/logger.py` and re-exported via
  `gedcom_parser.logging` (and `gedcom_parser.logger` for compatibility).
- Use `get_logger(__name__)` inside modules to inherit the shared console and
  master handlers. Each module also writes to its own file using the pattern
  `logs/<module_path>.log` (dots replaced with underscores).

## Handler/formatter contract
- Console handler: standard format `'%(asctime)s [%(levelname)s] %(name)s: %(message)s'`
  with timestamps in `%Y-%m-%d %H:%M:%S`.
- Master file handler: writes to `<logs_dir>/<logging.file>` with the same
  formatter; rotates when `logging.rotate` is `true`.
- Module file handler: one per module using `get_logger`, inherits the project
  formatter and respects the debug flag for log levels.

## Usage guidelines
- Always import via `from gedcom_parser.logging import get_logger` and initialize
  with `log = get_logger(__name__)`.
- Avoid configuring `logging.basicConfig` in modules; rely on the centralized
  setup instead.
- Use the YAML `debug` flag or `logging.level` to control verbosity in all
  modules consistently.
