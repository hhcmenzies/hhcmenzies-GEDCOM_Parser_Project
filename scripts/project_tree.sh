#!/usr/bin/env bash
tree -a \
  -I "*venv*|.git|__pycache__|.pytest_cache|node_modules|.DS_Store|.idea|.vscode" \
  > inventories/project_tree.txt
