#!/usr/bin/env bash
#
# PIL one-line installer (macOS / Linux).
#
#   curl -fsSL https://raw.githubusercontent.com/pjpoulose/PIL/master/bootstrap.sh | bash
#
# What it does:
#   1. Makes sure Python 3.11+ and git exist (offers to install them).
#   2. Downloads PIL into ~/pil (or $PIL_DIR).
#   3. Installs the one Python dependency.
#   4. Creates your config file and fills in your Instagram account id
#      automatically when possible.
#   5. Tells you the next step in plain language.
#
# Nothing is uploaded anywhere. Your Instagram data never leaves your machine.
#
set -euo pipefail

REPO="https://github.com/pjpoulose/PIL.git"
PIL_DIR="${PIL_DIR:-$HOME/pil}"

say()  { printf '\n=== %s ===\n' "$1"; }
note() { printf '  %s\n' "$1"; }
ask()  { read -rp "$1 [y/N] " ans </dev/tty; [[ "${ans:-}" =~ ^[Yy]$ ]]; }

have_python() {
  command -v python3 >/dev/null 2>&1 &&
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null
}

# --- 1. Python 3.11+ ---------------------------------------------------------
if ! have_python; then
  say "Python 3.11 or newer was not found — PIL needs it to run."
  OS="$(uname -s)"
  installed=false
  if [[ "$OS" == "Darwin" ]]; then
    if command -v brew >/dev/null 2>&1; then
      if ask "Install Python with Homebrew?"; then brew install python@3.12; installed=true; fi
    else
      note "Install Python from https://www.python.org/downloads/ (3.11+), then re-run this installer."
    fi
  elif [[ "$OS" == "Linux" ]]; then
    cmd=""
    if command -v apt-get >/dev/null 2>&1; then cmd="sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv"
    elif command -v dnf >/dev/null 2>&1; then     cmd="sudo dnf install -y python3 python3-pip"
    elif command -v pacman >/dev/null 2>&1; then cmd="sudo pacman -S --noconfirm python python-pip"
    fi
    if [[ -n "$cmd" ]] && ask "Install Python now? ($cmd)"; then eval "$cmd"; installed=true; fi
  fi
  if ! have_python; then
    note "Please install Python 3.11+ and re-run this installer."
    exit 1
  fi
fi
say "Python OK: $(python3 --version 2>&1)"

# --- 2. git ------------------------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  say "git was not found — needed to download PIL."
  OS="$(uname -s)"
  if [[ "$OS" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
    ask "Install git with Homebrew?" && brew install git
  elif [[ "$OS" == "Linux" ]]; then
    if command -v apt-get >/dev/null 2>&1; then ask "Run: sudo apt-get install -y git ?" && sudo apt-get install -y git
    elif command -v dnf >/dev/null 2>&1; then     ask "Run: sudo dnf install -y git ?" && sudo dnf install -y git
    elif command -v pacman >/dev/null 2>&1; then ask "Run: sudo pacman -S --noconfirm git ?" && sudo pacman -S --noconfirm git
    fi
  fi
  command -v git >/dev/null 2>&1 || { note "Please install git and re-run."; exit 1; }
fi

# --- 3. Download PIL ---------------------------------------------------------
if [[ -d "$PIL_DIR/.git" ]]; then
  say "PIL already downloaded — updating to the latest version."
  git -C "$PIL_DIR" pull --ff-only || note "(could not update; continuing with what you have)"
else
  say "Downloading PIL into $PIL_DIR"
  git clone "$REPO" "$PIL_DIR"
fi

# --- 4. Python dependency ----------------------------------------------------
say "Installing PIL's Python helper (mcp)"
if ! python3 -m pip install "mcp<2" 2>/dev/null; then
  note "Retrying with --break-system-packages (safe: it only affects the mcp package)…"
  python3 -m pip install --break-system-packages "mcp<2"
fi

# --- 5. Config ---------------------------------------------------------------
CONFIG_DIR="$HOME/.config/pil"
mkdir -p "$CONFIG_DIR"
CONFIG="$CONFIG_DIR/pil.config.json"
if [[ ! -f "$CONFIG" ]]; then
  cp "$PIL_DIR/pil.config.example.json" "$CONFIG"
  note "Created $CONFIG"
fi

# Try to fill in the Instagram account id automatically.
if command -v instagram-cli >/dev/null 2>&1; then
  FBID="$(instagram-cli accounts 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(1)
accs = d if isinstance(d, list) else d.get("accounts", d.get("data", []))
if accs:
    a = accs[0]
    print(a.get("user_fbid") or a.get("user_own_fbid") or a.get("id") or "")
' 2>/dev/null || true)"
  if [[ -n "${FBID:-}" ]]; then
    python3 - "$CONFIG" "$FBID" <<'EOF'
import json, sys
path, fbid = sys.argv[1], sys.argv[2]
with open(path) as f: cfg = json.load(f)
cfg["account_id"] = fbid
with open(path, "w") as f: json.dump(cfg, f, indent=2)
print("Instagram account linked in your config.")
EOF
  else
    note "Could not read your Instagram account automatically."
    note "Link it in your Instagram skill first, then re-run this installer — or"
    note "ask your AI assistant to finish the setup for you."
  fi
else
  note "instagram-cli not found — this comes with the Instagram skill."
  note "Once it's available, re-run this installer to link your account automatically."
fi

# --- 6. Next step ------------------------------------------------------------
say "Done! PIL is ready in $PIL_DIR"
cat <<EOF
Next step — build your library (each step resumes safely; run them in order):

  cd "$PIL_DIR/bin"
  python3 ingest_saved.py      # download your saved posts
  python3 extract_content.py   # AI reads each post (takes a while — batches of 25)
  python3 tag_all.py           # auto-tags
  python3 export_pwa.py        # builds your installable app

Then install the app:
  • Computer: unzip the app folder, double-click Start PIL, click Install.
  • Phone:    python3 publish_pwa.py <app folder> --provider netlify,
              then scan the QR code with your phone.

Or skip all of this: install the PIL skill in your AI assistant and say
"set up my Instagram library" — it will walk through everything with you.
EOF
