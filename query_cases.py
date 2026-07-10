#!/usr/bin/env python3
"""
Query Red Hat support cases for a specific account and product.
Outputs structured JSON for analysis.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from redhat_api import RedHatAPI


def resolve_token(cli_token: str | None) -> str:
    if cli_token:
        return cli_token

    env_token = os.environ.get("REDHAT_OFFLINE_TOKEN")
    if env_token:
        return env_token

    token_file = Path.home() / "rhcp-token"
    if token_file.exists():
        return token_file.read_text().strip()

    print("Error: No offline token found.", file=sys.stderr)
    print("Provide one via --token, REDHAT_OFFLINE_TOKEN env var, or ~/rhcp-token file.", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Query Red Hat support cases for a specific account and product"
    )
    parser.add_argument("--account", required=True, help="Red Hat account number")
    parser.add_argument("--product", required=True, help="Product name filter (case-insensitive substring match)")
    parser.add_argument("--token", default=None, help="Red Hat offline token (or set REDHAT_OFFLINE_TOKEN env var)")
    args = parser.parse_args()

    token = resolve_token(args.token)
    api = RedHatAPI(token)

    cases = api.fetch_cases(args.account)

    product_filter = args.product.lower()
    filtered = [c for c in cases if product_filter in c.product.lower()]

    now = datetime.now(timezone.utc)
    case_records = []
    for c in filtered:
        try:
            dt = datetime.fromisoformat(c.created.strip().replace('Z', '+00:00'))
            age_days = (now - dt).days
        except (ValueError, AttributeError):
            age_days = None

        case_records.append({
            "case_number": c.case_number,
            "summary": c.summary,
            "severity": c.severity,
            "status": c.status,
            "product": c.product,
            "created": c.created,
            "last_modified": c.last_modified,
            "case_url": c.case_url,
            "age_days": age_days,
        })

    ages = [r["age_days"] for r in case_records if r["age_days"] is not None]

    severity_counts = {}
    status_counts = {}
    for r in case_records:
        severity_counts[r["severity"]] = severity_counts.get(r["severity"], 0) + 1
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    output = {
        "account_number": args.account,
        "product_filter": args.product,
        "cases": case_records,
        "statistics": {
            "total_cases": len(case_records),
            "by_severity": severity_counts,
            "by_status": status_counts,
            "oldest_case_days": max(ages) if ages else None,
            "newest_case_days": min(ages) if ages else None,
            "average_age_days": round(sum(ages) / len(ages)) if ages else None,
        },
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
