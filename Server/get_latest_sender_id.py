"""
Utility to find the latest Instagram user who sent a DM to @tanglome,
print their username & IGSID, and optionally update Server/.env.
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv("Server/.env")

ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")
IG_USER_ID = os.getenv("INSTAGRAM_USER_ID", "17841472775037140")

if not ACCESS_TOKEN:
    print("Error: INSTAGRAM_ACCESS_TOKEN not set in Server/.env")
    exit(1)

url = f"https://graph.facebook.com/v21.0/{IG_USER_ID}/conversations?platform=instagram&fields=participants,updated_time,messages.limit(1){{message,from,created_time}}&limit=5&access_token={ACCESS_TOKEN}"

res = requests.get(url)
if res.status_code != 200:
    print(f"Error fetching conversations [{res.status_code}]: {res.text}")
    exit(1)

data = res.json().get("data", [])
print(f"\nFound {len(data)} conversation thread(s) on @tanglome:\n")

found_user = None

for conv in data:
    updated = conv.get("updated_time")
    participants = conv.get("participants", {}).get("data", [])
    other_users = [p for p in participants if p.get("id") != IG_USER_ID]
    msgs = conv.get("messages", {}).get("data", [])
    last_msg = msgs[0] if msgs else {}

    for u in other_users:
        username = u.get("username")
        user_id = u.get("id")
        print(f"• User: @{username} | IGSID: {user_id} | Last Activity: {updated}")
        if last_msg:
            print(f"  Last Msg: \"{last_msg.get('message')}\" from @{last_msg.get('from', {}).get('username')} at {last_msg.get('created_time')}")
        if not found_user:
            found_user = (username, user_id)

if found_user:
    print(f"\nMost recent recipient: @{found_user[0]} (ID: {found_user[1]})")
    print(f"To receive bot alerts on @{found_user[0]}, set in Server/.env:")
    print(f"INSTAGRAM_RECIPIENT_ID={found_user[1]}\n")
else:
    print("\nNo external users found. Please send a DM to @tanglome from your Instagram account to open the 24h window!")

