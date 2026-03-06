import redis

# Use 'localhost' if running script from your Windows machine
# Use 'redis' if running inside a Docker container
try:
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    r.set('swarm_status', 'Blackboard is LIVE 🟢')
    print(f"Success: {r.get('swarm_status')}")
except Exception as e:
    print(f"Error: {e}")