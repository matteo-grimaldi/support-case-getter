# Red Hat Support Cases Monitoring Script

A Zsh script for continuously monitoring Red Hat support case status across multiple accounts using the Red Hat Customer Portal API.

## Overview

This script retrieves and displays real-time support case data for multiple Red Hat accounts, filtering by case status ("Waiting on Customer" or "Waiting on Red Hat"). It uses OAuth 2.0 authentication via Red Hat's Single Sign-On service and continuously polls the Case Management API.

## Features

- **Multi-account monitoring**: Track cases across multiple Red Hat customer accounts
- **Status filtering**: Focus on active cases waiting for customer or Red Hat response
- **Continuous polling**: Auto-refresh case data at configurable intervals
- **OAuth 2.0 authentication**: Secure token-based authentication using offline tokens
- **Account labeling**: Assign friendly names to account numbers for easy identification

## Prerequisites

### Required Tools
- `zsh` (Z shell)
- `curl` - for API requests
- `jq` - JSON processor for parsing API responses
- `grep` and `cut` - for token extraction

Install dependencies on common systems:
```bash
# Ubuntu/Debian
sudo apt-get install zsh curl jq

# RHEL/CentOS/Fedora
sudo dnf install zsh curl jq

# macOS (with Homebrew)
brew install zsh curl jq
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
5. Store it securely in a file (e.g., `rhcp-token`)

```bash
# Save your token securely
echo "YOUR_OFFLINE_TOKEN_HERE" > rhcp-token
chmod 600 rhcp-token  # Restrict file permissions
```

**Security Warning**: Treat your offline token like a password. Never commit it to version control or share it publicly. The token provides API access to your Red Hat account data.

## Configuration

### Account Setup

Edit the `ACCOUNTS` array in the script to include your account numbers and friendly names:

```zsh
ACCOUNTS=(
  "1234566" "Account A"
  "1234566" "Account B"
  "1234566" "Account C"
  # Add more accounts as needed
)
```

The array format is: `"account_number" "friendly_name"`

### Polling Interval

Adjust the refresh rate by modifying the `DELAY` variable:

```zsh
DELAY=5  # Seconds between API calls
```

**Note**: Be mindful of API rate limits. Red Hat recommends reasonable polling intervals to avoid throttling.

## Usage

### Basic Execution

```bash
# Using a token file
./rhcp-get-cases.sh "$(cat rhcp-token)"

# Or pass token directly
./rhcp-get-cases.sh "YOUR_OFFLINE_TOKEN"
```

### Making the Script Executable

```bash
chmod +x rhcp-get-cases.sh
```

## How It Works

### Authentication Flow

1. **Token Exchange**: The script exchanges your offline token for a short-lived access token (valid for ~15 minutes)
2. **API Request**: The access token is used to authenticate API requests
3. **Auto-renewal**: The process repeats on each polling cycle

```
Offline Token → SSO Endpoint → Access Token → API Call → Case Data
```

### API Endpoints

- **Token endpoint**: `https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token`
- **Cases filter endpoint**: `https://api.access.redhat.com/support/v1/cases/filter`

### Case Filtering

The script filters cases using the following payload:

```json
{
  "accountNumber": "ACCOUNT_NUMBER",
  "statuses": ["Waiting on Customer", "Waiting on Red Hat"]
}
```

## Output Format

The script displays:
- Timestamp of data retrieval
- Account information (name and number)
- Raw API response containing case details

Example output:
```
[2025-01-21 10:30:45] Starting case data retrieval...

--- Fetching data for Account: Account A (6472242) ---

--Response {"cases": [...], "count": 5}--
```

## API Reference

### Red Hat Support Case Management API

- **Documentation**: [Customer Portal Integration Guide](https://docs.redhat.com/en/documentation/red_hat_customer_portal/1/html-single/customer_portal_integration_guide)
- **Swagger Spec**: Available at [Red Hat API Catalog](https://developers.redhat.com/api-catalog/api/case-management)

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
- **Use environment variables** or secure token files
- **Restrict file permissions**: `chmod 600 rhcp-token`
- **Rotate tokens periodically** via the Red Hat portal
- **Monitor token usage** for suspicious activity

### Script Security
- Review the script before running with production tokens
- Use `set -euo pipefail` for safer error handling (consider adding to script)
- Validate all user inputs if accepting parameters
- Log to secure locations if implementing logging

### Network Security
- Script uses HTTPS for all API communications
- Tokens are passed in HTTP headers, not URLs
- Consider running on secure, trusted networks

## Troubleshooting

### Authentication Errors

**Error: "Failed to obtain access token"**
- Verify your offline token is valid
- Check token hasn't expired (regenerate at Red Hat portal)
- Ensure proper formatting (no extra whitespace)

### API Errors

**403 Forbidden**
- Verify account permissions
- Check that your user has API access enabled
- Ensure account numbers are correct

**429 Too Many Requests**
- Reduce polling frequency (increase `DELAY`)
- Check Red Hat's rate limiting policies

### Script Errors

**Command not found: jq**
```bash
# Install jq
sudo apt-get install jq  # Debian/Ubuntu
sudo dnf install jq      # RHEL/Fedora
brew install jq          # macOS
```

**Permission denied**
```bash
chmod +x rhcp-get-cases.sh
```

## Contributing

We welcome contributions! Here's how you can help:

### Reporting Issues
- Check existing issues before creating new ones
- Include script version, OS, and error messages
- Provide steps to reproduce problems

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
- Check for proper token refresh behavior
- Ensure backward compatibility

## Extending the Script

### Adding Response Parsing

Parse specific fields from API response:
```zsh
CASES=$(echo "$RESPONSE" | jq -r '.cases[] | "\(.caseNumber) - \(.summary)"')
echo "$CASES"
```

### Adding Notifications

Send alerts when cases change:
```zsh
# Example using mail command
if [[ $NEW_CASES -gt 0 ]]; then
  echo "New cases detected" | mail -s "Red Hat Cases Alert" user@example.com
fi
```

### Filtering by Severity

Modify the payload to filter by case severity:
```zsh
PAYLOAD=$(jq -n \
  --arg acc "$ACC_NUM" \
  '{accountNumber: $acc, severity: "High", statuses: ["Waiting on Red Hat"]}')
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Resources

### Red Hat Documentation
- [Getting Started with Red Hat APIs](https://access.redhat.com/articles/3626371)
- [Customer Portal Integration Guide](https://docs.redhat.com/en/documentation/red_hat_customer_portal/1/html-single/customer_portal_integration_guide)
- [Subscription Management API Documentation](https://docs.redhat.com/en/documentation/subscription_central/1-latest/html-single/using_apis_in_red_hat_subscription_management)

### Related Tools
- [jq Tutorial](https://stedolan.github.io/jq/tutorial/)
- [ShellCheck - Shell Script Analysis](https://www.shellcheck.net/)
- [Curl Documentation](https://curl.se/docs/)

### Support
This tool is not supported per se, but you can get help in case of issues with used Red Hat APIs
- Red Hat Customer Portal: https://access.redhat.com
- Open a support case if you encounter API issues

## Changelog

### Version 1.0.0
- Initial release
- Multi-account support
- Continuous polling
- Status filtering (Waiting on Customer, Waiting on Red Hat)

## Acknowledgments

- Red Hat for providing comprehensive API documentation
- The open-source community for shell scripting best practices

---

**Note**: This is an unofficial tool and is not supported by Red Hat. For official support tools, visit the Red Hat Customer Portal.