import redis
import json
import time

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

while True:
    # 1. Dërgo "Heartbeat" (Kjo do ta bëjë statusin 'Alive')
    r.set("heartbeat:Scout", "online")
    
    # 2. Dërgo një detyrë në "Blackboard"
    tasks = [{"Agent": "Scout", "Task": "Scanning Area", "Status": "Active"}]
    r.set("blackboard", json.dumps(tasks))
    
    time.sleep(5) # Përditëso çdo 5 sekonda