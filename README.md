# Red Hat Support Cases TUI Monitor

A modern Terminal User Interface (TUI) for continuously monitoring Red Hat support case status across multiple accounts using the Red Hat Customer Portal API. Available in both Python and pure Bash implementations.

## Overview

This TUI application retrieves and displays real-time support case data for multiple Red Hat accounts, filtering by case status ("Waiting on Customer" or "Waiting on Red Hat"). It provides an interactive, color-coded dashboard that auto-refreshes at configurable intervals, using OAuth 2.0 authentication via Red Hat's Single Sign-On service.

## Features

### Core Functionality
- **Multi-account monitoring**: Track cases across multiple Red Hat customer accounts
- **Status filtering**: Focus on active cases waiting for customer or Red Hat response
- **Auto-refresh**: Continuously poll case data at configurable intervals (default: 15 minutes)
- **OAuth 2.0 authentication**: Secure token-based authentication using offline tokens with auto-refresh
- **Account labeling**: Display friendly names for account numbers

### Interactive TUI
- **Live dashboard**: Real-time updates without screen flicker
- **Color-coded status**: Visual indicators for case priority and status
  - 🔴 Red: Waiting on Red Hat (needs attention)
  - 🟡 Yellow: Waiting on Customer
- **Severity highlighting**: Urgent/High/Normal/Low with color coding
- **Summary statistics**: Quick overview of total cases and status breakdown
- **Keyboard shortcuts**: Press 'Q' to quit, Ctrl+C for emergency exit
- **Resize handling**: Adapts to terminal size changes without losing data

## Prerequisites

#### Required Tools
- `python3` (version 3.8 or higher)
- `pip3` - Python package manager
- `curl` - for API requests (used internally by requests library)

#### Python Dependencies
- `rich>=13.0.0` - Terminal UI framework
- `requests>=2.31.0` - HTTP library for API calls
- `PyYAML>=6.0` - YAML configuration file parsing

Install Python dependencies:
```bash
# Standard installation
pip3 install rich requests PyYAML

# Or using requirements.txt
pip3 install -r requirements.txt

# For managed devices (see Managed Devices section)
python3 -m venv .venv
source .venv/bin/activate
pip install rich requests PyYAML
```

### Red Hat Customer Portal Access
- Active Red Hat Customer Portal account
- Appropriate permissions for the accounts you want to monitor
- API access enabled for your user account

## Getting Your Offline Token

1. Visit the [Red Hat API Tokens page](https://access.redhat.com/management/api)
2. Log in with your Red Hat Customer Portal credentials
3. Click **Generate Token**
4. Copy the generated offline token
5. Store it securely in an environment variable or file

```bash
# Store in environment variable (recommended)
export REDHAT_OFFLINE_TOKEN="YOUR_OFFLINE_TOKEN_HERE"

# Or save in a secure file
echo "YOUR_OFFLINE_TOKEN_HERE" > ~/.rhcp-token
chmod 600 ~/.rhcp-token  # Restrict file permissions
```

**Security Warning**: Treat your offline token like a password. Never commit it to version control or share it publicly. The token provides API access to your Red Hat account data.

## Configuration

### Account Setup

Create a YAML configuration file with your account numbers and friendly names:

**accounts.yaml:**
```yaml
accounts:
  - id: "1234567"
    name: "Production Account"
  - id: "7654321"
    name: "Development Account"
  - id: "9876543"
    name: "Test Account"
```

Use the provided example as a template:
```bash
cp accounts.example.yaml accounts.yaml
# Edit with your account details
```

### Refresh Interval

The default refresh interval is 15 minutes. To change it, edit the script:

**Python version:**
```python
app = CaseMonitorTUI(accounts_file, offline_token, refresh_minutes=15)
```

**Note**: Be mindful of API rate limits. Red Hat recommends reasonable polling intervals to avoid throttling.

## Installation

### Quick Start (Automatic)

```bash
# Run the installation script
./install.sh
```

This will:
- Check Python version
- Install dependencies
- Make scripts executable
- Create example configuration

### Manual Installation

#### Python Version

1. **Download the files**

2. **Install Python dependencies**

**Important:** Use `pip`, NOT `pipx`. pipx installs in isolated environments and won't work for this script.

```bash
pip3 install rich requests PyYAML
```

3. **Make the script executable**
```bash
chmod +x rhcp-get-cases.py
```

### Installation on Managed Devices

Managed devices often restrict system-wide package installation. Use a virtual environment:

#### Manual Virtual Environment

```bash
# 1. Create virtual environment
python3 -m venv .venv

# 2. Activate it
source .venv/bin/activate

# 3. Install packages
pip install rich requests PyYAML

# 4. Run the script
python rhcp-get-cases.py accounts.yaml "$REDHAT_OFFLINE_TOKEN"

# 5. Deactivate when done
deactivate
```

## Usage

### Python Version

```bash
# Using environment variable (recommended)
export REDHAT_OFFLINE_TOKEN="your-token-here"
./rhcp-get-cases.py accounts.yaml "$REDHAT_OFFLINE_TOKEN"

# Using token file
./rhcp-get-cases.py accounts.yaml "$(cat ~/.rhcp-token)"
```

### Creating an Alias

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
export REDHAT_OFFLINE_TOKEN="your-token-here"
alias rhcases='python3 ~/path/to/rhcp-get-cases.py ~/path/to/accounts.yaml "$REDHAT_OFFLINE_TOKEN"'
```

Then simply run:
```bash
rhcases
```

### Keyboard Shortcuts

While the TUI is running:
- **Q** or **q** - Quit the application gracefully
- **Ctrl+C** - Emergency exit

## How It Works

### Authentication Flow

1. **Token Exchange**: The script exchanges your offline token for a short-lived access token (valid for ~5 minutes)
2. **API Request**: The access token is used to authenticate API requests
3. **Token Caching**: Access token is cached and reused until it expires
4. **Auto-renewal**: New tokens are obtained automatically when needed

```
Offline Token → SSO Endpoint → Access Token (cached) → API Call → Case Data
                                      ↓
                              Auto-refresh on expiry
```

### API Endpoints

- **Token endpoint**: `https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token`
- **Cases filter endpoint**: `https://api.access.redhat.com/support/v1/cases/filter`

### Case Filtering

The application filters cases using the following payload:

```json
{
  "accountNumber": "ACCOUNT_NUMBER",
  "statuses": ["Waiting on Customer", "Waiting on Red Hat"]
}
```

## Output Format

### Display Layout

```
╔═══════════════════════════════════════════════════════════╗
║              RED HAT CASES MONITOR                        ║
╚═══════════════════════════════════════════════════════════╝

Last Update: 2026-02-01 14:30:45 | Next refresh in: 234s

╔══ SUMMARY ══╗
║ Total: 12 | On RH: 5 | On Customer: 7 ║
╚═════════════╝

┌─ Production Account (1234567) - 5 case(s) ───────────────┐
│ CASE       │ SUMMARY                    │ SEVERITY │ STATUS              │
├────────────┼────────────────────────────┼──────────┼─────────────────────┤
│ 0123456    │ Critical system down       │ Urgent   │ Waiting on Red Hat  │
│ 0123457    │ Performance degradation    │ High     │ Waiting on Customer │
│ 0123458    │ Minor configuration issue  │ Low      │ Waiting on Customer │
└──────────────────────────────────────────────────────────────────────────┘

╔═══════════════════════════════════════════════════════════╗
║ Shortcuts: [Q] Quit | [Ctrl+C] Exit                      ║
╚═══════════════════════════════════════════════════════════╝
```

### Color Coding

- **Status Colors:**
  - 🔴 **Red** - Waiting on Red Hat (needs immediate attention)
  - 🟡 **Yellow** - Waiting on Customer

- **Severity Colors:**
  - **Urgent**: Bold Red
  - **High**: Red
  - **Normal**: Yellow
  - **Low**: Green

## API Reference

### Red Hat Support Case Management API

- **Documentation**: [Customer Portal Integration Guide](https://docs.redhat.com/en/documentation/red_hat_customer_portal/1/html-single/customer_portal_integration_guide)
- **API Catalog**: [Red Hat API Catalog - Case Management](https://developers.redhat.com/api-catalog/api/case-management)
- **Getting Started**: [Getting Started with Red Hat APIs](https://access.redhat.com/articles/3626371)

### Common API Operations

**Filter cases by status:**
```bash
curl -X POST \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"accountNumber": "123456", "statuses": ["Waiting on Customer"]}' \
  https://api.access.redhat.com/support/v1/cases/filter
```

**Get specific case:**
```bash
curl -H "Authorization: Bearer $ACCESS_TOKEN" \
  https://api.access.redhat.com/support/v1/cases/{case_number}
```

### Case Status Values

Common Red Hat support case statuses:
- `Waiting on Customer` - Red Hat needs information from you
- `Waiting on Red Hat` - Case is being worked on by Red Hat
- `Closed` - Case has been resolved
- `Closed with Notification` - Case closed with automated notification

## Security Best Practices

### Token Management
- **Never hardcode tokens** in scripts or version control
- **Use environment variables** for storing tokens (recommended)
- **Restrict file permissions**: `chmod 600` for token files
- **Rotate tokens periodically** via the Red Hat portal
- **Monitor token usage** for suspicious activity

```bash
# Good: Using environment variable
export REDHAT_OFFLINE_TOKEN="token"
./rhcp-get-cases.py accounts.yaml "$REDHAT_OFFLINE_TOKEN"

# Good: Using secure file
chmod 600 ~/.rhcp-token
./rhcp-get-cases.py accounts.yaml "$(cat ~/.rhcp-token)"

# Bad: Hardcoded in script or command history
./rhcp-get-cases.py accounts.yaml "eyJh..." # DON'T DO THIS
```

### Configuration Security
- Restrict permissions on `accounts.yaml` if it contains sensitive data
- Use `.gitignore` to exclude token files and sensitive configs
- Consider encrypting configuration files with sensitive data

### Script Security
- Scripts use HTTPS for all API communications
- Tokens are passed in HTTP headers, not URLs
- Terminal settings are properly restored on exit
- Error messages don't expose token data

### Network Security
- All API communications use TLS/HTTPS
- No sensitive data logged to disk by default
- Consider running on secure, trusted networks

## Troubleshooting

### Authentication Errors

**"Failed to obtain access token"**
- Verify your offline token is valid and not expired
- Check token format (should start with `eyJh...`)
- Regenerate token at the Red Hat portal if needed
- Ensure no extra whitespace or newlines in token

```bash
# Test your token
curl -s -X POST \
  "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=$REDHAT_OFFLINE_TOKEN" \
  -d "client_id=rhsm-api" | jq .
```

### Python Dependency Errors

**"ModuleNotFoundError: No module named 'rich'"**

Cause: You installed packages with `pipx` instead of `pip`, or you're on a managed device.

Solutions:
```bash
# Solution 1: Use regular pip (not pipx)
pip3 install rich requests PyYAML

# Solution 2: Use virtual environment (managed devices)
python3 -m venv .venv
source .venv/bin/activate
pip install rich requests PyYAML
```

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed solutions.

### API Errors

**403 Forbidden**
- Verify account permissions
- Check that your user has API access enabled
- Ensure account numbers in `accounts.yaml` are correct
- Confirm you have access to the specified accounts

**429 Too Many Requests**
- Increase refresh interval (reduce polling frequency)
- Default is 15 minutes; consider increasing to 30 minutes
- Check Red Hat's rate limiting policies

**Empty tables but cases count > 0**
- This was a bug in v1.0, fixed in v1.1
- Update to the latest version
- If still occurring, run diagnostic: `python3 diagnostic.py accounts.yaml TOKEN`

### Display Issues

**Cases disappear when resizing terminal**
- This was a bug in v1.0, fixed in v1.1
- Update to the latest version
- Ensure you're using fixed-width columns version

**Terminal looks garbled or broken**
- Ensure terminal supports UTF-8 encoding
- Use a modern terminal emulator (iTerm2, Alacritty, Windows Terminal)
- Increase terminal window size (minimum 80x24 recommended)
- Try running: `reset` to reset terminal state

**Colors not working**
- Check if terminal supports colors: `tput colors`
- Should return 8 or 256
- Update terminal emulator if needed

### Script Errors

**"Permission denied"**
```bash
chmod +x rhcp-get-cases.py
```

## Contributing

We welcome contributions! Here's how you can help:

### Reporting Issues
- Check existing issues before creating new ones
- Include version number, OS, and error messages
- Provide steps to reproduce problems
- Run diagnostic tools and include output

### Submitting Changes
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Make your changes
4. Test thoroughly with your Red Hat account
5. Commit with clear messages
6. Submit a pull request

### Testing Your Changes
- Test with multiple accounts if possible
- Verify error handling works correctly
- Check terminal resize behavior
- Test keyboard shortcuts
- Ensure backward compatibility
- Test on different terminal emulators

### Code Style
- **Python**: Follow PEP 8 guidelines
- **Bash**: Use ShellCheck for linting
- Add comments for complex logic
- Update documentation for new features

## Extending the Application

### Adding New Keyboard Shortcuts

Modify `check_keyboard_input()` in Python version:
```python
def check_keyboard_input(self):
    # ... existing code ...
    if char.lower() == 'r':
        self.fetch_all_cases()  # Manual refresh
    elif char.lower() == 'h':
        self.show_help()  # Show help screen
```

### Filtering by Severity

Modify the API payload:
```python
payload = {
    "accountNumber": account_number,
    "statuses": ["Waiting on Customer", "Waiting on Red Hat"],
    "severity": "High"  # Add severity filter
}
```

### Adding Notifications

Example email notification on status change:
```python
if new_waiting_on_rh > old_waiting_on_rh:
    import smtplib
    # Send email alert
```

### Custom Status Colors

Edit the color mapping in `create_account_table()`:
```python
severity_style = {
    "Urgent": "bold magenta",  # Change colors
    "High": "red",
    "Normal": "yellow",
    "Low": "cyan"
}.get(case.severity, "white")
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Resources

### Red Hat Documentation
- [Getting Started with Red Hat APIs](https://access.redhat.com/articles/3626371)
- [Customer Portal Integration Guide](https://docs.redhat.com/en/documentation/red_hat_customer_portal/1/html-single/customer_portal_integration_guide)
- [Subscription Management API Documentation](https://docs.redhat.com/en/documentation/subscription_central/1-latest/html-single/using_apis_in_red_hat_subscription_management)
- [API Tokens Management](https://access.redhat.com/management/api)

### Related Tools & Libraries
- [Rich - Python TUI Framework](https://github.com/Textualize/rich)
- [jq - JSON Processor](https://stedolan.github.io/jq/)
- [ShellCheck - Shell Script Analysis](https://www.shellcheck.net/)
- [Python Requests Documentation](https://requests.readthedocs.io/)

### Support
This tool is not officially supported by Red Hat, but you can:
- Open GitHub issues for bugs or feature requests
- Contact Red Hat support for API-related issues
- Visit Red Hat Customer Portal: https://access.redhat.com

## Changelog

### Version 1.2 (Current)
- Added keyboard shortcut support (press 'Q' to quit)
- Added footer bar with shortcuts display
- Improved user experience with graceful shutdown

### Version 1.1
- Fixed terminal resize bug causing cases to disappear
- Fixed missing cases in detail tables
- Added explicit column widths for consistent display
- Improved table rendering performance
- Added case count to table titles

### Version 1.0
- Initial release
- Multi-account support
- Auto-refresh functionality
- Color-coded status display
- Python and Bash implementations
- OAuth 2.0 token management

## Acknowledgments

- Red Hat for providing comprehensive API documentation and developer resources
- The Textualize team for the excellent Rich library
- The open-source community for shell scripting best practices and tools

---

**Note**: This is an unofficial tool created for convenience and is not officially supported by Red Hat. For official support tools and comprehensive case management, visit the [Red Hat Customer Portal](https://access.redhat.com).

**For detailed documentation:**
- [Managed Devices Guide](MANAGED_DEVICES.md)
- [Troubleshooting Guide](TROUBLESHOOTING.md)
- [Version Comparison](COMPARISON.md)
- [Bug Fixes Log](BUGFIXES.md)