"""
Shared Red Hat API client, data models, and account loading utilities.

Fallback strategy for current API behavior:
- v3 filter returns useful `totalCount` but often empty `cases`.
- search API provides case numbers.
- individual v3 case GET returns full case details reliably.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from urllib.parse import quote

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
    CASES_FILTER_ENDPOINT = "https://api.access.redhat.com/support/v3/cases/filter"
    CASES_GET_ENDPOINT = "https://api.access.redhat.com/support/v3/cases"
    SEARCH_ENDPOINT = "https://api.access.redhat.com/support/search/cases"
    CLIENT_ID = "rhsm-api"
    MAX_RESULTS_PER_PAGE = 200
    MAX_CONCURRENT_REQUESTS = 15

    def __init__(self, offline_token: str):
        self.offline_token = offline_token
        self.access_token: Optional[str] = None
        self.token_expiry: Optional[datetime] = None
        self._session = requests.Session()

    def get_access_token(self) -> str:
        """Obtain or refresh the access token"""
        if self.access_token and self.token_expiry and datetime.now() < self.token_expiry:
            return self.access_token

        response = self._session.post(
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

    def _auth_headers(self) -> dict:
        token = self.get_access_token()
        return {"Authorization": f"Bearer {token}"}

    def _get_open_case_count(self, account_number: str) -> int:
        """Return open-case count from v3 filter (or -1 if unavailable)."""
        resp = self._session.post(
            self.CASES_FILTER_ENDPOINT,
            headers={**self._auth_headers(), "Content-Type": "application/json"},
            json={
                "accountNumbers": [account_number],
                "maxResults": 1,
                "offset": 0,
            },
        )
        if resp.status_code != 200:
            return -1
        return resp.json().get("totalCount", 0)

    def _search_case_numbers(self, account_number: str) -> List[str]:
        """List case numbers for an account from search index."""
        case_numbers: List[str] = []
        rows_per_page = 200
        start = 0

        while True:
            q = f"case_accountNumber:{account_number}"
            url = (
                f"{self.SEARCH_ENDPOINT}"
                f"?q={quote(q)}"
                f"&rows={rows_per_page}&start={start}"
                f"&sort=case_lastModifiedDate+desc"
            )
            resp = self._session.get(url, headers=self._auth_headers())
            if resp.status_code != 200:
                break

            data = resp.json().get("response", {})
            docs = data.get("docs", [])
            for doc in docs:
                case_number = doc.get("case_number")
                if case_number:
                    case_numbers.append(case_number)

            start += len(docs)
            if not docs or start >= data.get("numFound", 0):
                break

        return case_numbers

    def _fetch_single_case(self, case_number: str) -> Optional[Case]:
        """Fetch a case by number; return None for closed/error cases."""
        try:
            resp = self._session.get(
                f"{self.CASES_GET_ENDPOINT}/{case_number}",
                headers=self._auth_headers(),
            )
        except requests.RequestException:
            return None

        if resp.status_code != 200:
            return None

        d = resp.json()
        if d.get("isClosed") or (d.get("status") or "").strip().lower() == "closed":
            return None

        return Case(
            case_number=d.get("caseNumber", ""),
            summary=(d.get("summary") or "")[:100],
            severity=d.get("severity", ""),
            status=d.get("status", ""),
            product=d.get("product", ""),
            created=d.get("createdDate", ""),
            last_modified=d.get("lastModifiedDate", ""),
        )

    def fetch_cases(self, account_number: str) -> List[Case]:
        """Fetch open cases using search + per-case GET fallback."""
        target = self._get_open_case_count(account_number)
        if target == 0:
            return []

        case_numbers = self._search_case_numbers(account_number)
        if not case_numbers:
            return []

        cases: List[Case] = []
        with ThreadPoolExecutor(max_workers=self.MAX_CONCURRENT_REQUESTS) as pool:
            futures = {pool.submit(self._fetch_single_case, cn): cn for cn in case_numbers}
            for future in as_completed(futures):
                case = future.result()
                if case is None:
                    continue
                cases.append(case)
                if target > 0 and len(cases) >= target:
                    for f in futures:
                        f.cancel()
                    break

        cases.sort(key=lambda c: c.last_modified or "", reverse=True)
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
