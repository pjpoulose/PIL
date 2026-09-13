-- PIL (Personal Instagram Library) database schema.
-- Created automatically on first run; safe to apply to an existing DB (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS folders(
    collection_id TEXT PRIMARY KEY,
    name TEXT,
    item_count INT
);

CREATE TABLE IF NOT EXISTS posts(
    post_id TEXT PRIMARY KEY,
    media_fbid TEXT,
    url TEXT,
    author TEXT,
    media_type TEXT,
    caption TEXT,
    saved_at TEXT,
    indexed_at TEXT
);

CREATE TABLE IF NOT EXISTS post_folders(
    post_id TEXT,
    collection_id TEXT,
    PRIMARY KEY(post_id, collection_id)
);

CREATE TABLE IF NOT EXISTS knowledge(
    post_id TEXT PRIMARY KEY,
    summary TEXT,
    key_points TEXT,   -- JSON array of strings
    howto TEXT,
    links TEXT         -- JSON array of URL strings
);

CREATE TABLE IF NOT EXISTS tags(
    post_id TEXT,
    tag TEXT
);

CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
CREATE INDEX IF NOT EXISTS idx_postfolders_cid ON post_folders(collection_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_unique ON tags(post_id, tag);
