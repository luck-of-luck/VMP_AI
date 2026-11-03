// Deterministic playground seed: answers in docs/evals/evaluation.xml depend on this data.
db = db.getSiblingDB("app");

db.events.drop();
db.profiles.drop();

const events = [];
for (let i = 0; i < 1000; i++) {
  let page;
  if (i < 300) page = "/home";
  else if (i < 500) page = "/pricing";
  else page = "/p" + (Math.floor((i - 500) / 100) + 1); // /p1../p5, 100 each
  events.push({
    page: page,
    type: "click",
    user: "u" + (i % 50),
    email: "u" + (i % 50) + "@example.com",
    seq: i,
  });
}
db.events.insertMany(events);
db.events.createIndex({ page: 1 });

db.profiles.insertMany([
  { name: "Ana", email: "ana@example.com", plan: "pro" },
  { name: "Bob", email: "bob@example.com", plan: "free" },
  { name: "Caio", email: "caio@example.com", plan: "pro" },
]);
db.profiles.createIndex({ email: 1 }, { unique: true });

print("seeded: events=" + db.events.countDocuments() + " profiles=" + db.profiles.countDocuments());
