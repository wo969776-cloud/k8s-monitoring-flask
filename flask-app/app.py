import time
import threading
from flask import Flask, jsonify
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

app = Flask(__name__)

# ── Prometheus 커스텀 메트릭 ──────────────────────────────────
REQUEST_COUNT = Counter(
    'flask_request_count',
    'Total request count',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'flask_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

# OOMKilled 재현용: 전역 리스트에 계속 append
_memory_leak_store = []


def track(endpoint):
    """데코레이터 없이 쓸 수 있는 메트릭 래퍼"""
    def decorator(f):
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                resp = f(*args, **kwargs)
                status = resp[1] if isinstance(resp, tuple) else 200
                REQUEST_COUNT.labels(
                    method='GET', endpoint=endpoint, status=str(status)
                ).inc()
                return resp
            except Exception as e:
                REQUEST_COUNT.labels(
                    method='GET', endpoint=endpoint, status='500'
                ).inc()
                raise e
            finally:
                REQUEST_DURATION.labels(
                    method='GET', endpoint=endpoint
                ).observe(time.time() - start)
        wrapper.__name__ = f.__name__
        return wrapper
    return decorator


# ── 엔드포인트 ────────────────────────────────────────────────

@app.route('/health')
@track('/health')
def health():
    return jsonify({"status": "ok"}), 200


@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}


@app.route('/api/incidents')
@track('/api/incidents')
def incidents():
    data = [
        {"id": 1, "type": "OOMKilled",    "status": "resolved", "pod": "flask-app-xxx"},
        {"id": 2, "type": "Ingress502",   "status": "resolved", "pod": "flask-app-yyy"},
        {"id": 3, "type": "NodeNotReady", "status": "active",   "pod": "N/A"},
    ]
    return jsonify({"incidents": data}), 200


@app.route('/error')
@track('/error')
def error():
    # 5xx 알람 트리거용
    return jsonify({"error": "intentional error for alerting test"}), 500


@app.route('/cpu-load')
@track('/cpu-load')
def cpu_load():
    # 3초간 CPU 바쁘게 돌리기
    deadline = time.time() + 3
    while time.time() < deadline:
        _ = sum(i * i for i in range(10000))
    return jsonify({"status": "cpu-load done"}), 200


@app.route('/memory-leak')
@track('/memory-leak')
def memory_leak():
    # 호출할 때마다 ~10MB씩 누수 — OOMKilled 재현용
    chunk = ' ' * (10 * 1024 * 1024)
    _memory_leak_store.append(chunk)
    used_mb = len(_memory_leak_store) * 10
    return jsonify({
        "status": "leaked",
        "total_leaked_mb": used_mb,
        "chunks": len(_memory_leak_store)
    }), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
