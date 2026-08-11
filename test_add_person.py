import requests
import sys

BASE='http://127.0.0.1:8000'
USERNAME='autouser'
PASSWORD='autopass'
IMAGE='dataset/100_Bill_McBride.jpg'

# Login
r = requests.post(f'{BASE}/auth/login', data={'username': USERNAME, 'password': PASSWORD})
if r.status_code != 200:
    print('Login failed', r.status_code, r.text)
    sys.exit(1)
token = r.json()['access_token']
print('Got token prefix', token[:8])

headers = {'Authorization': f'Bearer {token}'}

# Add person
person_id = 'test_miss_001'
name = 'Test Missing'
category = 'missing_person'
with open(IMAGE, 'rb') as f:
    files = {'file': (IMAGE, f, 'image/jpeg')}
    data = {'person_id': person_id, 'name': name, 'category': category}
    r = requests.post(f'{BASE}/add-person', headers=headers, data=data, files=files)
print('\n/add-person ->', r.status_code, r.text)

# Search using same image
with open(IMAGE, 'rb') as f:
    files = {'file': (IMAGE, f, 'image/jpeg')}
    r = requests.post(f'{BASE}/search', headers=headers, files=files)
print('\n/search ->', r.status_code)
try:
    print(r.json())
except Exception:
    print(r.text)
