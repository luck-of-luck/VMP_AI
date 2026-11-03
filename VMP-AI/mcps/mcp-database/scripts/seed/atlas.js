// Deterministic seed for the atlas-local playground (make atlas-local && make atlas-seed).
// Creates a tiny collection with 3-dimensional embeddings plus one text and one vector search index,
// so db_read_text_search / db_read_vector_search can be exercised manually against real mongot.
db = db.getSiblingDB("app");
db.articles.drop();
db.articles.insertMany([
  { _id: 1, title: "alpha", body: "postgres full text search", embedding: [1, 0, 0] },
  { _id: 2, title: "beta", body: "mysql fulltext index", embedding: [0, 1, 0] },
  { _id: 3, title: "gamma", body: "mongodb atlas vector search", embedding: [0, 0, 1] },
]);
db.articles.createSearchIndex("default", { mappings: { dynamic: true } });
db.articles.createSearchIndex("articles_vec", "vectorSearch", {
  fields: [{ type: "vector", path: "embedding", numDimensions: 3, similarity: "cosine" }],
});
print("seeded app.articles with search indexes: default (text), articles_vec (vector)");
