import requests
import time
import sqlite3
import json
import os
import sys

BASE = 'http://127.0.0.1:8000'
AUTH = 'http://127.0.0.1:8001'

print('Checking auth service...')
try:
    r = requests.post(AUTH + '/login', data={'username': 'autouser', 'password': 'autopass'})
    if r.status_code == 401:
        print('User not found, registering admin user...')
        reg = requests.post(AUTH + '/register', json={'username': 'autouser', 'password': 'autopass', 'role': 'admin'})
        print('register status', reg.status_code, reg.text[:200])
        reg.raise_for_status()
        r = requests.post(AUTH + '/login', data={'username': 'autouser', 'password': 'autopass'})
    print('login status', r.status_code)
    r.raise_for_status()
except Exception as exc:
    print('Auth login failed:', exc)
    sys.exit(1)

token = r.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Add test person
img_path = 'dataset/100_Bill_McBride.jpg'
if not os.path.isfile(img_path):
    print('Missing image file for test:', img_path)
    sys.exit(1)

with open(img_path, 'rb') as f:
    files = {'file': ('100_Bill_McBride.jpg', f, 'image/jpeg')}
    data = {'person_id': 'test_missing_001', 'name': 'Test Missing', 'category': 'missing_person'}
    r = requests.post(BASE + '/add-person', headers=headers, data=data, files=files)
print('/add-person', r.status_code)
print(r.text[:400])
if r.status_code not in (200, 201):
    sys.exit(1)

# Verify mapping entry
mapping = json.load(open('face_mapping.json', 'r', encoding='utf-8'))
entries = [m for m in mapping if m['person_id'] == 'test_missing_001']
print('mapping entries for test_missing_001', len(entries))
if entries:
    print(entries[-1])

# Test invalid category rejection
with open(img_path, 'rb') as f:
    files = {'file': ('100_Bill_McBride.jpg', f, 'image/jpeg')}
    data = {'person_id': 'test_invalid_001', 'name': 'Test Invalid', 'category': 'not_a_category'}
    r2 = requests.post(BASE + '/add-person', headers=headers, data=data, files=files)
print('/add-person invalid category', r2.status_code, r2.text[:200])

# Check camera locations endpoint
r = requests.get(BASE + '/camera-locations', headers=headers)
print('/camera-locations', r.status_code, r.text[:400])

# Start CCTV scan
video_path = 'demo_cctv_simulated.mp4'
target_path = 'demo_assets/fictional_suspect_reference.jpg'
if not os.path.isfile(video_path) or not os.path.isfile(target_path):
    print('Missing demo sample files:', video_path, target_path)
    sys.exit(1)

with open(video_path, 'rb') as vf, open(target_path, 'rb') as tf:
    files = {
        'video': ('demo_cctv_simulated.mp4', vf, 'video/mp4'),
        'target': ('fictional_suspect_reference.jpg', tf, 'image/jpeg'),
    }
    data = {'camera_id': 'demo_corridor', 'interval': '0.5', 'threshold': '0.45'}
    r = requests.post(BASE + '/cctv-scan', headers=headers, data=data, files=files)
print('/cctv-scan', r.status_code)
try:
    payload = r.json()
except Exception as exc:
    print('Failed to parse /cctv-scan response:', exc, r.text)
    sys.exit(1)
print(payload)
if r.status_code != 200 or 'job_id' not in payload:
    sys.exit(1)
job_id = payload['job_id']

# Poll until done or failed
final = None
for i in range(120):
    time.sleep(1)
    r = requests.get(BASE + f'/cctv-jobs/{job_id}/results', headers=headers)
    print('poll', i, r.status_code)
    try:
        j = r.json()
    except Exception as exc:
        print('poll json parse', exc, r.text)
        sys.exit(1)
    if j.get('status') in ('done', 'failed'):
        final = j
        print('final status', j.get('status'))
        break
    if 'matches' in j and 'events' in j:
        final = j
        print('final results received')
        break
    print('status response', j)
if final is None:
    print('Polling timed out after 120 seconds')
    sys.exit(1)

if final.get('status') != 'done':
    print('Scan did not complete successfully:', final)
    sys.exit(1)

target_person_id = final.get('input', {}).get('resolved_person_id')
print('resolved_person_id', target_person_id)

matches = final.get('matches', [])
events = final.get('events', [])
print('matches', len(matches), 'events', len(events))
if matches:
    print('match keys', sorted(matches[0].keys()))
    print('match camera_location', matches[0].get('camera_location'))
if events:
    print('event keys', sorted(events[0].keys()))
    print('event camera_location', events[0].get('camera_location'))

# Query sightings by resolved person_id first, then fallback to camera_id if needed
if target_person_id:
    r = requests.get(BASE + '/sightings', headers=headers, params={'person_id': target_person_id})
    print(f"/sightings?person_id={target_person_id}", r.status_code, len(r.json()))
    print(r.json()[:5])
    if len(r.json()) == 0:
        print('No sightings found for resolved person_id; falling back to camera_id query')
        r = requests.get(BASE + '/sightings', headers=headers, params={'camera_id': 'demo_corridor'})
        print('/sightings?camera_id=demo_corridor', r.status_code, len(r.json()))
        print(r.json()[:5])
else:
    print('Scan target did not resolve to an existing person_id; checking sightings by camera_id')
    r = requests.get(BASE + '/sightings', headers=headers, params={'camera_id': 'demo_corridor'})
    print('/sightings?camera_id=demo_corridor', r.status_code, len(r.json()))
    print(r.json()[:5])

conn = sqlite3.connect('audit.db')
cur = conn.cursor()
cur.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="sightings"')
print('sightings table exists', cur.fetchone())
if target_person_id:
    cur.execute(
        'SELECT person_id,camera_id,lat,lng,label,timestamp,video_time_sec,similarity,job_id FROM sightings WHERE person_id=?',
        (target_person_id,),
    )
else:
    cur.execute(
        'SELECT person_id,camera_id,lat,lng,label,timestamp,video_time_sec,similarity,job_id FROM sightings WHERE camera_id=?',
        ('demo_corridor',),
    )
rows = cur.fetchall()
print('sqlite rows for query', len(rows), rows[:5])
conn.close()

print('VERIFICATION COMPLETE')
