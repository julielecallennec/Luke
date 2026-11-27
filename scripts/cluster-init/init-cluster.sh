#!/bin/bash
set -e

echo "=============================================================================="
echo "      LUKE SAAS - ORCHESTRATION ET INITIALISATION AUTOMATISÉE PARTIE II      "
echo "=============================================================================="

wait_for_mongo() {
    local host=$1
    local port=$2
    local label=$3
    echo -n "En attente du nœud $label ($host:$port)... "
    until mongosh --host "$host" --port "$port" --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; do
        sleep 2
        echo -n "."
    done
    echo " [EN LIGNE]"
}

# 1. Attente de la disponibilité de tous les nœuds de données
echo "--- [1/6] Vérification réseau des conteneurs MongoDB ---"
wait_for_mongo configsvr1 27017 "Config Server 1"
wait_for_mongo configsvr2 27017 "Config Server 2"
wait_for_mongo configsvr3 27017 "Config Server 3"

wait_for_mongo shard1a 27017 "Shard 1 - Node A"
wait_for_mongo shard1b 27017 "Shard 1 - Node B"
wait_for_mongo shard1c 27017 "Shard 1 - Node C"

wait_for_mongo shard2a 27017 "Shard 2 - Node A"
wait_for_mongo shard2b 27017 "Shard 2 - Node B"
wait_for_mongo shard2c 27017 "Shard 2 - Node C"

# 2. Initialisation du Replica Set Config Server
echo "--- [2/6] Initialisation du Replica Set Config Server (rs-config) ---"
mongosh --host configsvr1 --port 27017 --eval '
try {
    const status = rs.status();
    console.log("rs-config déjà initialisé.");
} catch(e) {
    const res = rs.initiate({
        _id: "rs-config",
        configsvr: true,
        members: [
            { _id: 0, host: "configsvr1:27017", priority: 2 },
            { _id: 1, host: "configsvr2:27017", priority: 1 },
            { _id: 2, host: "configsvr3:27017", priority: 1 }
        ]
    });
    console.log("rs-config initialisé :", JSON.stringify(res));
}
'

# 3. Initialisation du Replica Set Shard 1
echo "--- [3/6] Initialisation du Replica Set Shard 1 (rs-shard1) ---"
mongosh --host shard1a --port 27017 --eval '
try {
    const status = rs.status();
    console.log("rs-shard1 déjà initialisé.");
} catch(e) {
    const res = rs.initiate({
        _id: "rs-shard1",
        members: [
            { _id: 0, host: "shard1a:27017", priority: 2 },
            { _id: 1, host: "shard1b:27017", priority: 1 },
            { _id: 2, host: "shard1c:27017", priority: 1 }
        ]
    });
    console.log("rs-shard1 initialisé :", JSON.stringify(res));
}
'

# 4. Initialisation du Replica Set Shard 2
echo "--- [4/6] Initialisation du Replica Set Shard 2 (rs-shard2) ---"
mongosh --host shard2a --port 27017 --eval '
try {
    const status = rs.status();
    console.log("rs-shard2 déjà initialisé.");
} catch(e) {
    const res = rs.initiate({
        _id: "rs-shard2",
        members: [
            { _id: 0, host: "shard2a:27017", priority: 2 },
            { _id: 1, host: "shard2b:27017", priority: 1 },
            { _id: 2, host: "shard2c:27017", priority: 1 }
        ]
    });
    console.log("rs-shard2 initialisé :", JSON.stringify(res));
}
'

# 5. Attente de la transition en Primary sur les Replica Sets
echo "--- [5/6] Stabilisation des élections des Replica Sets ---"
sleep 5

# 6. Attente et configuration de mongos
echo "--- [6/6] Configuration du Sharding et du routeur mongos ---"
wait_for_mongo mongos 27017 "Routeur mongos"

# Exécuter le script de configuration du sharding sur mongos
mongosh --host mongos --port 27017 /scripts/setup-sharding.js

echo "=============================================================================="
echo "✓ TOUTES LES COMPOSANTES DU CLUSTER DISTRIBUÉ SONT PRÊTES ET OPÉRATIONNELLES"
echo "=============================================================================="
exit 0
