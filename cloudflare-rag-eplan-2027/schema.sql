-- eplan-wiki-2027: full-text index over the scraped+bundled EPLAN 2027 API wiki
-- (see D:\3_workbench\Christian\covaga\scrapping_eplan\eplan_wiki_scraper.py)

DROP TABLE IF EXISTS docs_fts;
DROP TABLE IF EXISTS docs;

CREATE TABLE docs (
  path       TEXT PRIMARY KEY,   -- relative path within the wiki, e.g. "API Reference/.../Action.md"
  title      TEXT NOT NULL,
  kind       TEXT NOT NULL,      -- 'bundle' | 'standalone' | 'index'
  breadcrumb TEXT,               -- "Eplan API > API Reference > ... > Action"
  source_url TEXT,
  content    TEXT NOT NULL,
  size       INTEGER NOT NULL
);

-- content='docs' + content_rowid='rowid': FTS5 stores only the token index,
-- not a second copy of the text -- docs.content stays the single source of
-- truth, keeping the DB roughly one copy of the corpus instead of two.
CREATE VIRTUAL TABLE docs_fts USING fts5(
  title,
  breadcrumb,
  content,
  content='docs',
  content_rowid='rowid',
  tokenize='porter unicode61'
);

-- External-content FTS5 tables don't auto-sync -- these triggers do it, so
-- the ingestion script only ever has to INSERT INTO docs.
CREATE TRIGGER docs_ai AFTER INSERT ON docs BEGIN
  INSERT INTO docs_fts(rowid, title, breadcrumb, content) VALUES (new.rowid, new.title, new.breadcrumb, new.content);
END;
CREATE TRIGGER docs_ad AFTER DELETE ON docs BEGIN
  INSERT INTO docs_fts(docs_fts, rowid, title, breadcrumb, content) VALUES ('delete', old.rowid, old.title, old.breadcrumb, old.content);
END;
CREATE TRIGGER docs_au AFTER UPDATE ON docs BEGIN
  INSERT INTO docs_fts(docs_fts, rowid, title, breadcrumb, content) VALUES ('delete', old.rowid, old.title, old.breadcrumb, old.content);
  INSERT INTO docs_fts(rowid, title, breadcrumb, content) VALUES (new.rowid, new.title, new.breadcrumb, new.content);
END;
