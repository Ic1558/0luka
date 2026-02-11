#!/usr/bin/env python3
"""
Test sending task to GG Core via Redis
"""
from redis_local import get_local_redis
import json
import time

def test_ggcore_task():
    r = get_local_redis()
    
    # สร้าง test task
    task = {
        'id': f'test_ggcore_{int(time.time())}',
        'type': 'auto_task',
        'message': 'Hello GG Core, please process this automation task',
        'from': 'Claude_Test',
        'timestamp': time.time()
    }
    
    print(f"📤 Sending task to GG Core: {task['id']}")
    
    # ส่งไป GG Core
    r.lpush('task:auto', json.dumps(task))
    
    print("⏳ Waiting for GG Core response...")
    
    # รอ response จาก GG Core
    start_time = time.time()
    while time.time() - start_time < 30:
        response = r.brpop(f"response:gg:{task['id']}", timeout=5)
        if response:
            channel, message = response
            result = json.loads(message.decode())
            print(f"✅ GG Core responded: {result}")
            return True
        time.sleep(1)
    
    print("❌ GG Core timeout - no response")
    return False

if __name__ == "__main__":
    print("🧪 Testing GG Core Communication...")
    success = test_ggcore_task()
    print(f"Result: {'✅ Success' if success else '❌ Failed'}")
