// ==============================================================================
// Script d'initialisation du Sharding MongoDB & Répartition Multi-Tenant (Partie II)
// Exécuté sur le routeur mongos (luke_mongos)
// ==============================================================================

console.log("--> [1/5] Déclaration et rattachement des Shards (Replica Sets)...");

try {
    const res1 = sh.addShard("rs-shard1/shard1a:27017,shard1b:27017,shard1c:27017");
    console.log("✓ Shard 1 (rs-shard1) rattaché :", JSON.stringify(res1));
} catch (e) {
    console.log("ℹ Shard 1 déjà configuré ou note :", e.message);
}

try {
    const res2 = sh.addShard("rs-shard2/shard2a:27017,shard2b:27017,shard2c:27017");
    console.log("✓ Shard 2 (rs-shard2) rattaché :", JSON.stringify(res2));
} catch (e) {
    console.log("ℹ Shard 2 déjà configuré ou note :", e.message);
}

console.log("--> [2/5] Activation du sharding sur la base luke_db...");
try {
    const resDb = sh.enableSharding("luke_db");
    console.log("✓ Sharding activé sur 'luke_db' :", JSON.stringify(resDb));
} catch (e) {
    console.log("ℹ Sharding déjà activé sur 'luke_db' ou note :", e.message);
}

const dbLuke = db.getSiblingDB("luke_db");

console.log("--> [3/5] Création des index de Sharding sur les collections...");
dbLuke.companies.createIndex({ "_id": "hashed" });
dbLuke.users.createIndex({ "company_id": 1, "email": 1 }, { unique: true });
dbLuke.projects.createIndex({ "company_id": 1, "_id": 1 });
dbLuke.tasks.createIndex({ "company_id": 1, "_id": 1 });
console.log("✓ Index créés.");

console.log("--> [4/5] Sharding des collections...");
// companies: Hashed sharding pour équilibrer aléatoirement les organisations sur tous les shards
try {
    sh.shardCollection("luke_db.companies", { "_id": "hashed" });
    console.log("✓ Collection companies shardée ({ _id: 'hashed' }).");
} catch (e) { console.log("ℹ companies :", e.message); }

// users: Ranged Shard Key { company_id: 1, email: 1 } (préfixe conforme à l'index unique)
try {
    sh.shardCollection("luke_db.users", { "company_id": 1, "email": 1 }, true);
    console.log("✓ Collection users shardée ({ company_id: 1, email: 1 }, unique: true).");
} catch (e) { console.log("ℹ users :", e.message); }

// projects: Ranged Shard Key composée { company_id: 1, _id: 1 }
try {
    sh.shardCollection("luke_db.projects", { "company_id": 1, "_id": 1 });
    console.log("✓ Collection projects shardée ({ company_id: 1, _id: 1 }).");
} catch (e) { console.log("ℹ projects :", e.message); }

// tasks: Ranged Shard Key composée { company_id: 1, _id: 1 }
try {
    sh.shardCollection("luke_db.tasks", { "company_id": 1, "_id": 1 });
    console.log("✓ Collection tasks shardée ({ company_id: 1, _id: 1 }).");
} catch (e) { console.log("ℹ tasks :", e.message); }

console.log("--> [5/5] Configuration des Zones Multi-Tenant (Zone Sharding & Pre-splitting)...");
// Déclaration des Zones sur les shards
try {
    sh.addShardToZone("rs-shard1", "ZONE_AGENCE_WEB");
    console.log("✓ Zone ZONE_AGENCE_WEB associée à rs-shard1.");
} catch (e) { console.log("ℹ Zone 1 :", e.message); }

try {
    sh.addShardToZone("rs-shard2", "ZONE_TECHNOVA");
    console.log("✓ Zone ZONE_TECHNOVA associée à rs-shard2.");
} catch (e) { console.log("ℹ Zone 2 :", e.message); }

// IDs des deux entreprises de démonstration
const cid1 = ObjectId("652a1b2c3d4e5f6a7b8c9d01"); // Agence Web Créative
const cid2 = ObjectId("652a1b2c3d4e5f6a7b8c9d02"); // TechNova Solutions

// Rattachement des plages de clés aux zones
try {
    sh.updateZoneKeyRange("luke_db.tasks", { "company_id": cid1, "_id": MinKey }, { "company_id": cid1, "_id": MaxKey }, "ZONE_AGENCE_WEB");
    sh.updateZoneKeyRange("luke_db.tasks", { "company_id": cid2, "_id": MinKey }, { "company_id": cid2, "_id": MaxKey }, "ZONE_TECHNOVA");

    sh.updateZoneKeyRange("luke_db.projects", { "company_id": cid1, "_id": MinKey }, { "company_id": cid1, "_id": MaxKey }, "ZONE_AGENCE_WEB");
    sh.updateZoneKeyRange("luke_db.projects", { "company_id": cid2, "_id": MinKey }, { "company_id": cid2, "_id": MaxKey }, "ZONE_TECHNOVA");

    sh.updateZoneKeyRange("luke_db.users", { "company_id": cid1, "email": MinKey }, { "company_id": cid1, "email": MaxKey }, "ZONE_AGENCE_WEB");
    sh.updateZoneKeyRange("luke_db.users", { "company_id": cid2, "email": MinKey }, { "company_id": cid2, "email": MaxKey }, "ZONE_TECHNOVA");
    console.log("✓ Plages de clés associées aux Zones avec succès.");
} catch (e) { console.log("ℹ KeyRange :", e.message); }

// Pre-splitting immédiat et routage des chunks pour que la répartition soit visible immédiatement
try {
    sh.splitAt("luke_db.tasks", { "company_id": cid2, "_id": MinKey });
    sh.moveChunk("luke_db.tasks", { "company_id": cid2, "_id": MinKey }, "rs-shard2");

    sh.splitAt("luke_db.projects", { "company_id": cid2, "_id": MinKey });
    sh.moveChunk("luke_db.projects", { "company_id": cid2, "_id": MinKey }, "rs-shard2");

    sh.splitAt("luke_db.users", { "company_id": cid2, "email": MinKey });
    sh.moveChunk("luke_db.users", { "company_id": cid2, "email": MinKey }, "rs-shard2");
    console.log("✓ Pre-splitting et MoveChunk exécutés (TechNova routé vers rs-shard2).");
} catch (e) { console.log("ℹ Split/Move :", e.message); }

console.log("==============================================================================");
console.log("✓ INITIALISATION DU CLUSTER DISTRIBUÉ TERMINÉE AVEC SUCCÈS !");
console.log("==============================================================================");
