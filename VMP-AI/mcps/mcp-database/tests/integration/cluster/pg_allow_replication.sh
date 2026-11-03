#!/bin/sh
# initdb hook: let any host stream WAL (test topology only; the network is container-private).
echo "host replication all all trust" >> "$PGDATA/pg_hba.conf"
