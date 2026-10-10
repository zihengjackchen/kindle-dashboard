#!/bin/sh
# shellcheck disable=SC2153
DASHBOARD_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd) || exit 1
. "$DASHBOARD_DIR/lib/client.sh"
. "$DASHBOARD_DIR/lib/httpd.sh"
# The document shell integration returns Home when its child exits. Starting
# Mesquite before that transition lets appmgr cancel the new application's load.
# Detach first so both document and KUAL launchers can finish their lifecycle.
if [ "${1:-}" != '--after-launcher' ]; then
    check_enabled || exit 1
    nohup /bin/sh "$DASHBOARD_DIR/app-launch.sh" --after-launcher </dev/null >/dev/null 2>&1 &
    log 'Dashboard launch queued; waiting for launcher to return'
    exit 0
fi
sleep 3
launch_wait=0
while [ "$launch_wait" -lt 10 ]; do
    launch_app=$(probe lipc-get-prop com.lab126.appmgrd activeApp)
    case "$launch_app" in
        *shell_integration*|*kual*|*KUAL*) sleep 1; launch_wait=$((launch_wait + 1)) ;;
        *) break ;;
    esac
done
case "$launch_app" in *shell_integration*|*kual*|*KUAL*)
    log 'ERROR launcher did not return; Dashboard launch cancelled'
    exit 1 ;;
esac
# Keep failures visible after KUAL closes, and retain bounded startup stderr.
startup_exit() {
    startup_status=$?
    trap - 0
    if [ "$startup_status" -ne 0 ]; then
        log "Dashboard launch failed (exit $startup_status); see logs/startup.log and logs/httpd-probe.txt"
        sleep "$KUAL_SETTLE_SECONDS"
        display_notice 'Dashboard could not start' 'See extensions/dashboard/logs'
    fi
    exit "$startup_status"
}
trap startup_exit 0
if [ -f "$LOG_DIR/startup.log" ] && [ "$(wc -c < "$LOG_DIR/startup.log")" -ge "$MAX_LOG_BYTES" ]; then mv -f "$LOG_DIR/startup.log" "$LOG_DIR/startup.log.1"; fi
exec 2>> "$LOG_DIR/startup.log"
check_enabled || exit 1
# Detect capabilities before registering anything or changing light/power.
for app_command in sqlite3 lipc-get-prop lipc-set-prop mesquite curl cksum; do
    command -v "$app_command" >/dev/null 2>&1 || { fail "App requires $app_command; use KUAL Refresh as fallback"; exit 1; }
done
select_httpd || exit 1
if [ -f "$STATE_DIR/app.pid" ]; then
    pid=$(read_first "$STATE_DIR/app.pid")
    if is_uint "$pid" && [ -r "/proc/$pid/cmdline" ] && tr '\000' '\n' < "/proc/$pid/cmdline" | grep -F -x "$DASHBOARD_DIR/app-session.sh" >/dev/null; then
        lipc-set-prop com.lab126.appmgrd start app://org.kindledashboard.app
        exit $?
    fi
    fail 'Stale app session exists. Run Stop Dashboard, then reopen.'; exit 1
fi
stop_listener
display_opening
APP_ROOT=/var/local/mesquite/org.kindledashboard.app
mkdir -p "$APP_ROOT" || exit 1
# Mesquite runs as framework, while launchers run as root with umask 077.
# Only native UI assets are shared; NAS credentials stay in the shell client.
native_uid=$(id -u framework) && native_gid=$(id -g framework) || exit 1
chown "$native_uid:$native_gid" "$APP_ROOT" || exit 1
chmod 0755 "$APP_ROOT" || exit 1
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
# Mesquite on 5.16.2.1.1 resolves script assets from the native app directory,
# even with an HTTP content URL. Keep the per-launch settings alongside app.js.
cp "$STATE_DIR/web/$SESSION_KEY/session.js" "$APP_ROOT/session.js" || exit 1
# Same-origin local HTTP avoids old WebKit file:// CORS restrictions.
sed "s|src=\"index.html\"|src=\"http://127.0.0.1:$APP_PORT/$SESSION_KEY/index.html\"|" "$DASHBOARD_DIR/app/config.xml" > "$APP_ROOT/config.xml"
chmod 0644 "$APP_ROOT/config.xml" "$APP_ROOT/index.html" "$APP_ROOT/app.js" "$APP_ROOT/session.js" || exit 1
cp "$DASHBOARD_DIR/app/bridge.cgi" "$STATE_DIR/web/cgi-bin/action"
chmod 700 "$STATE_DIR/web/cgi-bin/action"
export DASHBOARD_DIR
nohup /bin/sh "$DASHBOARD_DIR/app-session.sh" "$SESSION_KEY" >/dev/null 2>> "$LOG_DIR/startup.log" &
sleep 1
[ -f "$STATE_DIR/app.pid" ] || { fail 'App bridge failed to start'; exit 1; }
if ! curl -q -fsS --max-time 5 -X POST --header "X-Dashboard-Session: $SESSION_KEY" "http://127.0.0.1:$APP_PORT/cgi-bin/action?heartbeat" | grep -q '"ok":true'; then
    /bin/sh "$DASHBOARD_DIR/stop.sh"
    fail 'Local bridge CGI/header support failed its self-check'
    exit 1
fi
lipc-set-prop com.lab126.appmgrd start app://org.kindledashboard.app || { /bin/sh "$DASHBOARD_DIR/stop.sh"; exit 1; }
log 'Native launch request accepted; waiting for Dashboard UI connection'
