#!/usr/bin/env python3
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_server_files():
    try:
        new_main_code = open("/root/master_kees/new_main.py").read()
        shared_data = open("/root/master_kees/shared_data.py").read()
        heatpump = open("/root/master_kees/clients/julianalaan_39/heatpump.py").read()
        heatpump_fixed = open("/root/master_kees/clients/julianalaan_39/heatpump_fixed.py").read()
        with open("/root/master_kees/new_main_test.log") as f:
            logs = f.read()[-2000:]
        all_code = (
            f"new_main.py:\n{new_main_code}\n\n"
            f"shared_data.py:\n{shared_data}\n\n"
            f"heatpump.py:\n{heatpump}\n\n"
            f"heatpump_fixed.py:\n{heatpump_fixed}\n\n"
            f"Recent logs:\n{logs}"
        )
        return all_code
    except Exception as e:
        return f"Error reading files: {e}"

def interact_with_agent(user_query):
    all_code = get_server_files()
    full_prompt = (
        f"You’re on my server (159.223.10.31). Here’s my code and logs:\n{all_code}\n\n"
        f"My question: {user_query}\n\n"
        "Help me fix or understand my server setup—keep it simple, I’m not a programmer."
    )
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": full_prompt}],
        max_tokens=2000
    )
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    print("Interactive Agent Chat - Talking to your server files! Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting.")
            break
        answer = interact_with_agent(user_input)
        print("Agent:", answer)