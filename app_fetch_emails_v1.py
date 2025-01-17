from imap_tools import MailBox
from msal import PublicClientApplication
import requests
import os
from dotenv import load_dotenv
load_dotenv()

# Configuration
CLIENT_ID = os.getenv('CLIENT_ID') 
ACCOUNT_EMAIL = os.getenv('ACCOUNT_EMAIL')  
AUTHORITY = 'https://login.microsoftonline.com/consumers'
SCOPES = ['https://graph.microsoft.com/.default']

def get_access_token():
    app = PublicClientApplication(client_id=CLIENT_ID, authority=AUTHORITY)
    flow = app.initiate_device_flow(scopes=SCOPES)
    if 'user_code' not in flow:
        raise Exception(f"Device flow initiation failed: {flow.get('error')}")

    print(flow['message'])  # Log in using this URL and code
    result = app.acquire_token_by_device_flow(flow)
    
    if 'access_token' in result:
        return result['access_token']
    else:
        raise Exception(f"Failed to get access token: {result.get('error_description')}")

def connect_to_outlook():
    access_token = get_access_token()
    headers = {'Authorization': f'Bearer {access_token}'}
    endpoint = f'https://graph.microsoft.com/v1.0/me/messages'

    try:
        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            emails = response.json()
            for email in emails['value']:
                print(f"Subject: {email['subject']}, From: {email['from']['emailAddress']['address']}")
        else:
            print(f"Failed to fetch emails: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    connect_to_outlook()
