-- Deterministic playground seed: answers in docs/evals/evaluation-postgres.json depend on this data.
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS articles;

CREATE TABLE users (
    id serial PRIMARY KEY,
    name text NOT NULL,
    email text UNIQUE,
    phone text
);

CREATE TABLE orders (
    id serial PRIMARY KEY,
    user_id int REFERENCES users(id),
    total numeric(10, 2) NOT NULL,
    created_at timestamptz DEFAULT now()
);

INSERT INTO users (name, email, phone)
SELECT 'user_' || i, 'user_' || i || '@example.com', '+5511' || lpad(i::text, 5, '0')
FROM generate_series(1, 500) i;

INSERT INTO orders (user_id, total)
SELECT ((i - 1) % 500) + 1, ((i * 37) % 20000) / 100.0
FROM generate_series(1, 5000) i;

CREATE INDEX idx_orders_user ON orders (user_id);

CREATE TABLE articles (
    id int PRIMARY KEY,
    title text NOT NULL,
    body text NOT NULL,
    embedding vector(3)
);

INSERT INTO articles (id, title, body, embedding) VALUES
    (1, 'alpha', 'postgres full text search', '[1,0,0]'),
    (2, 'beta', 'mysql fulltext index', '[0,1,0]'),
    (3, 'gamma', 'mongodb atlas vector search', '[0,0,1]');

CREATE INDEX articles_embedding_hnsw ON articles USING hnsw (embedding vector_cosine_ops);
CREATE INDEX articles_body_fts ON articles USING gin (to_tsvector('simple', body));

ANALYZE users;
ANALYZE orders;
ANALYZE articles;
