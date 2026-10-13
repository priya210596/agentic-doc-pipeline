#!/bin/sh
# End-to-end demo on the fictional Rack Manager example. From reference-implementation/:  sh examples/rack-manager/run_demo.sh
set -e
cd "$(dirname "$0")/../.."
export DOC_AIDEV_HOME="$(mktemp -d)"
E=examples/rack-manager
PORT=8765
python3 $E/app/server.py --port $PORT >/dev/null &
APP=$!
trap 'kill $APP 2>/dev/null' EXIT
UP=""
for i in 1 2 3 4 5 6 7 8 9 10; do python3 -c "import urllib.request as u; u.urlopen('http://127.0.0.1:$PORT/api/ports')" 2>/dev/null && UP=1 && break; sleep 0.5; done
[ -n "$UP" ] || { echo "Demo app did not start on port $PORT (is it already in use?)"; exit 1; }
python3 -m docaidev setup --tracker paste >/dev/null
DOC="${1:-$DOC_AIDEV_HOME/RACK-210_RackManager_Review_Doc.docx}"
echo "##### Run 1: review threads left unresolved, so the gate blocks #####"
python3 -m docaidev run $E/spec.md --repo $E/sample-repo --ref RACK-210 --accuracy 1 \
  --observations $E/observations.json --reviews $E/reviews-blocked.json --app-url http://127.0.0.1:$PORT --seed $E/seed.json --meta $E/meta.json --style $E/style.json --draft $E/draft.md --docs $E/published-docs --docs-url https://docs.example.com/rack-manager || true
echo; echo "##### Run 2: threads resolved, screens seeded and captured, Word doc written after confirmation #####"
python3 -m docaidev run $E/spec.md --repo $E/sample-repo --ref RACK-210 --accuracy 1 \
  --observations $E/observations.json --reviews $E/reviews-resolved.json \
  --app-url http://127.0.0.1:$PORT --seed $E/seed.json \
  --meta $E/meta.json --style $E/style.json --draft $E/draft.md --docs $E/published-docs --docs-url https://docs.example.com/rack-manager --docx "$DOC" --confirm "write $DOC"
echo; echo "Word document: $DOC"
