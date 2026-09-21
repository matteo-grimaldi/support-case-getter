# Cursor Integration Guide: Red Hat GraphQL API for Support Case Management

This document serves as an actionable integration spec for AI coding assistants (like Cursor) to implement a client module for the Red Hat GraphQL Support Case Management API.

---

## 1. Executive Summary & Configuration Specs

### Endpoint & Authentication Details
- **GraphQL Endpoint:** `https://graphql.redhat.com`
- **HTTP Method:** `POST`
- **Content Type:** `application/json`
- **Authentication:** OAuth2 SSO Bearer Token (`Authorization: Bearer <ACCESS_TOKEN>`)
- **Required Client Headers:**
  - `Content-Type: application/json`
  - `Authorization: Bearer <ACCESS_TOKEN>`
  - `apollographql-client-name: <client-app-name>`
  - `apollographql-client-version: <client-version>`

### Key API Conventions
1. **Value Wrapper Pattern:** Notice that almost all field values in Red Hat GraphQL responses are returned inside a nested `{ value }` wrapper object (e.g., `CaseNumber__c { value }`). Input/filtering queries often require passing values wrapped similarly or using strict ISO-8601 strings.
2. **Cursor-Based Pagination:** Uses standard Relay-style pagination (`first`, `after`, `edges { node, cursor }`, `pageInfo { hasNextPage, endCursor }`). Maximum recommended `first` batch size is **200**.
3. **Filtering Syntax:** Filtering requires typed operators (`eq`, `ne`, `like`, `in`, `nin`, `gt`, `gte`, `lt`, `lte`) and boolean compositions (`and`, `or`, `not`).

---

## 2. Best Practices & Key Considerations for Implementation

- **Data Fetching Errors:** Handled in the top-level `errors` array in GraphQL responses. Watch out for:
  - `DataFetchingException`: Permission issue or unauthorized scope.
  - `VALIDATION_INVALID_TYPE_VARIABLE`: Data structure mismatch in variables (e.g., missing `{ "value": ... }` wrapping or invalid date formatting).
- **Date Formatting:** Datetime values in filter arguments require ISO-8601 UTC strings formatted like:
  ```json
  "CreatedDate": { "gt": { "value": "2026-01-01T00:00:00Z" } }
  ```
- **Composite ID Lookups:** Before creating a support case, run `ResolveCaseLookupData` to obtain required internal Object IDs (`AccountId`, `ContactId`, `ProductId`, `RecordTypeId`).

---

## 3. Operations & GraphQL Queries

### 3.1. Authentication & Test Request
#### Example cURL
```bash
curl --request POST \
  --header 'content-type: application/json' \
  --header 'Authorization: Bearer <ACCESS_TOKEN>' \
  --header 'apollographql-client-name: my-amazing-graphql-client' \
  --header 'apollographql-client-version: 1.0.0' \
  --url 'https://graphql.redhat.com' \
  --data '{"query": "query NewestCases($count: Int) { redhat_support_uiapi { query { RedHatSupportCase(first: $count, orderBy: {CreatedDate: {order: DESC}}) { edges { node { Id CaseNumber__c { value } CreatedDate { value } } } } } } }", "variables": {"count": 1}}'
```

---

### 3.2. Account & Contact Operations

#### Get Contact and Account Info by SSO Username
```graphql
query GetContactAndAccount($ssoUsername: String) {
  redhat_support_uiapi {
    query {
      RedHatSupportContact(where: { SSOUserName__c: { eq: $ssoUsername } }) {
        edges {
          node {
            Id
            Name { value }
            Email { value }
            Phone { value }
            SSOUserName__c { value }
            RedHatSupportAccount {
              Id
              Name { value }
              AccountNumber { value }
            }
          }
        }
      }
    }
  }
}
```
*Variables Example:*
```json
{
  "ssoUsername": "john_doe_customer"
}
```

#### Get Account by Enterprise Account Number
```graphql
query GetAccountByNumber($accountNumber: String) {
  redhat_support_uiapi {
    query {
      RedHatSupportAccount(where: { AccountNumber: { eq: $accountNumber } }) {
        edges {
          node {
            Id
            Name { value }
            AccountNumber { value }
          }
        }
      }
    }
  }
}
```
*Variables Example:*
```json
{
  "accountNumber": "8675309"
}
```

#### Get Contacts for an Account (Paginated)
```graphql
query GetContactsForAccount($accountNumber: String, $first: Int = 200, $after: String) {
  redhat_support_uiapi {
    query {
      RedHatSupportContact(
        where: { RedHatSupportAccount: { AccountNumber: { eq: $accountNumber } } }
        first: $first
        after: $after
      ) {
        totalCount
        edges {
          cursor
          node {
            Id
            Name { value }
            Email { value }
            Phone { value }
            SSOUserName__c { value }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
```
*Variables Example:*
```json
{
  "accountNumber": "8675309",
  "first": 200,
  "after": null
}
```

---

### 3.3. Products & Business Hours

#### Get Active Products (Paginated)
```graphql
query GetActiveProducts($first: Int = 200, $after: String) {
  redhat_support_uiapi {
    query {
      RedHatSupportProduct2(
        where: { IsActive: { eq: true } }
        orderBy: { Name: { order: DESC } }
        first: $first
        after: $after
      ) {
        totalCount
        edges {
          cursor
          node {
            Id
            Name { value }
            VersionName__c { value }
            Family { value }
            ParentProduct__c { value }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
```

#### Get Support Business Hours
```graphql
query GetBusinessHours($first: Int = 200) {
  redhat_support_uiapi {
    query {
      RedHatSupportBusinessHours(
        first: $first
        where: { IsActive: { eq: true } }
      ) {
        totalCount
        edges {
          node {
            Id
            Name { value }
            TimeZoneSidKey { value }
          }
        }
      }
    }
  }
}
```

---

### 3.4. Case Management Operations

#### Fetch Default Support Cases List
```graphql
query GetSupportCases($first: Int = 200, $after: String) {
  redhat_support_uiapi {
    query {
      RedHatSupportCase(
        first: $first
        after: $after
        orderBy: { CaseNumber__c: { order: DESC } }
        where: {
          and: [
            { RedHatSupportRecordType: { Name: { eq: "Technical Support" } } }
            { AccessRestrictions__c: { eq: "None" } }
          ]
        }
      ) {
        edges {
          cursor
          node {
            Id
            CaseNumber__c { value }
            Subject { value }
            Status { value }
            Priority { value }
            CreatedDate { value }
            LastModifiedDate { value }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
```

#### Get Cases by Dynamic Filters
```graphql
query GetCasesByFilters($where: RedHatSupportCase_Filter, $first: Int = 100, $after: String) {
  redhat_support_uiapi {
    query {
      RedHatSupportCase(
        where: $where
        first: $first
        after: $after
        orderBy: { LastModifiedDate: { order: DESC } }
      ) {
        edges {
          cursor
          node {
            Id
            CaseNumber__c { value }
            Subject { value }
            Status { value }
            Priority { value }
            CreatedDate { value }
            LastModifiedDate { value }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
```
*Variables Example:*
```json
{
  "first": 100,
  "after": null,
  "where": {
    "Status": { "ne": "Closed" },
    "Priority": { "in": ["1 (Urgent)", "2 (High)"] },
    "CreatedDate": {
      "gt": {
        "value": "2026-01-01T00:00:00Z"
      }
    }
  }
}
```

#### Get Full Case Details with Comments
```graphql
query GetCaseAndComments($caseNumber: String, $first: Int = 200, $after: String) {
  redhat_support_uiapi {
    query {
      RedHatSupportCase(where: { CaseNumber__c: { eq: $caseNumber } }) {
        edges {
          node {
            Id
            CaseNumber__c { value }
            Subject { value }
            Status { value }
            Priority { value }
            Type { value }
            Product {
              Id
              Name { value }
              ParentProduct__r {
                Id
                Name { value }
              }
            }
            RedHatSupportAccount {
              Id
              Name { value }
              AccountNumber { value }
            }
            RedHatSupportContact {
              Id
              Name { value }
              Email { value }
              Phone { value }
              SSOUserName__c { value }
            }
            Owner {
              ... on RedHatSupportGroup {
                Id
                Name { value }
              }
              ... on RedHatSupportUser {
                Id
                Name { value }
              }
            }
            CreatedDate { value }
            LastModifiedDate { value }
            LastModifiedBy {
              Name { value }
            }
            CaseComments__r(
              first: $first
              after: $after
              orderBy: { CreatedDate: { order: DESC } }
            ) {
              edges {
                cursor
                node {
                  Id
                  Body__c { value }
                  LastModifiedByName__c { value }
                  IsAssociate__c { value }
                  IsCustomer__c { value }
                  CreatedDate { value }
                }
              }
              pageInfo {
                hasNextPage
                endCursor
              }
            }
          }
        }
      }
    }
  }
}
```

---

### 3.5. Case Creation & Pre-requisite Resolution

#### Pre-requisite Lookup Query (`ResolveCaseLookupData`)
Use this composite query before calling `CreateNewCase` to resolve requisite system Object IDs:
```graphql
query ResolveCaseLookupData(
  $ssoUser: String
  $accountNumber: String
  $productName: String
  $versionName: String
) {
  redhat_support_uiapi {
    # 1. Resolve Contact ID & Account ID by SSO Username
    Contact: query {
      RedHatSupportContact(where: { SSOUserName__c: { eq: $ssoUser } }, first: 1) {
        edges {
          node {
            Id
            AccountId { value }
          }
        }
      }
    }
    # 2. Resolve Account ID by Account Number
    Account: query {
      RedHatSupportAccount(where: { AccountNumber: { eq: $accountNumber } }, first: 1) {
        edges {
          node {
            Id
          }
        }
      }
    }
    # 3. Resolve RecordType ID by Developer Name
    RecordType: query {
      RedHatSupportRecordType(
        where: { SobjectType: { eq: "Case" }, DeveloperName: { eq: "Technical_Support" } }
        first: 1
      ) {
        edges {
          node {
            Id
          }
        }
      }
    }
    # 4. Resolve Product ID by Product Name & Version
    Product: query {
      RedHatSupportProduct2(
        where: {
          and: [
            { Name: { eq: $productName } }
            { VersionName__c: { eq: $versionName } }
          ]
        }
        first: 1
      ) {
        edges {
          node {
            Id
            Name { value }
            VersionName__c { value }
          }
        }
      }
    }
  }
}
```

#### Create New Support Case Mutation
```graphql
mutation CreateNewCase($input: RedHatSupportCaseCreateInput!) {
  redhat_support_uiapi {
    CaseCreate(input: $input) {
      RedHatSupportRecord {
        Id
        CaseNumber__c { value }
        Subject { value }
        Status { value }
        CreatedDate { value }
      }
    }
  }
}
```
*Variables Example:*
```json
{
  "input": {
    "RedHatSupportCase": {
      "Subject": "Application Crash on JBoss EAP Startup",
      "Description": "Detailed stack trace and logs attached. Issue occurs consistently after server reboot.",
      "Priority": "2 (High)",
      "ProductId": "<Product_Id>",
      "AccountId": "<Account_Id>",
      "Status": "In Progress",
      "Origin": "Web",
      "RecordTypeId": "<RecordType_Id>",
      "Language": "en_US",
      "ContactId": "<Contact_Id>"
    }
  }
}
```

#### Update Case Mutation
```graphql
mutation UpdateCase($input: RedHatSupportCaseUpdateInput!) {
  redhat_support_uiapi {
    CaseUpdate(input: $input) {
      RedHatSupportRecord {
        Id
        CaseNumber__c { value }
        Status { value }
        Priority { value }
        LastModifiedDate { value }
      }
    }
  }
}
```
*Variables Example:*
```json
{
  "input": {
    "Id": "500Yr90875yetsEIAQ",
    "RedHatSupportCase": {
      "Status": "Closed"
    }
  }
}
```

---

### 3.6. Case Comment Operations

#### Get Single Case Comment by ID
```graphql
query GetCaseComment($commentId: ID!) {
  redhat_support_uiapi {
    query {
      RedHatSupportCaseComment__c(where: { Id: { eq: $commentId } }) {
        edges {
          node {
            Id
            Body__c { value }
            Case__c { value }
            LastModifiedByName__c { value }
            IsAssociate__c { value }
            IsCustomer__c { value }
            CreatedDate { value }
          }
        }
      }
    }
  }
}
```

#### Create Case Comment Mutation
```graphql
mutation CreateCaseComment($input: RedHatSupportCaseComment__cCreateInput!) {
  redhat_support_uiapi {
    CaseComment__cCreate(input: $input) {
      RedHatSupportRecord {
        Id
        Body__c { value }
        Case__c { value }
        CreatedDate { value }
      }
    }
  }
}
```
*Variables Example:*
```json
{
  "input": {
    "RedHatSupportCaseComment__c": {
      "Case__c": "500Yr90875yetsEIAQ",
      "Body__c": "Updated logs have been applied to the system. Requesting further review.",
      "Visibility__c": "Public"
    }
  }
}
```

---

## 4. Cursor Implementation Instructions

When instructing Cursor to build client code against this API spec:
1. **API Client Layer:** Implement an HTTP client targeting `https://graphql.redhat.com` with mandatory headers (`Authorization`, `Content-Type`, `apollographql-client-name`, `apollographql-client-version`).
2. **Type Generation:** Parse the GraphQL definitions into TypeScript types / Pydantic models / Interfaces matching both inputs (`RedHatSupportCaseCreateInput`, `RedHatSupportCaseComment__cCreateInput`, etc.) and outputs.
3. **Value Unwrapper Utility:** Create a helper function to automatically unwrap standard Red Hat `{ value }` payload structures into clean domain objects (e.g., converting `{ CaseNumber__c: { value: "0123" } }` -> `{ caseNumber: "0123" }`).
4. **Pagination Helper:** Implement an auto-paginating wrapper around edge/cursor fields using standard cursor iterations up to `hasNextPage == false`.
