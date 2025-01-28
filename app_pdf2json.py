from transformers import AutoProcessor, AutoModelForImageTextToText
from qwen_vl_utils import process_vision_info
import json
import torch
import os 
from app_json2excel2onedrive import upload_to_onedrive, get_access_token
import shutil

processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-2B-Instruct")
model = AutoModelForImageTextToText.from_pretrained("Qwen/Qwen2-VL-2B-Instruct")


if torch.cuda.is_available():
    model = model.to("cuda")
    print("Model moved to GPU")
else:
    model = model.to("cpu")
    print("Model moved to CPU")


def pdf2json(file_path):
    file_name = file_path

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "image": file_name,
                    "resized_height": 696,
                    "resized_width": 943,
                },
                {
                    "type": "text",
                    "text": "Retrieve invoice_number, date_of_issue, seller_info, client_info, invoice_items_table, currency. Response must be in JSON format"
                }
            ]
        }
    ]

    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )

    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )

    # Move inputs to the same device as the model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    inputs = {key: value.to(device) for key, value in inputs.items()}

    generated_ids = model.generate(**inputs, max_new_tokens=1024)
    generated_ids_trimmed = [
        out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs["input_ids"], generated_ids)
    ]

    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=True)

    json_string = output_text[0]
    json_string = json_string.strip("[]'")
    json_string = json_string.replace("```json\n", "").replace("\n```", "")
    json_string = json_string.replace("'", "")
    print(json_string)
    try:
        formatted_json2 = json.loads(json_string)
        # formatted_json2 = {
        #     "invoice_number": "04/85/1345",
        #     "date_of_issue": "04. January 2023",
        #     "seller_info": {
        #         "name": "PSI Services SA",
        #         "address": "17, Rue de Flawetter - L-6775 Gravenmacher",
        #         "phone": "+352 222 333 444",
        #         "email": "pierre.muller@luxconglobal.lu"
        #     },
        #     "client_info": {
        #         "name": "PSI Concepts SA"
        #     },
        #     "invoice_items_table": [
        #         {
        #         "position": 1,
        #         "description": "Yearly Fee 2022",
        #         "vat_percent": 17.00,
        #         "net_amount": 8000.00,
        #         "vat_amount": 1360.00,
        #         "gross_amount": 9360.00
        #         }
        #     ],
        #     "currency": "EUR"
        # }
        formatted_json = {
            "client": formatted_json2["seller_info"]["name"],
            "date": formatted_json2["date_of_issue"],
            "brutto": formatted_json2["invoice_items_table"][0]["gross_amount"],
            "net": formatted_json2["invoice_items_table"][0]["net_amount"],
            "vat": formatted_json2["invoice_items_table"][0]["vat_amount"],
            "currency": formatted_json2["currency"],
        }
        extension = file_name.split('.')[-1]
        filename = file_name.split('/')[-1]
        formatted_json['date'] = formatted_json['date'].replace('.', '')
        formatted_filename = formatted_json['client'] + '.' + extension
        formatted_filename_json = formatted_json['client'] + '.json'
        file_path = 'Data/InvoiceData/' + formatted_filename_json

        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                existing_data = json.load(f)
                if not isinstance(existing_data, list):
                    existing_data = [existing_data]
        else:
            existing_data = []

        existing_data.append(formatted_json)

        with open(file_path, 'w') as f:
            json.dump(existing_data, f, indent=4)
            access_token = get_access_token()
            filepathinOneDrive = 'Attachments/' + formatted_json['client'] + '/' + formatted_json['client'] + '_' + formatted_json['date'] + '.' + extension
            print('filename: ', filename)
            print('filepathinOneDrive: ', filepathinOneDrive)
            print('formatted_filename: ', formatted_filename)
            print('extension: ', extension)
            upload_to_onedrive(access_token, file_name, filepathinOneDrive)
            # if subdirectory does not exist, create it
            if not os.path.exists('Data/Attachments/' + formatted_json['client']):
                os.makedirs('Data/Attachments/' + formatted_json['client'])
                print("creating the dir!!!!")
            shutil.copy(file_path, 'Data/' + filepathinOneDrive)    
    except json.JSONDecodeError as e:
        print("Not valid JSON format:", e)

if __name__ == "__main__":
    attachments_folder = "attachments/"
    try:
        for filename in os.listdir(attachments_folder):
            file_path = os.path.join(attachments_folder, filename)
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                print(f"Processing picture file: {file_path}")
                pdf2json(file_path)
            # else:
            #     print(f"Can not process: {file_path}. It needs to be a picture file.")
    except Exception as e:
        print(f"Error: {e}")