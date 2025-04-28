from typing import Dict, Optional

# Dummy data for organizations
ORGANIZATIONS = {
    "rf-test": {"id": 1, "name": "RF-Test Organization"},
    "acme-corp": {"id": 2, "name": "ACME Corporation"},
    "tech-solutions": {"id": 3, "name": "Tech Solutions Ltd"}
}

# Dummy data for advisers
ADVISERS = {
    "john.doe@example.com": {"id": 101, "name": "John Doe", "email": "john.doe@example.com"},
    "jane.smith@example.com": {"id": 102, "name": "Jane Smith", "email": "jane.smith@example.com"},
    "bob.wilson@example.com": {"id": 103, "name": "Bob Wilson", "email": "bob.wilson@example.com"},
    "bob.wilson2@example.com": {"id": 104, "name": "Bob Wilson", "email": "bob.wilson2@example.com"}
}

# Dummy data for clients
CLIENTS = {
    "alice.johnson@example.com": {"id": 201, "name": "Alice Johnson", "email": "alice.johnson@example.com"},
    "charlie.brown@example.com": {"id": 202, "name": "Charlie Brown", "email": "charlie.brown@example.com"},
    "diana.ross@example.com": {"id": 203, "name": "Diana Ross", "email": "diana.ross@example.com"}
}

def get_organisation_id_by_name(org_name: str) -> Optional[int]:
    """Get organization ID by name."""
    org_name = org_name.lower()
    for key, org in ORGANIZATIONS.items():
        if key in org_name or org["name"].lower() in org_name:
            return org["id"]
    return None

def get_adviser_id_by_name(adviser_name: str) -> Optional[int]:
    """Get adviser ID by name."""
    adviser_name = adviser_name.lower()
    for adviser in ADVISERS.values():
        if adviser_name in adviser["name"].lower():
            return adviser["id"]
    return None

def get_adviser_id_by_email(email: str) -> Optional[int]:
    """Get adviser ID by email."""
    email = email.lower()
    if email in ADVISERS:
        return ADVISERS[email]["id"]
    return None

def get_client_id_by_name(client_name: str) -> Optional[int]:
    """Get client ID by name."""
    client_name = client_name.lower()
    for client in CLIENTS.values():
        if client_name in client["name"].lower():
            return client["id"]
    return None

def get_client_id_by_email(email: str) -> Optional[int]:
    """Get client ID by email."""
    email = email.lower()
    if email in CLIENTS:
        return CLIENTS[email]["id"]
    return None 