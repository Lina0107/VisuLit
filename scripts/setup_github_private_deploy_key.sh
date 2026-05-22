#!/usr/bin/env bash
# Run on the VPS as root (or the user that owns /opt/visulit):
#   cd /opt/visulit && bash scripts/setup_github_private_deploy_key.sh
#
# Prepares SSH deploy key so `git pull` works after the repo is made private.
set -euo pipefail

REPO_SSH="git@github.com:Lina0107/VisuLit.git"
KEY_PATH="${HOME}/.ssh/visulit_deploy_ed25519"
SSH_CONFIG="${HOME}/.ssh/config"

if [ ! -d .git ]; then
  echo "ERROR: Run this from the git repo root (e.g. cd /opt/visulit)."
  exit 1
fi

mkdir -p "${HOME}/.ssh"
chmod 700 "${HOME}/.ssh"

if [ ! -f "${KEY_PATH}" ]; then
  echo "Generating deploy key at ${KEY_PATH} ..."
  ssh-keygen -t ed25519 -f "${KEY_PATH}" -N "" -C "visulit-vps-deploy"
fi
chmod 600 "${KEY_PATH}"
chmod 644 "${KEY_PATH}.pub"

if ! grep -q "Host github.com-visulit" "${SSH_CONFIG}" 2>/dev/null; then
  cat >> "${SSH_CONFIG}" <<'EOF'

Host github.com-visulit
  HostName github.com
  User git
  IdentityFile ~/.ssh/visulit_deploy_ed25519
  IdentitiesOnly yes
EOF
  chmod 600 "${SSH_CONFIG}"
  echo "Added github.com-visulit to ${SSH_CONFIG}"
fi

# Use the SSH host alias so this key is used only for this repo.
REPO_SSH="git@github.com-visulit:Lina0107/VisuLit.git"
git remote set-url origin "${REPO_SSH}"
echo "git remote origin -> ${REPO_SSH}"

echo ""
echo "========== ADD THIS DEPLOY KEY ON GITHUB =========="
echo "Repo: https://github.com/Lina0107/VisuLit/settings/keys"
echo "Title: visulit-vps (read-only is enough)"
echo ""
cat "${KEY_PATH}.pub"
echo "==================================================="
echo ""
echo "After saving the key on GitHub, test:"
echo "  ssh -T git@github.com-visulit"
echo "  git pull origin main"
echo ""
echo "Then make the repo private:"
echo "  Settings -> Danger zone -> Change visibility -> Private"
echo ""
