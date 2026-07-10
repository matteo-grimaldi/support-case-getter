"""
Shared Red Hat API client, data models, and account loading utilities.
"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

import yaml
import requests


@dataclass
class Case:
    """Represents a Red Hat support case"""
    case_number: str
    summary: str
    severity: str
    status: str
    product: str
    created: str
    last_modified: str

    @property
    def case_url(self) -> str:
        return f"https://access.redhat.com/support/cases/#/case/{self.case_number}"


@dataclass
class Account:
    """Represents a Red Hat account"""
    id: str
    name: str
    cases: list[Case] | None = None

    def __post_init__(self):
        if self.cases is None:
            self.cases = []


class RedHatAPI:
    """Handles Red Hat API interactions"""

    TOKEN_ENDPOINT = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
    CASES_ENDPOINT = "https://api.access.redhat.com/support/v1/cases/filter"
    CLIENT_ID = "rhsm-api"

    def __init__(self, offline_token: str):
        self.offline_token = offline_token
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None

    def get_access_token(self) -> str:
        """Obtain or refresh the access token"""
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        response = requests.post(
            self.TOKEN_ENDPOINT,
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.offline_token,
                "client_id": self.CLIENT_ID
            }
        )

        if response.status_code != 200:
            raise Exception(f"Failed to obtain access token: {response.text}")

        data = response.json()
        self.access_token = data.get("access_token")

        if not self.access_token:
            raise Exception("No access token in response")

        expires_in = data.get("expires_in", 300)
        self.token_expiry = datetime.now() + timedelta(seconds=expires_in)

        return self.access_token

    def fetch_cases(self, account_number: str) -> List[Case]:
        """Fetch cases for a specific account"""
        token = self.get_access_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        payload = {
            "accountNumber": account_number,
            "statuses": ["Waiting on Customer", "Waiting on Red Hat"]
        }

        response = requests.post(
            self.CASES_ENDPOINT,
            headers=headers,
            json=payload
        )

        if response.status_code != 200:
            raise Exception(f"Failed to fetch cases: {response.text}")

        data = response.json()
        cases = []

        for case_data in data.get("cases", []):
            cases.append(Case(
                case_number=case_data.get("caseNumber", ""),
                summary=case_data.get("summary", "")[:100],
                severity=case_data.get("severity", ""),
                status=case_data.get("status", ""),
                product=case_data.get("product", ""),
                created=case_data.get("createdDate", ""),
                last_modified=case_data.get("lastModifiedDate", "")
            ))

        return cases


def load_accounts(yaml_path: str) -> List[Account]:
    """Load accounts from a YAML file"""
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Accounts file not found: {path}")

    with open(path, 'r') as f:
        data = yaml.safe_load(f)

    return [
        Account(id=acc.get('id', ''), name=acc.get('name', ''))
        for acc in data.get('accounts', [])
    ]
