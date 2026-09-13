<#
.SYNOPSIS
  PIL one-line installer (Windows).

  Run in PowerShell:
    irm https://raw.githubusercontent.com/pjpoulose/PIL/master/bootstrap.ps1 | iex

.DESCRIPTION
  1. Makes sure Python 3.11+ and git exist (offers to install via winget).
  2. Downloads PIL into ~\pil (or $env:PIL_DIR).
  3. Installs the one Python dependency.
  4. Creates your config file and fills in your Instagram account id
     automatically when possible.
  5. Tells you the next step in plain language.

  Nothing is uploaded anywhere. Your Instagram data never leaves your machine.
#>
$ErrorActionPreference = 'Stop'

$Repo   = 'https://github.com/pjpoulose/PIL.git'
$PilDir = if ($env:PIL_DIR) { $env:PIL_DIR } else { Join-Path $HOME 'pil' }

function Say($msg)  { Write-Host "`n=== $msg ===" }
function Note($msg) { Write-Host "  $msg" }
function Ask($msg) {
  $ans = Read-Host "$msg [y/N]"
  return $ans -match '^[Yy]$'
}
function Have-Python {
  foreach ($c in @('py -3.11', 'py -3.12', 'py -3', 'python3', 'python')) {
    $parts = $c -split ' '
    try {
      $v = & $parts[0] $parts[1..($parts.Length-1)] -c 'import sys; print(1 if sys.version_info >= (3,11) else 0)' 2>$null
      if ($v -eq '1') { return $c }
    } catch {}
  }
  return $null
}

# --- 1. Python 3.11+ ----------------------------------------------------------
$PyCmd = Have-Python
if (-not $PyCmd) {
  Say 'Python 3.11 or newer was not found — PIL needs it to run.'
  if ((Get-Command winget -ErrorAction SilentlyContinue) -and (Ask 'Install Python with winget?')) {
    winget install --id Python.Python.3.12 -e --silent --accept-source-agreements --accept-package-agreements
    $PyCmd = Have-Python
  }
  if (-not $PyCmd) {
    Note 'Install Python 3.11+ from https://www.python.org/downloads/ (tick "Add python.exe to PATH"), then re-run.'
    exit 1
  }
}
$PyParts = $PyCmd -split ' '
$PyExe = $PyParts[0]
$PyArgs = if ($PyParts.Length -gt 1) { $PyParts[1..($PyParts.Length-1)] } else { @() }
function Py { & $PyExe @PyArgs @args }
Say "Python OK: $(Py --version 2>&1)"

# --- 2. git -------------------------------------------------------------------
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Say 'git was not found — needed to download PIL.'
  if ((Get-Command winget -ErrorAction SilentlyContinue) -and (Ask 'Install git with winget?')) {
    winget install --id Git.Git -e --silent --accept-source-agreements --accept-package-agreements
  }
  if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Note 'Install git from https://git-scm.com/download/win, then re-run.'
    exit 1
  }
  # refresh PATH for this session
  $env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
              [System.Environment]::GetEnvironmentVariable('Path','User')
}

# --- 3. Download PIL ----------------------------------------------------------
if (Test-Path (Join-Path $PilDir '.git')) {
  Say 'PIL already downloaded — updating to the latest version.'
  git -C $PilDir pull --ff-only 2>$null; if ($LASTEXITCODE -ne 0) { Note '(could not update; continuing with what you have)' }
} else {
  Say "Downloading PIL into $PilDir"
  git clone $Repo $PilDir
}

# --- 4. Python dependency -----------------------------------------------------
Say "Installing PIL's Python helper (mcp)"
Py -m pip install 'mcp<2'

# --- 5. Config ----------------------------------------------------------------
$ConfigDir = Join-Path $HOME '.config\pil'
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null
$Config = Join-Path $ConfigDir 'pil.config.json'
if (-not (Test-Path $Config)) {
  Copy-Item (Join-Path $PilDir 'pil.config.example.json') $Config
  Note "Created $Config"
}

if (Get-Command instagram-cli -ErrorAction SilentlyContinue) {
  try {
    $fbid = instagram-cli accounts 2>$null | Py -c "
import json, sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(1)
accs = d if isinstance(d, list) else d.get('accounts', d.get('data', []))
print((accs[0].get('user_fbid') or accs[0].get('user_own_fbid') or accs[0].get('id') or '') if accs else '')
" 2>$null
    if ($fbid) {
      Py - $Config $fbid.Trim() @'
import json, sys
path, fbid = sys.argv[1], sys.argv[2]
with open(path) as f: cfg = json.load(f)
cfg["account_id"] = fbid
with open(path, "w") as f: json.dump(cfg, f, indent=2)
print("Instagram account linked in your config.")
'@
    } else {
      Note 'Could not read your Instagram account automatically.'
      Note 'Link it in your Instagram skill first, then re-run — or ask your AI assistant to finish setup.'
    }
  } catch { Note 'Could not read your Instagram account automatically.' }
} else {
  Note 'instagram-cli not found — this comes with the Instagram skill.'
  Note "Once it's available, re-run this installer to link your account automatically."
}

# --- 6. Next step -------------------------------------------------------------
Say "Done! PIL is ready in $PilDir"
@"
Next step — build your library (each step resumes safely; run them in order):

  cd "$PilDir\bin"
  python3 ingest_saved.py      # download your saved posts
  python3 extract_content.py   # AI reads each post (takes a while — batches of 25)
  python3 tag_all.py           # auto-tags
  python3 export_pwa.py        # builds your installable app

Then install the app:
  - Computer: unzip the app folder, double-click Start PIL.vbs, click Install.
  - Phone:    python3 publish_pwa.py <app folder> --provider netlify,
              then scan the QR code with your phone.

Or skip all of this: paste this into your AI assistant and it will do the
whole setup with you:

  Clone https://github.com/pjpoulose/PIL into your workspace and follow its
  SKILL.md to set up my Personal Instagram Library.
"@
