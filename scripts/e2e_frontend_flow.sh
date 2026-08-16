#!/usr/bin/env bash
# End-to-end proof of the Relay journey against a running API (default :8000).
# Registers two fresh users, creates a responsibility, hands it over, and asserts
# the No Boomerang invariant from real API responses. No browser required.
#
#   ./scripts/e2e_frontend_flow.sh            # uses http://127.0.0.1:8000
#   RELAY_API=http://127.0.0.1:8000 ./scripts/e2e_frontend_flow.sh
set -euo pipefail
B="${RELAY_API:-http://127.0.0.1:8000}"
S=$RANDOM
jqp() { python3 -c "import sys,json;d=json.load(sys.stdin);print(d$1)"; }
pass() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; exit 1; }

echo "=== Relay E2E against $B (run $S) ==="

AT=$(curl -s -X POST "$B/v1/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"amy$S@relay.example\",\"password\":\"password123\",\"display_name\":\"Amy Stone\"}" | jqp "['access_token']")
BT=$(curl -s -X POST "$B/v1/auth/register" -H 'Content-Type: application/json' \
  -d "{\"email\":\"ben$S@relay.example\",\"password\":\"password123\",\"display_name\":\"Ben Stone\"}" | jqp "['access_token']")
[ -n "$AT" ] && [ -n "$BT" ] && pass "registered two users" || fail "register"

HID=$(curl -s -X POST "$B/v1/households" -H "Authorization: Bearer $AT" -H 'Content-Type: application/json' \
  -d '{"name":"Stone House","timezone":"America/New_York"}' | jqp "['id']")
pass "created household"

[ "$(curl -s "$B/v1/households" -H "Authorization: Bearer $AT" | jqp '.__len__()')" = "1" ] \
  && pass "GET /v1/households -> 1" || fail "list households"

TOK=$(curl -s -X POST "$B/v1/households/$HID/invites" -H "Authorization: Bearer $AT" -H 'Content-Type: application/json' \
  -d "{\"email\":\"ben$S@relay.example\"}" | jqp "['token']")
curl -s -X POST "$B/v1/invites/$TOK/accept" -H "Authorization: Bearer $BT" >/dev/null && pass "invite + accept"

MEM=$(curl -s "$B/v1/households/$HID/members" -H "Authorization: Bearer $AT")
echo "$MEM" | grep -q "Amy Stone" && pass "members carry display_name" || fail "member names"
BMID=$(echo "$MEM" | python3 -c "import sys,json;d=json.load(sys.stdin);print([m['id'] for m in d if m['role']=='member'][0])")

RID=$(curl -s -X POST "$B/v1/responsibilities?household_id=$HID" -H "Authorization: Bearer $AT" -H 'Content-Type: application/json' \
  -d '{"title":"Smoke detector safety","domain":"home","completion_standard":"All detectors tested","target_at":"2026-09-01T14:00:00Z","steps":[
    {"step_key":"anticipate","kind":"anticipate","description":"Remember the monthly test","provenance":"user_explicit"},
    {"step_key":"decide","kind":"decide","description":"Decide which need new batteries","provenance":"user_explicit","is_assumption":true},
    {"step_key":"execute","kind":"execute","description":"Test each detector","provenance":"user_explicit","due_at":"2026-09-01T14:00:00Z"},
    {"step_key":"follow_up","kind":"follow_up","description":"Log completion","provenance":"user_explicit"}]}' | jqp "['id']")
pass "created 4-step responsibility"

QBEFORE=$(curl -s "$B/v1/me/ghost-queue" -H "Authorization: Bearer $AT" | jqp '.__len__()')
pass "Amy ghost-queue before: $QBEFORE reminders"

CID=$(curl -s -X POST "$B/v1/responsibilities/$RID/handoffs" -H "Authorization: Bearer $AT" -H 'Content-Type: application/json' \
  -d "{\"target_membership_id\":\"$BMID\"}" | jqp "['id']")
pass "proposed handoff Amy -> Ben"

[ "$(curl -s "$B/v1/me/handoffs" -H "Authorization: Bearer $BT" | jqp '.__len__()')" = "1" ] \
  && pass "Ben inbox (GET /v1/me/handoffs) -> 1 pending" || fail "inbox"

ACC=$(curl -s -X POST "$B/v1/handoffs/$CID/accept" -H "Authorization: Bearer $BT" -H 'Content-Type: application/json' \
  -d "{\"idempotency_key\":\"e2e-$S\"}")
echo "  ✓ Ben accepted: reminders_rerouted=$(echo "$ACC" | jqp "['reminders_rerouted']") ownership_version=$(echo "$ACC" | jqp "['ownership_version']")"

AQ=$(curl -s "$B/v1/me/ghost-queue" -H "Authorization: Bearer $AT" | jqp '.__len__()')
BQ=$(curl -s "$B/v1/me/ghost-queue" -H "Authorization: Bearer $BT" | jqp '.__len__()')
[ "$AQ" = "0" ] && pass "NO BOOMERANG: Amy queue now empty" || fail "Amy queue = $AQ"
[ "$BQ" = "$QBEFORE" ] && pass "NO BOOMERANG: Ben queue now has $BQ (rerouted)" || fail "Ben queue = $BQ"

PROOF=$(curl -s "$B/v1/responsibilities/$RID/proof-of-relief" -H "Authorization: Bearer $AT")
echo "  ✓ proof: transferred=$(echo "$PROOF" | jqp "['transferred']") lifecycle_obligations=$(echo "$PROOF" | jqp "['lifecycle_obligations_transferred']")"

OWN=$(curl -s "$B/v1/responsibilities/$RID" -H "Authorization: Bearer $AT" | jqp "['current_owner_membership_id']")
[ "$OWN" = "$BMID" ] && pass "ownership moved: owner is now Ben" || fail "owner not moved"

echo "=== E2E PASSED ==="
