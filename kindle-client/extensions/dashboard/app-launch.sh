#!/bin/sh
# shellcheck disable=SC2153
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
. "$DASHBOARD_DIR/lib/client.sh"
check_enabled || exit 1
# Detect capabilities before registering anything or changing light/power.
for app_command in sqlite3 lipc-get-prop lipc-set-prop mesquite curl cksum; do
    command -v "$app_command" >/dev/null 2>&1 || { fail "App requires $app_command; use KUAL Refresh as fallback"; exit 1; }
done
"$BUSYBOX_BIN" httpd --help 2>&1 | grep -q -- '-p' || { fail 'App requires BusyBox httpd with CGI support; see docs/kindle-app.md'; exit 1; }
if [ -f "$STATE_DIR/app.pid" ]; then
    pid=$(read_first "$STATE_DIR/app.pid")
    if is_uint "$pid" && [ -r "/proc/$pid/cmdline" ] && tr '\000' '\n' < "/proc/$pid/cmdline" | grep -F -x "$DASHBOARD_DIR/app-session.sh" >/dev/null; then
        lipc-set-prop com.lab126.appmgrd start app://org.kindledashboard.app
        exit $?
    fi
    fail 'Stale app session exists. Run Stop Dashboard, then reopen.'; exit 1
fi
stop_listener
APP_ROOT=/var/local/mesquite/org.kindledashboard.app
mkdir -p "$APP_ROOT" || exit 1
cp "$DASHBOARD_DIR/app/index.html" "$DASHBOARD_DIR/app/app.js" "$DASHBOARD_DIR/app/config.xml" "$APP_ROOT/" || exit 1
# Registration is scoped to this application. No framework/lockscreen patches.
sqlite3 /var/local/appreg.db <<'SQL' || exit 1
.timeout 3000
BEGIN IMMEDIATE;
INSERT OR IGNORE INTO interfaces(interface) VALUES('application');
INSERT OR IGNORE INTO handlerIds(handlerId) VALUES('org.kindledashboard.app');
INSERT OR REPLACE INTO properties(handlerId,name,value) VALUES('org.kindledashboard.app','lipcId','org.kindledashboard.app');
INSERT OR REPLACE INTO properties(handlerId,name,value) VALUES('org.kindledashboard.app','command','/usr/bin/mesquite -l org.kindledashboard.app -c file:///var/local/mesquite/org.kindledashboard.app/');
INSERT OR REPLACE INTO properties(handlerId,name,value) VALUES('org.kindledashboard.app','supportedOrientation','U');
COMMIT;
SQL
umask 077
SESSION_KEY=$(od -An -N24 -tx1 /dev/urandom | tr -d ' \n')
[ "${#SESSION_KEY}" = 48 ] || exit 1
printf '%s\n' "$SESSION_KEY" > "$STATE_DIR/app-key"
mkdir -p "$STATE_DIR/web/cgi-bin" || exit 1
mkdir -p "$STATE_DIR/web/$SESSION_KEY" || exit 1
cp "$DASHBOARD_DIR/app/index.html" "$DASHBOARD_DIR/app/app.js" "$STATE_DIR/web/$SESSION_KEY/" || exit 1
printf 'window.DASHBOARD={base:"http://127.0.0.1:%s",key:"%s"};\n' "$APP_PORT" "$SESSION_KEY" > "$STATE_DIR/web/$SESSION_KEY/session.js"
# Same-origin local HTTP avoids old WebKit file:// CORS restrictions.
sed "s|src=\"index.html\"|src=\"http://127.0.0.1:$APP_PORT/$SESSION_KEY/index.html\"|" "$DASHBOARD_DIR/app/config.xml" > "$APP_ROOT/config.xml"
cp "$DASHBOARD_DIR/app/bridge.cgi" "$STATE_DIR/web/cgi-bin/action"
chmod 700 "$STATE_DIR/web/cgi-bin/action"
export DASHBOARD_DIR
nohup /bin/sh "$DASHBOARD_DIR/app-session.sh" "$SESSION_KEY" >/dev/null 2>&1 &
sleep 1
[ -f "$STATE_DIR/app.pid" ] || { fail 'App bridge failed to start'; exit 1; }
if ! curl -q -fsS --max-time 5 -X POST --header "X-Dashboard-Session: $SESSION_KEY" "http://127.0.0.1:$APP_PORT/cgi-bin/action?heartbeat" | grep -q '"ok":true'; then
    /bin/sh "$DASHBOARD_DIR/stop.sh"
    fail 'Local bridge CGI/header support failed its self-check'
    exit 1
fi
lipc-set-prop com.lab126.appmgrd start app://org.kindledashboard.app || { /bin/sh "$DASHBOARD_DIR/stop.sh"; exit 1; }
log 'Launched Dashboard library app'
