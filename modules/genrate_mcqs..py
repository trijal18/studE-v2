import os
from dotenv import load_dotenv
import google.generativeai as genai
import json
import project.modules.pdf_to_text as pdf_to_text

import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
import project.modules.pdf_to_text as pdf_to_text  

import os
import json
import google.generativeai as genai
from dotenv import load_dotenv
import project.modules.pdf_to_text as pdf_to_text

def genrate_mcqs(file_path):
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=key)

    generation_config = {
        "temperature": 1,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        "response_mime_type": "text/plain",
    }

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config,
        system_instruction="""
            Generate 10 multiple-choice questions based on the given text. Provide the question, a list of plausible answer options, and indicate the correct answer. Format the response as a JSON array of objects like below:

            [
            {
                "question": "...",
                "options": ["...", "...", "...", "..."],
                "answer": "..."
            }
            ]
        """
    )

    chat_session = model.start_chat(history=[])
    text = pdf_to_text.pdf_to_text(file_path)
    response = chat_session.send_message(text)

    # Clean and extract JSON from markdown-style response
    raw_text = response.text.strip()

    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]  # Remove ```json\n
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]  # Remove closing ```

    # Try parsing cleaned JSON
    try:
        mcqs = json.loads(raw_text)
        return mcqs[0]
    except json.JSONDecodeError as e:
        print("JSON Decode Error:", e)
        print("Cleaned text was:\n", raw_text)
        return {}



print(type(genrate_mcqs(r"C:\Users\91942\Downloads\1 (1).pdf")))

def genrate_content(file_path):
    #pass api key
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    genai.configure(api_key=key)

    # configure the model
    generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
    }

    #create model and pass instructions
    model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=generation_config,
    # safety_settings = Adjust safety settings
    # See https://ai.google.dev/gemini-api/docs/safety-settings
    system_instruction="""
            **Prompt:**  
            "Generate multiple-choice questions based on the given text. Provide the question, a list of plausible answer options, and indicate the correct answer. Format the response as a JSON object. Ensure the question and options are clear and directly related to the content of the text.  

            **Example Output:**
            {
            "question": "What is VNC used for in the context of a Raspberry Pi?",
            "options": [
                "To access the Raspberry Pi's graphical interface remotely",
                "To control the Raspberry Pi's camera",
                "To update the Raspberry Pi's operating system",
                "To connect the Raspberry Pi to a network"
            ],
            "answer": "To access the Raspberry Pi's graphical interface remotely"
            }
            """,
    )

    chat_session = model.start_chat(
    history=[
    ]
    )

    text=pdf_to_text.pdf_to_text(file_path)

    response = chat_session.send_message(text)

    dict=json.loads(response.text[8:-3])

    res_summary=chat_session.send_message("Please generate a detailed summary of the given text, ensuring that no asterisks (***) are included in the output text.")
    summary=res_summary.text
    return dict, summary