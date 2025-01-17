import os
import requests
from msal import PublicClientApplication, SerializableTokenCache
from dotenv import load_dotenv
load_dotenv()

# Configuration
CLIENT_ID = os.getenv('CLIENT_ID') 
ACCOUNT_EMAIL = os.getenv('ACCOUNT_EMAIL')    
AUTHORITY = 'https://login.microsoftonline.com/common'
SCOPES = ['Mail.Read']
TOKEN_CACHE_FILE = 'token_cache.json'

def load_token_cache():
    cache = SerializableTokenCache()
    if os.path.exists(TOKEN_CACHE_FILE):
        with open(TOKEN_CACHE_FILE, 'r') as f:
            cache.deserialize(f.read())
    return cache

def save_token_cache(cache):
    if cache.has_state_changed:
        with open(TOKEN_CACHE_FILE, 'w') as f:
            f.write(cache.serialize())

def get_access_token():
    cache = load_token_cache()
    app = PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
        token_cache=cache
    )

    # Attempt to acquire token silently
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and 'access_token' in result:
            save_token_cache(cache)
            return result['access_token']

    # If silent acquisition fails, initiate device code flow
    flow = app.initiate_device_flow(scopes=SCOPES)
    if 'user_code' not in flow:
        raise Exception(f"Device flow initiation failed: {flow.get('error')}")

    print(flow['message'])  # Prompt user to authenticate
    result = app.acquire_token_by_device_flow(flow)

    if 'access_token' in result:
        save_token_cache(cache)
        return result['access_token']
    else:
        raise Exception(f"Failed to get access token: {result.get('error_description')}")

def fetch_emails():
    try:
        access_token = get_access_token()
        headers = {'Authorization': f'Bearer {access_token}'}
        endpoint = 'https://graph.microsoft.com/v1.0/me/messages?$top=10&$orderby=receivedDateTime desc'

        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            emails = response.json()
            for email in emails.get('value', []):
                subject = email.get('subject', '(No Subject)')
                sender = email.get('from', {}).get('emailAddress', {}).get('address', '(Unknown Sender)')
                print(f"From: {sender}, Subject: {subject}")
        else:
            print(f"Failed to fetch emails: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    fetch_emails()
