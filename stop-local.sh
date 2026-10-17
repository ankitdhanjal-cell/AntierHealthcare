#!/usr/bin/env bash
D=$HOME/.ahs-local
for f in api worker; do [ -f $D/$f.pid ] && kill $(cat $D/$f.pid) 2>/dev/null; done
fuser -k 8010/tcp 3010/tcp >/dev/null 2>&1
redis-cli -p 6389 shutdown nosave >/dev/null 2>&1
[ -f $D/pg/postmaster.pid ] && kill $(head -1 $D/pg/postmaster.pid) 2>/dev/null
echo stopped
