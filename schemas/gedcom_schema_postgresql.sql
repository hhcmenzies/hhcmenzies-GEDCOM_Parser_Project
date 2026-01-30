-- Enable extensions for text search (if not already enabled)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- 1. Provenance table
CREATE TABLE gedcom_imports (
    import_id        SERIAL PRIMARY KEY,
    filename        TEXT NOT NULL,
    import_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    file_hash       TEXT
);

-- 2. Header table
CREATE TABLE gedcom_headers (
    import_id       INTEGER PRIMARY KEY REFERENCES gedcom_imports(import_id),
    gedcom_version  TEXT,
    source_system   TEXT,
    destination     TEXT,
    character_set   TEXT,
    submitter_name  TEXT,
    submission_date DATE,
    submission_time TIME,
    copyright       TEXT
    -- (One header per import; import_id serves as primary key here)
);

-- 3. Raw GEDCOM lines table
CREATE TABLE gedcom_lines (
    line_id     SERIAL PRIMARY KEY,
    import_id   INTEGER NOT NULL REFERENCES gedcom_imports(import_id) ON DELETE CASCADE,
    line_num    INT NOT NULL,
    level       INT NOT NULL,
    xref_id     TEXT,
    tag         TEXT NOT NULL,
    value       TEXT,
    pointer     TEXT,
    parent_line_id INTEGER REFERENCES gedcom_lines(line_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX ux_lines_import_line ON gedcom_lines(import_id, line_num);
CREATE INDEX idx_lines_tag ON gedcom_lines(tag);
CREATE INDEX idx_lines_pointer ON gedcom_lines(import_id, pointer);

-- 4. Individuals table
CREATE TYPE sex_enum AS ENUM ('M','F','U');
CREATE TYPE date_qualifier_enum AS ENUM ('ABT','BEF','AFT','BET','CAL','EST');
CREATE TABLE individuals (
    indiv_id    SERIAL PRIMARY KEY,
    import_id   INTEGER NOT NULL REFERENCES gedcom_imports(import_id) ON DELETE CASCADE,
    xref_id     TEXT NOT NULL,
    name_full   TEXT NOT NULL,
    name_given  TEXT,
    name_surname TEXT,
    sex         sex_enum NOT NULL DEFAULT 'U',
    birth_date  DATE,
    birth_date_qual date_qualifier_enum,
    birth_place_id  INTEGER REFERENCES places(place_id) ON DELETE SET NULL,
    death_date  DATE,
    death_date_qual date_qualifier_enum,
    death_place_id  INTEGER REFERENCES places(place_id) ON DELETE SET NULL,
    occupation  TEXT
    -- ... additional name parts and fields as needed ...
);
ALTER TABLE individuals ADD CONSTRAINT ux_individual_unique_xref UNIQUE(import_id, xref_id);

-- 5. Families table
CREATE TABLE families (
    fam_id      SERIAL PRIMARY KEY,
    import_id   INTEGER NOT NULL REFERENCES gedcom_imports(import_id) ON DELETE CASCADE,
    xref_id     TEXT NOT NULL,
    husband_id  INTEGER REFERENCES individuals(indiv_id) ON DELETE SET NULL,
    wife_id     INTEGER REFERENCES individuals(indiv_id) ON DELETE SET NULL,
    marriage_date DATE,
    marriage_date_qual date_qualifier_enum,
    marriage_place_id INTEGER REFERENCES places(place_id) ON DELETE SET NULL,
    divorce_date   DATE,
    divorce_date_qual date_qualifier_enum,
    divorce_place_id INTEGER REFERENCES places(place_id) ON DELETE SET NULL
);
ALTER TABLE families ADD CONSTRAINT ux_family_unique_xref UNIQUE(import_id, xref_id);

CREATE TABLE family_children (
    family_id INTEGER NOT NULL REFERENCES families(fam_id) ON DELETE CASCADE,
    child_id  INTEGER NOT NULL REFERENCES individuals(indiv_id) ON DELETE CASCADE,
    PRIMARY KEY (family_id, child_id)
);

-- 6. Events table
CREATE TABLE events (
    event_id    SERIAL PRIMARY KEY,
    import_id   INTEGER NOT NULL REFERENCES gedcom_imports(import_id) ON DELETE CASCADE,
    event_tag   TEXT NOT NULL,
    event_date  DATE,
    event_date_qual date_qualifier_enum,
    event_place_id INTEGER REFERENCES places(place_id) ON DELETE SET NULL,
    value       TEXT,
    individual_id INTEGER REFERENCES individuals(indiv_id) ON DELETE CASCADE,
    family_id   INTEGER REFERENCES families(fam_id) ON DELETE CASCADE,
    CHECK (individual_id IS NOT NULL OR family_id IS NOT NULL)
);

-- 7. Places table
CREATE TABLE places (
    place_id    SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    latitude    REAL,
    longitude   REAL,
    country     TEXT,
    state       TEXT,
    city        TEXT
    -- plus optional standardized_name or components as needed
);
CREATE INDEX idx_places_name ON places USING gin (unaccent(lower(name)) gin_trgm_ops);

-- 8. Repositories, Sources, Citations
CREATE TABLE repositories (
    repo_id     SERIAL PRIMARY KEY,
    import_id   INTEGER NOT NULL REFERENCES gedcom_imports(import_id) ON DELETE CASCADE,
    xref_id     TEXT NOT NULL,
    name        TEXT,
    address_id  INTEGER REFERENCES addresses(address_id) ON DELETE SET NULL,
    UNIQUE(import_id, xref_id)
);
CREATE TABLE sources (
    source_id   SERIAL PRIMARY KEY,
    import_id   INTEGER NOT NULL REFERENCES gedcom_imports(import_id) ON DELETE CASCADE,
    xref_id     TEXT NOT NULL,
    title       TEXT,
    author      TEXT,
    publication TEXT,
    repository_id INTEGER REFERENCES repositories(repo_id) ON DELETE SET NULL,
    call_number TEXT,
    UNIQUE(import_id, xref_id)
);
CREATE TABLE citations (
    citation_id SERIAL PRIMARY KEY,
    import_id   INTEGER NOT NULL REFERENCES gedcom_imports(import_id) ON DELETE CASCADE,
    source_id   INTEGER NOT NULL REFERENCES sources(source_id) ON DELETE CASCADE,
    refers_to_type TEXT NOT NULL,
    refers_to_id   INTEGER NOT NULL,
    detail      TEXT
    -- (enforce refers_to integrity via application or triggers)
);

-- 9. Notes and Multimedia
CREATE TABLE notes (
    note_id     SERIAL PRIMARY KEY,
    import_id   INTEGER NOT NULL REFERENCES gedcom_imports(import_id) ON DELETE CASCADE,
    xref_id     TEXT,
    note_text   TEXT,
    UNIQUE(import_id, xref_id)
);
CREATE TABLE multimedia (
    media_id    SERIAL PRIMARY KEY,
    import_id   INTEGER NOT NULL REFERENCES gedcom_imports(import_id) ON DELETE CASCADE,
    xref_id     TEXT,
    file_path   TEXT,
    title       TEXT,
    format      TEXT,
    UNIQUE(import_id, xref_id)
);
-- (Link tables for notes->entities and media->entities would be defined similarly to citations if needed)

-- 10. Custom Tags
CREATE TABLE custom_tags (
    custom_tag_id SERIAL PRIMARY KEY,
    import_id   INTEGER NOT NULL REFERENCES gedcom_imports(import_id) ON DELETE CASCADE,
    owner_type  TEXT NOT NULL,
    owner_xref  TEXT NOT NULL,
    tag         TEXT NOT NULL,
    value       TEXT
);
-- Index to quickly find custom tags by type or tag name
CREATE INDEX idx_customtags_owner ON custom_tags(import_id, owner_type, owner_xref);

-- 11. Tag Definitions (for classification)
CREATE TABLE gedcom_tag_definitions (
    tag         TEXT PRIMARY KEY,
    in_5_5_1    BOOLEAN,
    in_5_5_5    BOOLEAN,
    in_7        BOOLEAN,
    description TEXT
);
-- (This table will be pre-populated with standard tag info; any tag not here is considered custom)
