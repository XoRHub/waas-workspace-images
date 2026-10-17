# shellcheck shell=bash
# Supervise the Hermes web dashboard (sourced by waas-entrypoint: RUNDIR,
# log and strict mode come from it). Loopback only: reachable solely from
# inside the session, i.e. through the password-gated VNC display.
# --no-open: waas-hermes-kiosk is the session's browser; without it hermes
# spawns a second Firefox via webbrowser.open().
if [[ "${WAAS_HERMES_DASHBOARD:-1}" != "0" ]]; then
    cat > "${RUNDIR}/supervisor.d/60-hermes-dashboard.conf" <<EOF
[program:hermes-dashboard]
command=/usr/local/bin/hermes dashboard --no-open
priority=40
autorestart=true
environment=HOME="${HOME}"
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
redirect_stderr=true
EOF
    log "hermes dashboard enabled (127.0.0.1:9119; WAAS_HERMES_DASHBOARD=0 disables)"
else
    log "hermes dashboard disabled (WAAS_HERMES_DASHBOARD=0)"
fi
