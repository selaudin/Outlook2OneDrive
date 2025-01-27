import os
import requests
from msal import PublicClientApplication, SerializableTokenCache
import logging
from dotenv import load_dotenv
load_dotenv()


logging.basicConfig(
    filename='email_fetch.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
CLIENT_ID = os.getenv('CLIENT_ID') 
ACCOUNT_EMAIL = os.getenv('ACCOUNT_EMAIL') 
AUTHORITY = 'https://login.microsoftonline.com/common'
SCOPES = ['Mail.Read']
TOKEN_CACHE_FILE = 'token_cache.json'
ATTACHMENTS_DIR = 'Data/attachments' 

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
            logger.info("Acquired token silently.")
            return result['access_token']

    # If silent acquisition fails, initiate device code flow
    flow = app.initiate_device_flow(scopes=SCOPES)
    if 'user_code' not in flow:
        logger.error(f"Device flow initiation failed: {flow.get('error')}")
        raise Exception(f"Device flow initiation failed: {flow.get('error')}")

    logger.info("Initiating device code flow. Please authenticate.")
    print(flow['message'])  # Prompt user to authenticate
    result = app.acquire_token_by_device_flow(flow)

    if 'access_token' in result:
        save_token_cache(cache)
        logger.info("Acquired token via device code flow.")
        return result['access_token']
    else:
        logger.error(f"Failed to get access token: {result.get('error_description')}")
        raise Exception(f"Failed to get access token: {result.get('error_description')}")

def download_attachment(access_token, message_id, attachment):
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    attachment_id = attachment['id']
    attachment_name = attachment['name']
    attachment_content_type = attachment['contentType']

    # Endpoint to download the attachment
    download_endpoint = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments/{attachment_id}/$value"

    response = requests.get(download_endpoint, headers=headers)
    if response.status_code == 200:
        # Ensure the attachments directory exists
        os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
        # Sanitize attachment name to prevent directory traversal attacks
        safe_attachment_name = os.path.basename(attachment_name)
        file_path = os.path.join(ATTACHMENTS_DIR, safe_attachment_name)
        with open(file_path, 'wb') as f:
            f.write(response.content)
        logger.info(f"Downloaded attachment: {safe_attachment_name}")
    else:
        logger.error(f"Failed to download attachment {attachment_name}: {response.status_code} - {response.text}")

def fetch_emails():
    try:
        access_token = get_access_token()
        headers = {'Authorization': f'Bearer {access_token}'}
        endpoint = 'https://graph.microsoft.com/v1.0/me/messages?$top=10&$orderby=receivedDateTime desc&$expand=attachments'

        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            emails = response.json()
            for email in emails.get('value', []):
                subject = email.get('subject', '(No Subject)')
                sender = email.get('from', {}).get('emailAddress', {}).get('address', '(Unknown Sender)')
                logger.info(f"From: {sender}, Subject: {subject}")

                attachments = email.get('attachments', [])
                if attachments:
                    logger.info(f"Found {len(attachments)} attachment(s). Downloading...")
                    for attachment in attachments:
                        if attachment['@odata.type'] == '#microsoft.graph.fileAttachment':
                            download_attachment(access_token, email['id'], attachment)
                        elif attachment['@odata.type'] == '#microsoft.graph.itemAttachment':
                            logger.warning("Item attachments are not handled in this script.")
                        else:
                            logger.warning(f"Unknown attachment type: {attachment['@odata.type']}")
                else:
                    logger.info("No attachments found in this email.")
                logger.info("-" * 50)
        else:
            logger.error(f"Failed to fetch emails: {response.status_code} - {response.text}")

    except Exception as e:
        logger.error(f"An error occurred: {e}")

if __name__ == "__main__":
    fetch_emails()
