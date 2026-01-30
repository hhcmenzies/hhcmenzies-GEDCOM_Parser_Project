#!/usr/bin/env bash
set -euo pipefail

echo "Starting GEDCOM Parser Project reorganization..."

# 1. Create new directories for the standardized layout
mkdir -pv src/gedcom_parser/enrichment src/gedcom_parser/schema src/gedcom_parser/validation
mkdir -pv scripts archive/scripts archive/datasets archive/docs archive/logs archive/outputs

# 2. Move enrichment/normalization scripts into src/gedcom_parser/enrichment/
echo "Moving enrichment and normalization modules into src/gedcom_parser/enrichment/..."
mv -v src/gedcom_parser/postprocess/*.py src/gedcom_parser/enrichment/ 2>/dev/null || true  # move all postprocess scripts
# (If any enrichment scripts were at root or other locations, move them as well)
if [ -f media_normalizer.py ]; then mv -v media_normalizer.py src/gedcom_parser/enrichment/; fi
if [ -f ma_notables_pipeline.py ]; then mv -v ma_notables_pipeline.py src/gedcom_parser/enrichment/; fi

# 3. Move and consolidate GEDCOM schema files under schemas/
echo "Consolidating schema definition files under schemas/..."
mkdir -pv schemas
# Move any schema or tag-definition files from datasets or elsewhere into schemas/
if [ -f datasets/gedcom_schema.json ]; then mv -v datasets/gedcom_schema.json schemas/; fi
if [ -f datasets/gedcom_tags.json ]; then mv -v datasets/gedcom_tags.json schemas/; fi
if [ -f datasets/gedcom_tags_meta_schema.json ]; then mv -v datasets/gedcom_tags_meta_schema.json schemas/; fi
if [ -f datasets/name_block_schema.json ]; then mv -v datasets/name_block_schema.json schemas/; fi  # if it was in datasets
# Also move any other *.schema.json, *schema_draft.json, or canonical tag files into schemas/
shopt -s nullglob
for f in *gedcom5*.json canonical_*_gedcom*.json; do
    case "$f" in
        *gedcom*schema*.json|canonical_tag_dictionary_*.json|canonical_grammar_placements_*.json|*tag_context_index*.json)
            mv -v "$f" schemas/ 2>/dev/null || true ;;
    esac
done
shopt -u nullglob

# 4. Normalize datasets location (non-schema JSON stays in datasets/)
# (No action needed if they are already in datasets/; ensure that directory exists and old dataset files not needed are archived)
mkdir -pv datasets
# If any enrichment data files were outside datasets (e.g., in src or root), move them into datasets/.
if [ -f src/gedcom_parser/data/occupation_keywords.json ]; then mv -v src/gedcom_parser/data/*.json datasets/; fi

# 5. Relocate pipeline and utility scripts to scripts/ directory
echo "Moving run and verify scripts into scripts/..."
# Move shell scripts
if [ -f run_pipeline.sh ]; then mv -v run_pipeline.sh scripts/; fi
if [ -f run_ma_notables.sh ]; then mv -v run_ma_notables.sh scripts/; fi
if [ -f verify_all.sh ]; then mv -v verify_all.sh scripts/; fi        # legacy verify script (will be archived)
if [ -f verify_all_C24_5.sh ]; then mv -v verify_all_C24_5.sh scripts/; fi  # legacy
if [ -f verify_all_C24_7.sh ]; then mv -v verify_all_C24_7.sh scripts/; fi  # legacy
if [ -f verify_all_C24_9.sh ]; then mv -v verify_all_C24_9.sh scripts/; fi
if [ -f verify_ma_notables.sh ]; then mv -v verify_ma_notables.sh scripts/; fi
# Move Python utility scripts
if [ -f preflight_ma_notables.py ]; then mv -v preflight_ma_notables.py scripts/; fi
if [ -f preflight_ma_notables.v2_3.py ]; then mv -v preflight_ma_notables.v2_3.py scripts/; fi
if [ -f apply_no_dates_quarantine.py ]; then mv -v apply_no_dates_quarantine.py scripts/; fi
if [ -f ma_notables_pipeline.py ]; then mv -v ma_notables_pipeline.py scripts/; fi  # if it exists outside src
if [ -f run.py ]; then mv -v run.py scripts/; fi
if [ -f parse_gedcom.py ]; then mv -v parse_gedcom.py scripts/; fi

# 6. Archive legacy and duplicate scripts, datasets, and docs
echo "Archiving legacy files..."
# Move deprecated scripts from scripts/ to archive/scripts/ (those we moved in step 5 that are outdated)
for f in verify_all.sh verify_all_C24_5.sh verify_all_C24_7.sh preflight_ma_notables.v2_3.py run.py parse_gedcom.py; do
    if [ -f scripts/$f ]; then mv -v "scripts/$f" archive/scripts/; fi
done
# Move any old dataset files (e.g., older versions or unused JSON) to archive/datasets
if [ -f datasets/collections.v2_3_roles.json ]; then mv -v datasets/collections.v2_3_roles.json archive/datasets/; fi
if [ -f datasets/tag_metadata.json ]; then mv -v datasets/tag_metadata.json archive/datasets/; fi
# Archive documentation (PDFs, markdowns) from docs/ if any
if [ -d docs ]; then
    mv -v docs/*.pdf archive/docs/ 2>/dev/null || true
    mv -v docs/*.md archive/docs/ 2>/dev/null || true
    mv -v docs/*.txt archive/docs/ 2>/dev/null || true
fi
# Archive inventory files, logs, and sample outputs if present
if [ -d inventories ]; then mv -v inventories archive/ 2>/dev/null || true; fi
if [ -d logs ]; then mv -v logs/* archive/logs/ 2>/dev/null || true; fi
if [ -f outpput.zip ]; then mv -v outpput.zip archive/outputs/; fi  # typo 'outpput.zip' handled if exists
if [ -f logs.zip ]; then mv -v logs.zip archive/logs/; fi

# 7. Cleanup empty directories (if any of these directories are now empty, remove them)
rmdir docs 2>/dev/null || true
rmdir src/gedcom_parser/postprocess 2>/dev/null || true
rmdir src/gedcom_parser/data 2>/dev/null || true
rmdir inventories 2>/dev/null || true

# 8. Update import references in code (postprocess -> enrichment, etc.) for compatibility
echo "Updating code references to new module paths..."
grep -RIl "gedcom_parser\.postprocess" . | xargs sed -i 's/gedcom_parser\.postprocess/gedcom_parser.enrichment/g'
# (If any references to moved data files or schemas exist, update those paths similarly)
# e.g., replace references to datasets/gedcom_tags.json if they were moved to schemas/
grep -RIl "datasets/gedcom_tags.json" src/gedcom_parser | xargs sed -i 's#datasets/gedcom_tags.json#schemas/gedcom_tags.json#g' || true

echo "Reorganization completed. Please review the 'archive/' folder for archived items."
