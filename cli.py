"""Terminal chat: the simplest interface to the agent. Slack and Teams will be siblings of this file."""

import os

import anthropic
from dotenv import load_dotenv

from agent import run_agent


def main():
    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key.")
        return
    client = anthropic.Anthropic()

    print("IT Helpdesk Agent (type 'exit' to quit)")
    try:
        user_email = ""
        while not user_email:
            user_email = input("Your email: ").strip()

        messages = []  # The conversation history. Claude only remembers what we resend.
        while True:
            user_input = input("\nYou: ").strip()
            if user_input.lower() == "exit":
                break
            if not user_input:
                continue

            messages.append({"role": "user", "content": user_input})
            try:
                reply = run_agent(client, messages, user_email)
            except anthropic.AuthenticationError:
                print("\nThe API rejected your key. Check ANTHROPIC_API_KEY in your .env file.")
                break
            except anthropic.RateLimitError:
                print("\nRate limited by the API. Wait a moment and try again.")
                continue
            except anthropic.APIStatusError as e:
                print(f"\nThe API returned an error ({e.status_code}): {e.message}")
                continue
            except anthropic.APIConnectionError:
                print("\nCouldn't reach the API. Check your internet connection and try again.")
                continue
            print(f"\nAgent: {reply}")
    except (EOFError, KeyboardInterrupt):
        print()


if __name__ == "__main__":
    main()
