#!/usr/bin/env python3
import time
import sys
import os
import requests

BASE_URL = os.getenv('BASE_URL', 'http://localhost:8000')
EMAIL = os.getenv('TEST_EMAIL')
PASSWORD = os.getenv('TEST_PASSWORD')

if not EMAIL or not PASSWORD:
    print("Need TEST_EMAIL and TEST_PASSWORD env vars")
    sys.exit(1)

session = requests.Session()

def login():
    print(f"Logging in as {EMAIL}...")
    resp = session.post(f'{BASE_URL}/auth/login', json={'email': EMAIL, 'password': PASSWORD})
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    if resp.status_code == 429:
        print("Rate limited, waiting 60s...")
        time.sleep(60)
        resp = session.post(f'{BASE_URL}/auth/login', json={'email': EMAIL, 'password': PASSWORD})
        print(f"Retry Status: {resp.status_code}")
        print(f"Retry Response: {resp.text}")
    resp.raise_for_status()
    return resp.json()

def main():
    try:
        login()
        print("\nNow check your email for the OTP code.")
        code = input("Enter the code from email: ").strip()
        print(f"Verifying OTP with code {code}...")
        resp = session.post(f'{BASE_URL}/auth/verify-otp', 
                          json={'email': EMAIL, 'code': code, 'remember_device': True})
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        resp.raise_for_status()
        tokens = resp.json()
        access_token = tokens['access_token']
        print(f"\nGot access token: {access_token[:20]}...")
        
        print("\nCalling GET /auth/me...")
        headers = {'Authorization': f'Bearer {access_token}'}
        resp = session.get(f'{BASE_URL}/auth/me', headers=headers)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
        resp.raise_for_status()
        print("\n✓ Success!")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
