#!/bin/sh
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
/bin/sh "$DASHBOARD_DIR/stop.sh" || exit 1
sqlite3 /var/local/appreg.db <<'SQL' || exit 1
.timeout 3000
BEGIN IMMEDIATE;
DELETE FROM properties WHERE handlerId='org.kindledashboard.app';
DELETE FROM handlerIds WHERE handlerId='org.kindledashboard.app';
COMMIT;
SQL
for file in index.html app.js config.xml session.js; do rm -f "/var/local/mesquite/org.kindledashboard.app/$file"; done
rmdir /var/local/mesquite/org.kindledashboard.app 2>/dev/null || :
printf 'Dashboard app registration removed. You can delete documents/Dashboard.sh.\n'
