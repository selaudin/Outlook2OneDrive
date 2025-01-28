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
SCOPES = ['Mail.Read', 'Files.ReadWrite']
TOKEN_CACHE_FILE = 'token_cache.json'
ATTACHMENTS_DIR = 'attachments' 
ONEDRIVE_DEST_FOLDER = '/Attachments'  # OneDrive folder path

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

    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPES, account=accounts[0])
        if result and 'access_token' in result:
            save_token_cache(cache)
            logger.info("Acquired token silently.")
            return result['access_token']

    flow = app.initiate_device_flow(scopes=SCOPES)
    if 'user_code' not in flow:
        logger.error(f"Device flow initiation failed: {flow.get('error')}")
        raise Exception(f"Device flow initiation failed: {flow.get('error')}")

    logger.info("Initiating device code flow. Please authenticate.")
    print(flow['message'])  
    result = app.acquire_token_by_device_flow(flow)

    if 'access_token' in result:
        save_token_cache(cache)
        logger.info("Acquired token via device code flow.")
        return result['access_token']
    else:
        logger.error(f"Failed to get access token: {result.get('error_description')}")
        raise Exception(f"Failed to get access token: {result.get('error_description')}")

def upload_to_onedrive(access_token, file_path, destination_file_name, destination_folder=ONEDRIVE_DEST_FOLDER):
    """
    Uploads a file to OneDrive.

    :param access_token: OAuth2 access token.
    :param file_path: Local path to the file.
    :param file_name: Name to save the file as in OneDrive.
    :param destination_folder: OneDrive folder path where the file will be uploaded.
    """
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/octet-stream'
    }

    # files sizes (<4MB)
    destination_folder = destination_folder.replace(' ', '%20')
    upload_url = f'https://graph.microsoft.com/v1.0/me/drive/root:{destination_folder}/{destination_file_name}:/content'

    # Read the file content
    with open(file_path, 'rb') as f:
        file_content = f.read()

    # request to upload the file
    response = requests.put(upload_url, headers=headers, data=file_content)

    if response.status_code in [200, 201]:
        logger.info(f"Successfully uploaded {destination_file_name} to OneDrive at {destination_folder}.")
    else:
        logger.error(f"Failed to upload {destination_file_name} to OneDrive: {response.status_code} - {response.text}")

def upload_large_file_to_onedrive(access_token, file_path, destination_file_name, destination_folder=ONEDRIVE_DEST_FOLDER):
    """
    Uploads a large file to OneDrive using an upload session.

    :param access_token: OAuth2 access token.
    :param file_path: Local path to the file.
    :param file_name: Name to save the file as in OneDrive.
    :param destination_folder: OneDrive folder path where the file will be uploaded.
    """
    headers = {
        'Authorization': f'Bearer {access_token}'
    }

    destination_folder = destination_folder.replace(' ', '%20')
    upload_session_url = f"https://graph.microsoft.com/v1.0/me/drive/root:{destination_folder}/{destination_file_name}:/createUploadSession"

    upload_session_payload = {
        "item": {
            "@microsoft.graph.conflictBehavior": "rename",
            "name": file_name
        }
    }

    upload_session_response = requests.post(upload_session_url, headers=headers, json=upload_session_payload)

    if upload_session_response.status_code == 200:
        upload_url = upload_session_response.json()['uploadUrl']
    else:
        logger.error(f"Failed to create upload session for {file_name}: {upload_session_response.status_code} - {upload_session_response.text}")
        return

    # Read the file in chunks and upload
    file_size = os.path.getsize(file_path)
    chunk_size = 320 * 1024  # 320KB chunks
    with open(file_path, 'rb') as f:
        bytes_uploaded = 0
        while bytes_uploaded < file_size:
            chunk_data = f.read(chunk_size)
            if not chunk_data:
                break
            start_range = bytes_uploaded
            end_range = bytes_uploaded + len(chunk_data) - 1
            headers = {
                'Content-Length': str(len(chunk_data)),
                'Content-Range': f'bytes {start_range}-{end_range}/{file_size}'
            }
            chunk_response = requests.put(upload_url, headers=headers, data=chunk_data)
            if chunk_response.status_code in [200, 201, 202]:
                bytes_uploaded += len(chunk_data)
                logger.info(f"Uploaded {bytes_uploaded}/{file_size} bytes of {file_name}.")
            else:
                logger.error(f"Failed to upload chunk {start_range}-{end_range} of {file_name}: {chunk_response.status_code} - {chunk_response.text}")
                break

    logger.info(f"Finished uploading {file_name} to OneDrive.")

def fetch_emails():
    try:
        access_token = get_access_token()
        headers = {'Authorization': f'Bearer {access_token}'}
        endpoint = 'https://graph.microsoft.com/v1.0/me/messages?$top=1&$orderby=receivedDateTime desc&$expand=attachments'

        response = requests.get(endpoint, headers=headers)
        if response.status_code == 200:
            emails = response.json()
            for email in emails.get('value', []):
                subject = email.get('subject', '(No Subject)')
                sender = email.get('from', {}).get('emailAddress', {}).get('address', '(Unknown Sender)')
                logger.info(f"From: {sender}, Subject: {subject}")

                attachments = email.get('attachments', [])
                if attachments:
                    logger.info(f"Found {len(attachments)} attachment(s). Downloading and uploading to OneDrive...")
                    for attachment in attachments:
                        if attachment['@odata.type'] == '#microsoft.graph.fileAttachment':
                            attachment_name = attachment['name']
                            attachment_id = attachment['id']
                            download_endpoint = f"https://graph.microsoft.com/v1.0/me/messages/{email['id']}/attachments/{attachment_id}/$value"
                            download_response = requests.get(download_endpoint, headers=headers)
                            
                            if download_response.status_code == 200:
                                # Save attachment locally
                                os.makedirs(ATTACHMENTS_DIR, exist_ok=True)
                                safe_attachment_name = os.path.basename(attachment_name)
                                file_path = os.path.join(ATTACHMENTS_DIR, safe_attachment_name)
                                with open(file_path, 'wb') as f:
                                    f.write(download_response.content)
                                logger.info(f"Downloaded attachment: {safe_attachment_name}")

                                # Determine if the file is large and choose upload method
                                file_size = os.path.getsize(file_path)
                                if file_size < 4 * 1024 * 1024:  # <4MB
                                    upload_to_onedrive(access_token, file_path, safe_attachment_name)
                                else:
                                    upload_large_file_to_onedrive(access_token, file_path, safe_attachment_name)
                            else:
                                logger.error(f"Failed to download attachment {attachment_name}: {download_response.status_code} - {download_response.text}")
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
