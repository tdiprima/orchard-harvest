#!/usr/bin/env bash
set -euo pipefail

# Test ORCID public API anonymous access via the expanded-search endpoint
curl -s -m 20 -H "Accept: application/json" \
  "https://pub.orcid.org/v3.0/expanded-search/?q=affiliation-org-name:%22Example%20University%22&rows=3" \
  | head

# Test the ORCID works endpoint for one iD and summarize the first few work groups
curl -s -m 20 -H "Accept: application/json" "https://pub.orcid.org/v3.0/0000-0001-5109-3700/works" | python3 -c "
import json,sys
data=json.load(sys.stdin)
groups=data.get('group',[])
print('groups:',len(groups))
for g in groups[:3]:
    ws=g['work-summary'][0]
    print('-', ws['title']['title']['value'][:80], '|', (ws.get('publication-date') or {}).get('year',{}) )
"

# Run the harvest script with a limited number of authors and works
ORCID_MAX_AUTHORS=5 ORCID_MAX_WORKS=3 uv run main.py

# Run the test suite
uv run --with pytest==8.4.2 python -m pytest -q 2>&1 | tail -5

# Mutation check: verify tests catch a changed placeholder string
sed -i.bak 's/no public works listed/none/' orcid_harvest/formatter.py
uv run --with pytest==8.4.2 python -m pytest -q 2>&1 | tail -2
mv orcid_harvest/formatter.py.bak orcid_harvest/formatter.py

# Verify happy path exits cleanly (expect 0)
ORCID_MAX_AUTHORS=3 ORCID_MAX_WORKS=2 uv run main.py >/dev/null 2>&1
status=$?
echo "ok exit=$status"

# Verify invalid config exits with an error (expect non-zero)
set +e
ORCID_MAX_AUTHORS=0 uv run main.py
status=$?
set -e
echo "bad-config exit=$status"
