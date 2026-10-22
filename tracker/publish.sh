#!/bin/sh
# Rebuild reports, mails and the dashboard, then push the dashboard to GitHub Pages.
# Only dashboard/index.html is published; raw data files stay on this laptop.
# Payments R4s marked on the dashboard are pulled from the fines ledger first.
set -e
cd "$(dirname "$0")"
python3 track.py --pull
cd dashboard
if [ ! -d .git ]; then
  git init -q -b main
  # personal noreply address, so no work email ends up in the public history
  git config user.email "$(gh api user --jq '"\(.id)+\(.login)@users.noreply.github.com"')"
  git config user.name "$(gh api user --jq .login)"
  git config credential.helper '!gh auth git-credential'  # push with the gh login, this repo only
fi
git add index.html
if git diff --cached --quiet; then
  echo "Dashboard unchanged, nothing to publish."
  exit 0
fi
git commit -q -m "Update dashboard ($(date +%Y-%m-%d))

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
if ! git remote | grep -q origin; then
  repo="$(gh api user --jq .login)/rok-3514-dashboard"
  gh repo view "$repo" >/dev/null 2>&1 || gh repo create "$repo" --public \
    --description "Kingdom 3514 weekly fort and tech activity"
  git remote add origin "https://github.com/$repo.git"
  git push -q -u origin main
  gh api -X POST "repos/$repo/pages" -f 'source[branch]=main' -f 'source[path]=/' >/dev/null
else
  git push -q origin main
fi
echo "Published: https://$(gh api user --jq .login).github.io/rok-3514-dashboard/"
