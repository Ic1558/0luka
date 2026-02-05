import os
import redis
from flask import Flask, render_template_string

REDIS_URL = os.getenv("REDIS_URL")
r = redis.from_url(REDIS_URL, decode_responses=True)

app = Flask(__name__)

TEMPLATE = """
<!doctype html>
<title>Lisa Monitor</title>
<h2>🌐 Real-Time Lisa Monitor (Last 20 logs)</h2>
<pre>
{% for log_id, log in logs %}
{{ loop.index }}. {{ log_id }} => {{ log }}
{% endfor %}
</pre>
<meta http-equiv="refresh" content="3">
"""

@app.route("/")
def home():
    logs = r.xrevrange("lisa:response_log", count=20)
    return render_template_string(TEMPLATE, logs=logs)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5080)

