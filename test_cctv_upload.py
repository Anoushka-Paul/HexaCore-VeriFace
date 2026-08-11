import requests, time, json
BASE='http://127.0.0.1:8000'
TOKEN=None
# login
r = requests.post(f'{BASE}/auth/login', data={'username':'autouser','password':'autopass'})
r.raise_for_status()
TOKEN = r.json()['access_token']
headers={'Authorization': f'Bearer {TOKEN}'}
# upload
files={'video':('demo_cctv_simulated.mp4', open('demo_cctv_simulated.mp4','rb'),'video/mp4'), 'target':('fictional_suspect_reference.jpg', open('demo_assets/fictional_suspect_reference.jpg','rb'),'image/jpeg')}
r = requests.post(f'{BASE}/cctv-scan', headers=headers, files=files, data={'camera_id':'demo_corridor','interval':'0.5','threshold':'0.45'})
print('initial response', r.status_code, r.text)
job = r.json().get('job_id')
print('job:', job)
# poll
for _ in range(60):
    time.sleep(1)
    r = requests.get(f'{BASE}/cctv-jobs/{job}/results', headers=headers)
    print('poll', r.status_code, r.text[:200])
    j = r.json()
    if j.get('status')=='done' or j.get('status')=='failed':
        print('final:', json.dumps(j, indent=2))
        break
