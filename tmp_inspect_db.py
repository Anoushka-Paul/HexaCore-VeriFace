import sqlite3
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
DB = BASE / 'audit.db'
print('DB exists', DB.exists())
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute('SELECT name FROM sqlite_master WHERE type="table" AND name="sightings"')
print('sightings table exists', cur.fetchone())
cur.execute('SELECT count(*) FROM sightings')
print('sightings count', cur.fetchone()[0])
cur.execute('SELECT person_id,camera_id,lat,lng,label,timestamp,video_time_sec,similarity,job_id FROM sightings ORDER BY id DESC LIMIT 20')
rows = cur.fetchall()
print('rows count', len(rows))
for row in rows:
    print(row)
conn.close()
print('jobs:')
for job_dir in sorted((BASE / 'cctv_jobs').glob('*')):
    if job_dir.is_dir():
        print('job', job_dir.name)
        status_path = job_dir / 'status.json'
        results_path = job_dir / 'results.json'
        if status_path.exists():
            print(' status', json.loads(status_path.read_text(encoding='utf-8')))
        if results_path.exists():
            x = json.loads(results_path.read_text(encoding='utf-8'))
            print(' results status', x.get('status'), 'matches', len(x.get('matches', [])), 'events', len(x.get('events', [])))
            if 'input' in x:
                print(' input video', x['input'].get('video'), 'camera_id', x['input'].get('camera_id'), 'camera_location', x['input'].get('camera_location'))
            if x.get('events'):
                print(' first event', x['events'][0].get('camera_location'), x['events'][0].get('best_similarity'))
