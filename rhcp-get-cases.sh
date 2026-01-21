#!/bin/zsh

# Configuration
ACCOUNTS_FILE="accounts.yaml"
OFFLINE_TOKEN="${1:-}"
API_ENDPOINT="https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
CLIENT_ID="rhsm-api"
RESTART_MINUTES=15

DELAY=$((RESTART_MINUTES * 60))

# Colors
autoload -U colors && colors
RED=$fg[red]
CYAN=$fg[cyan]
BOLD=$bold_color
NC=$reset_color

# Validate input
if [[ -z "$OFFLINE_TOKEN" ]]; then
    echo "Usage: $0 <offline_token>"
    exit 1
fi

if [[ ! -f "$ACCOUNTS_FILE" ]]; then
    echo "Error: $ACCOUNTS_FILE not found."
    exit 1
fi

while true; do
    # Obtain Access Token
    RESPONSE=$(curl -s -X POST "$API_ENDPOINT" \
        -d "grant_type=refresh_token" \
        -d "refresh_token=$OFFLINE_TOKEN" \
        -d "client_id=$CLIENT_ID")

    ACCESS_TOKEN=$(echo "$RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

    if [[ -z "$ACCESS_TOKEN" ]]; then
        echo "Error: Failed to obtain access token"
        exit 1
    fi

    clear
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Starting case data retrieval..."
    echo -e "\n"

    # Read YAML and loop through accounts
    # We use yq to output "ID|NAME" and split it in the loop
    yq e '.accounts[] | .id + "|" + .name' "$ACCOUNTS_FILE" | while read -r line; do
        ACC_NUM="${line%%|*}"
        ACC_NAME="${line##*|}"

        echo "--- Fetching data for Account: $ACC_NAME ($ACC_NUM) ---"

        # API Call
        curl -s -X POST \
                -H "Authorization: Bearer $ACCESS_TOKEN" \
                -H "Content-Type: application/json" \
                -d @- "https://api.access.redhat.com/support/v1/cases/filter" <<EOF | jq -r --arg b "$BOLD" --arg c "$CYAN" --arg r "$RED" --arg nc "$NC" '
                .cases | map({
                    case: ("https://access.redhat.com/support/cases/#/case/" + .caseNumber), 
                    status: .status, 
                    severity: .severity, 
                    product: .product, 
                    summary: .summary, 
                    lastModifiedAt: .lastModifiedDate
                    }) | 
                [ ("CASE"), ("SUMMARY"), ("SEVERITY"), ("STATUS"), ("PRODUCT"), ("MODIFIED") ],
                (.[] | [ 
                    .case, 
                    .summary[:100],
                    .severity,
                    (if .status == "Waiting on Red Hat" then ($r + .status + $nc) else ($c + .status + $nc) end), 
                    .product,
                    .lastModifiedAt
                    ]) | @tsv' | column -t -s $'\t'
                {
                "accountNumber": "$ACC_NUM",
                "statuses": ["Waiting on Customer", "Waiting on Red Hat"]
                }
EOF
        echo -e "\n"
    done


    sleep "$DELAY"
done