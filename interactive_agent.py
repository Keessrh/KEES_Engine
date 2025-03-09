#!/usr/bin/env python3
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def interact_with_agent(user_query):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": user_query}],
        max_tokens=2000
    )
    return response.choices[0].message.content.strip()

if __name__ == "__main__":
    print("Interactive Agent Chat. Type 'exit' to quit.")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Exiting.")
            break
        answer = interact_with_agent(user_input)
        print("Agent:", answer)
