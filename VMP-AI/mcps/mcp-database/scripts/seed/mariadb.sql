-- Deterministic playground seed: answers in docs/evals/evaluation-mariadb.json depend on this data.
CREATE DATABASE IF NOT EXISTS app;
USE app;

DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS articles;

CREATE TABLE customers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(200) UNIQUE
);

CREATE TABLE products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    price DECIMAL(10, 2) NOT NULL
);

INSERT INTO customers (name, email)
WITH RECURSIVE seq AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM seq WHERE n < 100)
SELECT CONCAT('customer_', n), CONCAT('customer_', n, '@example.com') FROM seq;

INSERT INTO products (name, price)
WITH RECURSIVE seq AS (SELECT 1 AS n UNION ALL SELECT n + 1 FROM seq WHERE n < 50)
SELECT CONCAT('product_', n), n * 20.00 FROM seq;

INSERT INTO products (name, price) VALUES ('golden-widget', 999.99);

CREATE TABLE articles (
    id INT PRIMARY KEY,
    title VARCHAR(50) NOT NULL,
    body TEXT NOT NULL,
    FULLTEXT KEY articles_body_ft (body)
);

INSERT INTO articles (id, title, body) VALUES
    (1, 'alpha', 'postgres full text search'),
    (2, 'beta', 'mysql fulltext index'),
    (3, 'gamma', 'mongodb atlas vector search');

ANALYZE TABLE customers, products, articles;
