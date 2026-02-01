#!/usr/bin/env python3
"""
Red Hat Cases TUI Monitor
A terminal user interface for monitoring Red Hat support cases
"""

import sys
import time
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box
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
    last_modified: str
    
    @property
    def case_url(self) -> str:
        return f"https://access.redhat.com/support/cases/#/case/{self.case_number}"


@dataclass
class Account:
    """Represents a Red Hat account"""
    id: str
    name: str
    cases: List[Case] = None
    
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
        
        # Token typically expires in 5 minutes, refresh before that
        expires_in = data.get("expires_in", 300)
        self.token_expiry = datetime.now()
        
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
                last_modified=case_data.get("lastModifiedDate", "")
            ))
        
        return cases


class CaseMonitorTUI:
    """Main TUI application"""
    
    def __init__(self, accounts_file: str, offline_token: str, refresh_minutes: int = 15):
        self.accounts_file = Path(accounts_file)
        self.api = RedHatAPI(offline_token)
        self.refresh_seconds = refresh_minutes * 60
        self.console = Console()
        self.accounts: List[Account] = []
        self.last_update: Optional[datetime] = None
        self.running = True
        self.error_message: Optional[str] = None
        
    def load_accounts(self) -> List[Account]:
        """Load accounts from YAML file"""
        if not self.accounts_file.exists():
            raise FileNotFoundError(f"Accounts file not found: {self.accounts_file}")
        
        with open(self.accounts_file, 'r') as f:
            data = yaml.safe_load(f)
        
        accounts = []
        for acc_data in data.get('accounts', []):
            accounts.append(Account(
                id=acc_data.get('id', ''),
                name=acc_data.get('name', '')
            ))
        
        return accounts
    
    def fetch_all_cases(self):
        """Fetch cases for all accounts"""
        self.error_message = None
        try:
            for account in self.accounts:
                try:
                    account.cases = self.api.fetch_cases(account.id)
                except Exception as e:
                    self.error_message = f"Error fetching cases for {account.name}: {str(e)}"
                    account.cases = []
            
            self.last_update = datetime.now()
        except Exception as e:
            self.error_message = f"Error: {str(e)}"
    
    def create_header(self) -> Panel:
        """Create the header panel"""
        header_text = Text()
        header_text.append("Red Hat Cases Monitor", style="bold cyan")
        header_text.append("\n")
        
        if self.last_update:
            header_text.append(f"Last Update: {self.last_update.strftime('%Y-%m-%d %H:%M:%S')}", style="dim")
        
        next_update = self.refresh_seconds - (int(time.time()) % self.refresh_seconds)
        header_text.append(f" | Next refresh in: {next_update}s", style="dim")
        
        if self.error_message:
            header_text.append(f"\n⚠ {self.error_message}", style="bold red")
        
        return Panel(header_text, box=box.ROUNDED, style="cyan")
    
    def create_account_table(self, account: Account) -> Table:
        """Create a table for a single account's cases"""
        table = Table(
            title=f"[bold]{account.name}[/bold] ({account.id})",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            border_style="cyan"
        )
        
        table.add_column("Case #", style="cyan", no_wrap=True)
        table.add_column("Summary", style="white", max_width=50)
        table.add_column("Severity", justify="center", no_wrap=True)
        table.add_column("Status", justify="center", no_wrap=True)
        table.add_column("Product", style="white", max_width=20)
        table.add_column("Modified", style="dim", no_wrap=True)
        
        if not account.cases:
            table.add_row("", "[dim]No active cases[/dim]", "", "", "", "")
        else:
            for case in account.cases:
                # Color code status
                if case.status == "Waiting on Red Hat":
                    status_style = "bold red"
                else:
                    status_style = "bold yellow"
                
                # Color code severity
                severity_style = {
                    "Urgent": "bold red",
                    "High": "red",
                    "Normal": "yellow",
                    "Low": "green"
                }.get(case.severity, "white")
                
                table.add_row(
                    f"[link={case.case_url}]{case.case_number}[/link]",
                    case.summary,
                    f"[{severity_style}]{case.severity}[/{severity_style}]",
                    f"[{status_style}]{case.status}[/{status_style}]",
                    case.product,
                    case.last_modified
                )
        
        return table
    
    def create_summary_panel(self) -> Panel:
        """Create a summary statistics panel"""
        total_cases = sum(len(acc.cases) for acc in self.accounts)
        waiting_on_rh = sum(
            len([c for c in acc.cases if c.status == "Waiting on Red Hat"]) 
            for acc in self.accounts
        )
        waiting_on_customer = total_cases - waiting_on_rh
        
        summary_text = Text()
        summary_text.append(f"Total Cases: {total_cases}", style="bold white")
        summary_text.append(" | ")
        summary_text.append(f"Waiting on Red Hat: {waiting_on_rh}", style="bold red")
        summary_text.append(" | ")
        summary_text.append(f"Waiting on Customer: {waiting_on_customer}", style="bold yellow")
        
        return Panel(summary_text, title="Summary", box=box.ROUNDED, style="green")
    
    def create_layout(self) -> Layout:
        """Create the main layout"""
        layout = Layout()
        
        # Create vertical layout
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="summary", size=3),
            Layout(name="body")
        )
        
        # Add header
        layout["header"].update(self.create_header())
        
        # Add summary
        layout["summary"].update(self.create_summary_panel())
        
        # Add account tables
        if self.accounts:
            body_layout = Layout()
            body_layout.split_column(
                *[Layout(name=f"account_{i}") for i in range(len(self.accounts))]
            )
            
            for i, account in enumerate(self.accounts):
                body_layout[f"account_{i}"].update(self.create_account_table(account))
            
            layout["body"].update(body_layout)
        
        return layout
    
    def run(self):
        """Run the TUI application"""
        try:
            # Load accounts
            self.accounts = self.load_accounts()
            
            # Initial fetch
            self.console.print("[bold cyan]Initializing...[/bold cyan]")
            self.fetch_all_cases()
            
            # Main loop with live updates
            with Live(self.create_layout(), console=self.console, refresh_per_second=1) as live:
                last_fetch = time.time()
                
                while self.running:
                    current_time = time.time()
                    
                    # Refresh data if needed
                    if current_time - last_fetch >= self.refresh_seconds:
                        self.fetch_all_cases()
                        last_fetch = current_time
                    
                    # Update display
                    live.update(self.create_layout())
                    
                    # Small sleep to prevent CPU spinning
                    time.sleep(0.5)
                    
        except KeyboardInterrupt:
            self.console.print("\n[bold yellow]Shutting down...[/bold yellow]")
        except Exception as e:
            self.console.print(f"\n[bold red]Error: {str(e)}[/bold red]")
            raise


def main():
    """Main entry point"""
    if len(sys.argv) != 3:
        print("Usage: redhat_cases_tui.py <accounts_file> <offline_token>")
        print("\nExample:")
        print("  ./redhat_cases_tui.py accounts.yaml your-offline-token")
        sys.exit(1)
    
    accounts_file = sys.argv[1]
    offline_token = sys.argv[2]
    
    app = CaseMonitorTUI(accounts_file, offline_token, refresh_minutes=15)
    app.run()


if __name__ == "__main__":
    main()