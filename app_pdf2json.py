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
else:
    model = model.to("cpu")

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
                    "text": "Retrieve company name (output it as 'client'), date(convert the format in DDMMYYYY), vat, brutto, net, currency. Response must be in JSON format."
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
        formatted_json = json.loads(json_string)
        extension = file_name.split('.')[-1]
        filename = file_name.split('/')[-1]
        formatted_json['date'] = formatted_json['date'].replace('.', '')
        formatted_filename = formatted_json['client']+'_'+formatted_json['date']+'.'+extension
        formatted_filename_json = formatted_json['client']+'_'+formatted_json['date']+'.json'
        with open('Data/InvoiceData/'+formatted_filename_json, 'w') as f:
            access_token = get_access_token()
            filepathinOneDrive = 'Attachments/'+formatted_json['client']+'/'+formatted_filename
            print('filename: ', filename)
            print('filepathinOneDrive: ', filepathinOneDrive)
            print('formatted_filename: ', formatted_filename)
            print('extension: ', extension)
            upload_to_onedrive(access_token, file_name, filepathinOneDrive)
            # convert format of DD.MM.YYYY to DDMMYYYY
            json.dump(formatted_json, f)
            shutil.copy(file_path, 'Data/Attachments/'+formatted_json['client']+'_'+formatted_json['date']+'.'+extension)
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