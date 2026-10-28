import os
import httpx
from dotenv import  load_dotenv

load_dotenv()

API_KEY = os.getenv("BREVO_API_KEY")
URL = "https://api.brevo.com/v3/smtp/email"

headers = {
    "accept": "application/json",
    "api-key": API_KEY,
    "content-type": "application/json",
}

payload = {
    "sender": {"name": "CargoFlow Africa", "email": "noreply@cargoflowafrica.co.za"},
    "to": [{"email": "junior@apextransportgroup.co.za", "name": "Test User"}],
    "subject": "Brevo API Test",
    "htmlContent": "<html><body><h3>It works!</h3><p>Your Brevo API integration is successfully configured.</p></body></html>",
}

response = httpx.post(URL, json=payload, headers=headers)
print(f"Status Code: {response.status_code}")
print(response.json())