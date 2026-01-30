#!/usr/bin/env bash
# Stage 3: Load Custom Tags into Database (Optional)
# Description: Inserts the custom tags report data into a database for persistent storage and analysis.
# Input:  inventory/latest/custom_tags_report.import2.json
# (Configure DB connection settings inside the Python script or via environment as needed)
echo "Loading custom tags into the database..."
python scripts/load_custom_tags_to_db.py \
    -i inventory/latest/custom_tags_report.import2.json
