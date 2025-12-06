#!/usr/bin/env python3
import sys
import os

# Add the src directory to the module search path
ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from gedcom_parser.main import main

if __name__ == "__main__":
    main()
