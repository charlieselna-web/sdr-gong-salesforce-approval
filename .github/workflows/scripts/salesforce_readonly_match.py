import argparse
import json
import os
import sys

from simple_salesforce import (
    Salesforce,
    SalesforceAuthenticationFailed,
    SalesforceMalformedRequest,
    format_soql,
)


def required_env(name):
    value = os.getenv(name)

    if not value:
        print(f"Missing required environment variable: {name}")
        sys.exit(1)

    return value


def clean_record(value):
    if isinstance(value, dict):
        return {
            key: clean_record(child)
            for key, child in value.items()
            if key != "attributes"
        }

    if isinstance(value, list):
        return [clean_record(item) for item in value]

    return value


def run_query(sf, label, soql):
    print("")
    print("=" * 80)
    print(label)
    print("=" * 80)
    print(soql)

    try:
        result = sf.query_all(soql)
    except SalesforceMalformedRequest as error:
        print(f"Salesforce query failed for: {label}")
        print(error.content)
        sys.exit(1)

    records = result.get("records", [])
    cleaned = clean_record(records)

    print("")
    print(f"Found {len(cleaned)} record(s).")
    print(json.dumps(cleaned, indent=2, sort_keys=True))

    return cleaned


def soql_literal(value):
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prospect-email", required=True)
    parser.add_argument("--company-domain", required=True)
    parser.add_argument("--account-name", required=False, default="")

    args = parser.parse_args()

    username = required_env("SALESFORCE_USERNAME")
    password = required_env("SALESFORCE_PASSWORD")
    security_token = required_env("SALESFORCE_SECURITY_TOKEN")
    domain = os.getenv("SALESFORCE_DOMAIN", "test")

    prospect_email = args.prospect_email.strip().lower()
    company_domain = args.company_domain.strip().lower()
    account_name = args.account_name.strip()

    print("Starting Salesforce read-only matching.")
    print("Mode: READ ONLY")
    print(f"Salesforce domain: {domain}")
    print(f"Prospect email: {prospect_email}")
    print(f"Company domain: {company_domain}")
    print(f"Account name: {account_name or '(none provided)'}")

    try:
        sf = Salesforce(
            username=username,
            password=password,
            security_token=security_token,
            domain=domain,
        )
    except SalesforceAuthenticationFailed as error:
        print("Salesforce authentication failed.")
        print("Check SALESFORCE_USERNAME, SALESFORCE_PASSWORD, SALESFORCE_SECURITY_TOKEN, and SALESFORCE_DOMAIN.")
        print(error)
        sys.exit(1)

    print("Salesforce authentication succeeded.")

    contacts = run_query(
        sf,
        "CONTACT MATCHES BY EMAIL",
        format_soql(
            """
            SELECT Id, Name, FirstName, LastName, Email, AccountId, Account.Name, Owner.Name
            FROM Contact
            WHERE Email = {}
            LIMIT 10
            """,
            prospect_email,
        ),
    )

    leads = run_query(
        sf,
        "LEAD MATCHES BY EMAIL",
        format_soql(
            """
            SELECT Id, Name, Company, Email, Status, IsConverted, Owner.Name
            FROM Lead
            WHERE Email = {}
            AND IsConverted = false
            LIMIT 10
            """,
            prospect_email,
        ),
    )

    account_queries = []

    if company_domain:
        account_queries.append(
            format_soql(
                """
                SELECT Id, Name, Website, Owner.Name
                FROM Account
                WHERE Website LIKE {}
                LIMIT 20
                """,
                f"%{company_domain}%",
            )
        )

    if account_name:
        account_queries.append(
            format_soql(
                """
                SELECT Id, Name, Website, Owner.Name
                FROM Account
                WHERE Name LIKE {}
                LIMIT 20
                """,
                f"%{account_name}%",
            )
        )

    accounts_by_id = {}

    for index, query in enumerate(account_queries, start=1):
        accounts = run_query(
            sf,
            f"ACCOUNT MATCHES #{index}",
            query,
        )

        for account in accounts:
            accounts_by_id[account["Id"]] = account

    account_ids = set(accounts_by_id.keys())

    for contact in contacts:
        account_id = contact.get("AccountId")
        if account_id:
            account_ids.add(account_id)

    opportunities = []

    if account_ids:
        account_id_list = ", ".join(
            soql_literal(account_id) for account_id in sorted(account_ids)
        )

        opportunities = run_query(
            sf,
            "OPEN S0 OPPORTUNITY MATCHES",
            f"""
            SELECT Id, Name, AccountId, Account.Name, StageName, IsClosed, Owner.Name, CreatedDate
            FROM Opportunity
            WHERE AccountId IN ({account_id_list})
            AND IsClosed = false
            AND StageName = 'S0'
            ORDER BY CreatedDate DESC
            LIMIT 20
            """,
        )
    else:
        print("")
        print("=" * 80)
        print("OPEN S0 OPPORTUNITY MATCHES")
        print("=" * 80)
        print("Skipped because no Account IDs were found.")

    print("")
    print("=" * 80)
    print("MATCH SUMMARY")
    print("=" * 80)
    print(f"Contacts found: {len(contacts)}")
    print(f"Leads found: {len(leads)}")
    print(f"Accounts found: {len(accounts_by_id)}")
    print(f"Open S0 Opportunities found: {len(opportunities)}")

    if len(opportunities) == 1:
        print("")
        print("Recommended match:")
        print(f"Opportunity: {opportunities[0].get('Name')} / {opportunities[0].get('Id')}")
        print(f"Account: {opportunities[0].get('Account', {}).get('Name')} / {opportunities[0].get('AccountId')}")
    elif len(opportunities) > 1:
        print("")
        print("Multiple open S0 Opportunities found. Human approval should choose the correct one.")
    elif contacts or leads or accounts_by_id:
        print("")
        print("Salesforce records were found, but no open S0 Opportunity was found.")
    else:
        print("")
        print("No strong Salesforce match found.")

    print("")
    print("READ ONLY COMPLETE. No Salesforce records were created or updated.")


if __name__ == "__main__":
    main()
