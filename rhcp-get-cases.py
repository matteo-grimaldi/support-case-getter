#!/usr/bin/env python3
"""
Red Hat Cases TUI Monitor
A terminal user interface for monitoring Red Hat support cases
"""

import sys
import time
import json
import subprocess
import threading
import select
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

from rich.console import Console, Group
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
        self.key_pressed = None
        
    def keyboard_listener(self):
            """Dedicated thread to catch the 'q' key"""
            import tty
            import termios
            import sys
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                while self.running:
                    # This will block until a key is pressed
                    char = sys.stdin.read(1)
                    if char.lower() == 'q':
                        self.running = False
                        break
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            """Check for keyboard input in a non-blocking way"""
            import sys
            import tty
            import termios
            
            # Save terminal settings
            old_settings = termios.tcgetattr(sys.stdin)
            try:
                tty.setcbreak(sys.stdin.fileno())
                # Check if input is available
                if select.select([sys.stdin], [], [], 0)[0]:
                    char = sys.stdin.read(1)
                    if char.lower() == 'q':
                        self.running = False
            finally:
                # Restore terminal settings
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
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
        # Count cases for title
        case_count = len(account.cases) if account.cases else 0
        
        table = Table(
            title=f"[bold]{account.name}[/bold] ({account.id}) - {case_count} case(s)",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            border_style="cyan",
            expand=False,  # Don't expand to fill space
            show_lines=False  # Don't show lines between rows for better performance
        )
        
        table.add_column("Case #", style="cyan", no_wrap=True, width=10)
        table.add_column("Summary", style="white", no_wrap=True, width=100, overflow="crop")
        table.add_column("Severity", justify="center", no_wrap=True, width=8)
        table.add_column("Status", no_wrap=True, width=20)
        table.add_column("Product", style="white", no_wrap=True, width=35, overflow="crop")
        table.add_column("Modified", style="dim", no_wrap=True, width=19)
        
        # Check if cases is None or empty list
        if not account.cases or len(account.cases) == 0:
            table.add_row("", "[dim]No active cases[/dim]", "", "", "", "")
        else:
            # Add ALL cases - no filtering
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
                    case.summary or "",
                    f"[{severity_style}]{case.severity}[/{severity_style}]",
                    f"[{status_style}]{case.status}[/{status_style}]",
                    case.product or "",
                    case.last_modified or ""
                )
        
        return table
    
    def create_summary_panel(self) -> Panel:
        """Create a summary statistics panel"""
        # Use (acc.cases or []) to ensure len() always receives a list
        total_cases = sum(len(acc.cases or []) for acc in self.accounts)
        
        waiting_on_rh = sum(
            len([c for c in (acc.cases or []) if c.status == "Waiting on Red Hat"]) 
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
    
    def create_footer(self) -> Panel:
        """Create the footer panel with keyboard shortcuts"""
        footer_text = Text()
        footer_text.append("Shortcuts: ", style="bold white")
        footer_text.append("[Q] ", style="bold cyan")
        footer_text.append("Quit", style="white")
        footer_text.append(" | ", style="dim")
        footer_text.append("[Ctrl+C] ", style="bold cyan")
        footer_text.append("Exit", style="white")
        
        return Panel(footer_text, box=box.ROUNDED, style="dim")
    
    def create_layout(self) -> Layout:
        """Create the main layout"""
        layout = Layout()
        
        # Create vertical layout with fixed sizes for header/summary/footer
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="summary", size=3),
            Layout(name="body", ratio=1),  # Body gets remaining space
            Layout(name="footer", size=3)
        )
        
        # Add header
        layout["header"].update(self.create_header())
        
        # Add summary
        layout["summary"].update(self.create_summary_panel())
        
        # Add footer
        layout["footer"].update(self.create_footer())
        
        # Add account tables
        if self.accounts:
            # Create a simple group of tables instead of nested layouts
            tables = []
            for account in self.accounts:
                tables.append(self.create_account_table(account))
                # Add spacing between tables
                tables.append(Text(""))
            
            layout["body"].update(Group(*tables))
        
        return layout
    
    def run(self):
            """Run the TUI application"""
            try:
                self.accounts = self.load_accounts()
                self.console.print("[bold cyan]Initializing...[/bold cyan]")
                self.fetch_all_cases()
                
                # Start the keyboard listener in a background thread
                input_thread = threading.Thread(target=self.keyboard_listener, daemon=True)
                input_thread.start()

                with Live(self.create_layout(), console=self.console, refresh_per_second=2) as live:
                    last_fetch = time.time()
                    while self.running:
                        current_time = time.time()
                        if current_time - last_fetch >= self.refresh_seconds:
                            self.fetch_all_cases()
                            last_fetch = current_time
                        
                        live.update(self.create_layout())
                        time.sleep(0.2) # Faster response time
            except KeyboardInterrupt:
                pass
            finally:
                self.console.print("\n[bold yellow]Exiting...[/bold yellow]")

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