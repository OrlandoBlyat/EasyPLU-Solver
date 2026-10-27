# Sourced by prodstart.bash with repository root as the working directory.
https_args=()
if [[ "${configure_https:-false}" == true ]]; then
  https_args+=(--configure)
fi
"$python_bin" scripts/setup-https.py "${https_args[@]}" --frontend-port "$frontend_port"
IFS=$'\t' read -r https_mode https_host https_port < <("$python_bin" scripts/setup-https.py --print --frontend-port "$frontend_port")

if [[ "$https_mode" != none ]]; then
  if ! command -v caddy >/dev/null; then
    if [[ ! -t 0 ]]; then
      echo "Caddy is required. Install it before production startup." >&2; exit 1
    fi
    read -r -p "Install Caddy using the system package manager (sudo)? [y/N] " caddy_answer
    case "$caddy_answer" in
      y|Y|yes|YES)
        if command -v dnf >/dev/null; then sudo dnf install -y caddy
        elif command -v apt-get >/dev/null; then sudo apt-get update; sudo apt-get install -y caddy
        else echo "Install Caddy from https://caddyserver.com/docs/install" >&2; exit 1
        fi ;;
      *) echo "Caddy installation skipped. Startup cancelled." >&2; exit 1 ;;
    esac
  fi
  # Keep CA keys and renewal state private and persistent across restarts.
  umask 077
  export XDG_DATA_HOME="$PWD/var/caddy-data"
  export XDG_CONFIG_HOME="$PWD/var/caddy-config"
  mkdir -p "$XDG_DATA_HOME" "$XDG_CONFIG_HOME"
  chmod 700 "$XDG_DATA_HOME" "$XDG_CONFIG_HOME"
  if [[ "$https_mode" == letsencrypt || "$https_port" -lt 1024 ]]; then
    bind_unprivileged=false
    if [[ -r /proc/sys/net/ipv4/ip_unprivileged_port_start ]]; then
      read -r first_unprivileged_port < /proc/sys/net/ipv4/ip_unprivileged_port_start
      if [[ "$first_unprivileged_port" -le 80 ]]; then bind_unprivileged=true; fi
    fi
    caddy_binary="$(command -v caddy)"
    if [[ "$EUID" -ne 0 ]] && ! "$bind_unprivileged" && ! { command -v getcap >/dev/null && getcap "$caddy_binary" | grep -q cap_net_bind_service; }; then
      if [[ ! -t 0 ]]; then
        echo "Caddy needs permission to bind low ports. Grant CAP_NET_BIND_SERVICE to $caddy_binary, then retry." >&2; exit 1
      fi
      read -r -p "Allow Caddy to bind HTTPS ports using sudo setcap? [y/N] " bind_answer
      case "$bind_answer" in
        y|Y|yes|YES) sudo setcap cap_net_bind_service=+ep "$caddy_binary" ;;
        *) echo "Port permission skipped. Startup cancelled." >&2; exit 1 ;;
      esac
    fi
  fi
  caddy validate --config "$PWD/var/https/Caddyfile" --adapter caddyfile
  frontend_host=127.0.0.1
  export EDGE_CLIENT_IP_HEADER=x-real-ip
  export TRUST_EDGE_CLIENT_IP=1
  export ALLOW_INSECURE_HTTP=0
  echo "HTTPS: https://${https_host}:${https_port}"
  if [[ "$https_mode" == local ]]; then
    echo "Trust this public CA certificate on each device after startup:"
    echo "$XDG_DATA_HOME/caddy/pki/authorities/local/root.crt"
  else
    echo "Caddy needs permission to bind ports 80/443. If denied, grant its binary CAP_NET_BIND_SERVICE or use an administrator-managed Caddy service."
  fi
else
  export ALLOW_INSECURE_HTTP=1
  echo "WARNING: HTTP mode selected. Passwords and SMS codes are unencrypted without an external HTTPS proxy." >&2
fi
