import requests
import sys
import time

BASE = 'http://127.0.0.1:8000'
USERNAME = 'autouser'
PASSWORD = 'autopass'
IMAGE_PATH = 'dataset/012_David_Beckham.jpg'

def pretty(o):
    import json
    print(json.dumps(o, indent=2))

try:
    print('GET /health')
    r = requests.get(f'{BASE}/health', timeout=10)
    r.raise_for_status()
    pretty(r.json())
except Exception as e:
    print('Health check failed:', e)
    sys.exit(1)

# Register (ignore if already exists)
try:
    print('\nPOST /auth/register')
    r = requests.post(f'{BASE}/auth/register', json={'username': USERNAME, 'password': PASSWORD, 'role': 'admin'}, timeout=10)
    if r.status_code == 200 or r.status_code == 201:
        pretty(r.json())
    else:
        print('Register returned', r.status_code, r.text)
except Exception as e:
    print('Register failed:', e)

# Login
try:
    print('\nPOST /auth/login')
    r = requests.post(f'{BASE}/auth/login', data={'username': USERNAME, 'password': PASSWORD}, timeout=10)
    r.raise_for_status()
    token = r.json().get('access_token')
    print('Got token:', token[:8] + '...' if token else None)
except Exception as e:
    print('Login failed:', e)
    sys.exit(1)

# Perform search
try:
    print('\nPOST /search')
    headers = {'Authorization': f'Bearer {token}'}
    with open(IMAGE_PATH, 'rb') as f:
        files = {'file': (IMAGE_PATH, f, 'image/jpeg')}
        r = requests.post(f'{BASE}/search', headers=headers, files=files, timeout=30)
    if r.status_code == 200:
        print('Search results:')
        pretty(r.json())
    else:
        print('Search failed', r.status_code, r.text)
except Exception as e:
    print('Search request failed:', e)
    sys.exit(1)
