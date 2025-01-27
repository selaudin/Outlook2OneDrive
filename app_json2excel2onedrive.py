import os
import requests
from msal import PublicClientApplication, SerializableTokenCache
import logging
from dotenv import load_dotenv
load_dotenv()
from Json2Excel.main import process_invoice

logging.basicConfig(
    filename='email_fetch_upload.log',
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
ATTACHMENTS_DIR = 'Data/attachments' 
ONEDRIVE_DEST_FOLDER = '/Invoices'  # OneDrive folder path

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

def upload_large_file_to_onedrive(access_token, file_path, file_name, destination_folder=ONEDRIVE_DEST_FOLDER):
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
    upload_session_url = f"https://graph.microsoft.com/v1.0/me/drive/root:{destination_folder}/{file_name}:/createUploadSession"

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

def upload_json2onedrive(json_filename=None, excel_filename=None, company_name=None, directory=None):
    # full_path_json  = os.path.join('Data/InvoiceData/', json_filename)
    # if process_invoice(full_path_json, full_path_excel):
    #     access_token = get_access_token()
    #     upload_to_onedrive(access_token, full_path_json, json_filename, destination_folder="/InvoiceData")
    #     upload_to_onedrive(access_token, full_path_excel, excel_filename, destination_folder="/Summaries")
    #     print("Files uploaded successfully.")
    # else:
    #     print("Invoice processing failed.")
    if directory:
        for file in os.listdir(directory):
            if file.endswith('.json'):
                file_name = file.split('.')[0]
                full_path = os.path.join(directory, file)
                excel_filename = file_name + '.xlsx'
                full_path_excel = os.path.join('Data/Summaries/', excel_filename)
                if process_invoice(full_path, full_path_excel):
                    access_token = get_access_token()
                    upload_to_onedrive(access_token=access_token, file_path=full_path, destination_file_name=file, destination_folder="/Invoices/InvoiceData")
                    upload_to_onedrive(access_token=access_token, file_path=full_path_excel, destination_file_name=excel_filename, destination_folder="/Invoices/Summaries")
                    print(f"Uploaded {file} to OneDrive.")
                else:
                    print(f"Processing failed for {file}.")

if __name__ == "__main__":
    # Example usage:
    # upload_json2onedrive('PSI Concepts SA.json', 'invoice_data.xlsx', 'Aevux')
    upload_json2onedrive(directory='Data/InvoiceData/')