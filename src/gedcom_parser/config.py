import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DEFAULTS = {
    "canonical_tag_dict": os.path.join(BASE_DIR, "../../datasets/gedcom/canonical/canonical_tag_dictionary_gedcom551.patched.json"),
    "grammar_placements": os.path.join(BASE_DIR, "../../datasets/gedcom/canonical/canonical_grammar_placements_gedcom551.backbone.plus_seeds.plus_ancestry_ext.json"),
    "raw_lines_dir": os.path.join(BASE_DIR, "../../outputs/raw_capture/run3_ctx"),
    "output_dir": os.path.join(BASE_DIR, "../../outputs/parsed"),
}
