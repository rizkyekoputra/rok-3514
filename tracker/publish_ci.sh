#!/bin/sh
# GitHub Action side of publish.sh: push the freshly built dashboard/index.html to the Pages repo.
# Needs DEPLOY_KEY (write deploy key of the Pages repo) and DASHBOARD_REPO (owner/name).
# Refuses to publish if the live dashboard has a week this checkout doesn't (laptop published but didn't push).
set -e
cd "$(dirname "$0")"
key="$RUNNER_TEMP/dashboard_key"
printf '%s\n' "$DEPLOY_KEY" > "$key"
chmod 600 "$key"
export GIT_SSH_COMMAND="ssh -i $key -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
site="$RUNNER_TEMP/site"
git clone -q --depth 1 "git@github.com:$DASHBOARD_REPO.git" "$site"

python3 - "$site/index.html" dashboard/index.html <<'EOF'
import json, re, sys
weeks = lambda p: set(json.loads(re.search(r'const DATA = (.*?);\n', open(p, encoding='utf-8').read()).group(1))['weeks'])
missing = weeks(sys.argv[1]) - weeks(sys.argv[2])
if missing:
    sys.exit(f'Live dashboard has week(s) {sorted(missing)} that are not in the repo. Push the laptop changes first.')
EOF

cp dashboard/index.html "$site/index.html"
cd "$site"
git add index.html
if git diff --cached --quiet; then
  echo "Dashboard unchanged, nothing to publish."
  exit 0
fi
git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
  commit -q -m "Recalculate dashboard ($(date -u +%Y-%m-%d))"
git push -q origin HEAD:main
echo "Published"
