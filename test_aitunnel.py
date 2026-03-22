import os
import requests
from dotenv import load_dotenv

load_dotenv()

headers = {
    "Authorization": f"Bearer {os.getenv('AITUNNEL_API_KEY')}",
    "Content-Type": "application/json"
}

payload = {
    "model": os.getenv("AITUNNEL_MODEL", "gpt-4o-mini"),
    "messages": [{"role": "user", "content": "Ответь одним словом: ОК"}],
    "max_tokens": 20,
    "temperature": 0
}

r = requests.post(
    "https://api.aitunnel.ru/v1/chat/completions",
    headers=headers,
    json=payload,
    timeout=60
)

print("STATUS:", r.status_code)
print("RESPONSE:", r.text[:500])