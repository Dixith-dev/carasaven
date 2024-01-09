from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from openai import OpenAI
import os
from dotenv import load_dotenv, find_dotenv
import shelve
import time
import re
import sys

#--------------------------------------------------------------
# Load API key
#--------------------------------------------------------------

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# --------------------------------------------------------------
# Upload file
# --------------------------------------------------------------

def upload_file(path):
    # Upload a file with an "assistants" purpose
    file = client.files.create(file=open(path, "rb"), purpose="assistants")
    return file

file = upload_file("dataset.pdf")

# --------------------------------------------------------------
# Create assistant
# --------------------------------------------------------------

def create_assistant(file):
    """
    You currently cannot set the temperature for Assistant via the API.
    """
    assistant = client.beta.assistants.create(
        name="carasaven AI",
        instructions="As the carasaven AI, developed by Tab Robotics, your main responsibility is to provide users with assistance regarding the products offered by carasaven. When addressing users, please use the pronoun 'we' to refer to the company. Your integration on their website aims to ensure prompt and relevant support in a professional manner, enabling users to navigate through available options efficiently. As a user, my questions will solely pertain to carasaven, and not about the AI itself. Therefore, please only provide information based on the data provided. For instance, if I ask 'What products do you provide?', your response should be concise and informative, stating the specific services offered by carasaven. Additionally, when the user greets you at the start of the conversation, please respond with 'How can I assist you today?' and don't say this after you provide your first response please continue the conversation like a human. Please look at what you are saying and make sure it makes. sense if the user asks a question instead of greeting please answer the question and do not be robotic and repeat this please continue the conversation like a human. Please try to answer in very short format but also provide the most important information in short. Please maintain some space between the sentences. Try to be happy and positive. When user asks to recommend a product also give him the image link and give it only once. If you cant find the link in the dataset please do not make it up because the link will be processed as an image to show to the user. Do not recommend or display any links that are not in the dataset.'",                                    
        tools=[{"type": "retrieval"}],
        model="gpt-4-1106-preview",
        file_ids=[file.id],
    )
    return assistant

assistant = create_assistant(file)

assist_id = assistant.id

# --------------------------------------------------------------
# Thread management
# --------------------------------------------------------------

def check_if_thread_exists(wa_id):
    with shelve.open("thread_data//threads_db") as threads_shelf:
        return threads_shelf.get(wa_id, None)

def store_thread(wa_id, thread_id):
    with shelve.open("thread_data//threads_db", writeback=True) as threads_shelf:
        threads_shelf[wa_id] = thread_id


# --------------------------------------------------------------
# Generate response
# --------------------------------------------------------------
        
def generate_response(message_body, wa_id, name):
    # Check if there is already a thread_id for the wa_id
    thread_id = check_if_thread_exists(wa_id)

    # If a thread doesn't exist, create one and store it
    if thread_id is None:
        print(f"Creating new thread for {name} with wa_id {wa_id}")
        thread = client.beta.threads.create()
        store_thread(wa_id, thread.id)
        thread_id = thread.id

    # Otherwise, retrieve the existing thread
    else:
        print(f"Retrieving existing thread for {name} with wa_id {wa_id}")
        thread = client.beta.threads.retrieve(thread_id)

    # Add message to thread
    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=message_body,
    )

    # Run the assistant and get the new message
    new_message = run_assistant(thread)
    print(f"To {name}:", new_message)
    cleaned_response = re.sub(r'【.*】', '', new_message)
    return cleaned_response


# --------------------------------------------------------------
# Run assistant
# --------------------------------------------------------------

def run_assistant(thread):
    # Retrieve the Assistant
    assistant = client.beta.assistants.retrieve(assist_id)

    # Run the assistant
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
    )

    # Wait for completion
    while run.status != "completed":
        # Be nice to the API
        #time.sleep(0.1)
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

    # Retrieve the Messages
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    new_message = messages.data[0].content[0].text.value
    print(f"Generated message: {new_message}")
    return new_message

# --------------------------------------------------------------
# Test assistant with flask
# --------------------------------------------------------------

app = Flask(__name__)
CORS(app)

conversation_details = {}
current_stage = "initial"

@app.route('/')
def home():
    return render_template('bannner.html')  

# Define route for getting response
@app.route('/get-response', methods=['POST'])
def get_response():
    global current_stage
    user_input = request.json['message'].lower().strip()
    user_id = request.json.get('user_id')  # Get user/session identifier from the request
    if not user_id:
        return jsonify({'response': "Error: User ID is missing or invalid."})

    flask_output = generate_response(user_input, wa_id=user_id, name="User")  # Use user_id for wa_id
    return jsonify({'response': flask_output})


if __name__ == '__main__':
    app.run(debug=True)
