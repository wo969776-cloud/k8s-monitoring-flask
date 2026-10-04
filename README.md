# k8s-monitoring-flask

장애 재현용 엔드포인트를 가진 Flask 앱과, 이를 GitOps로 배포하기 위한 Kubernetes manifest 저장소입니다.
Prometheus 커스텀 메트릭(`flask_request_count`, `flask_request_duration_seconds`)을 `/metrics`로 노출합니다.

관련 레포(클러스터 인프라·Helm values·진단 스냅샷 수집기): [k8s-monitoring-infra](https://github.com/wo969776-cloud/k8s-monitoring-infra)

## 디렉터리 구조

```
.github/workflows/
└── ci-cd.yaml                 # 이미지 빌드·푸시 → manifest 이미지 태그 갱신
flask-app/
├── app.py                     # Flask 앱 (엔드포인트 + Prometheus 메트릭)
├── Dockerfile                 # gunicorn 단일 워커로 실행
├── requirements.txt
└── k8s/
    ├── manifests.yaml         # Deployment / Service / Ingress (namespace: default)
    └── k8s-dashboards/        # Grafana 대시보드 ConfigMap 4종 (namespace: monitoring, label grafana_dashboard: "1")
        ├── application-dashboard-configmap.yaml
        ├── cluster-dashboard-configmap.yaml
        ├── data-layer-dashboard-configmap.yaml
        └── kubernetes-dashboard-configmap.yaml
```

## 엔드포인트

| 경로 | 용도 |
|---|---|
| `/health` | 헬스체크. liveness·readiness probe가 사용 |
| `/metrics` | Prometheus 메트릭 노출 |
| `/api/incidents` | 코드에 하드코딩된 샘플 incident 목록(JSON) 응답 |
| `/cpu-load` | 요청당 약 3초간 CPU 연산 — CPU 과부하 재현용 |
| `/memory-leak` | 호출할 때마다 약 5MB를 전역 리스트에 누적 — OOMKilled 재현용 |
| `/error` | 항상 HTTP 500 응답 — 5xx 알람 트리거용 |

## CI/CD 흐름

`main` 브랜치에 push하면 `.github/workflows/ci-cd.yaml`이 실행됩니다.

1. `flask-app/`을 빌드해 Docker Hub에 `flask-observability:latest`, `flask-observability:<commit SHA>` 태그로 푸시
2. `sed`로 `flask-app/k8s/manifests.yaml`의 image를 `<commit SHA>` 태그로 갱신
3. github-actions 계정으로 manifest 변경을 커밋·푸시 (`ci: update image tag to <SHA>`)
4. ArgoCD가 manifest 변경을 감지해 클러스터에 자동 sync

ArgoCD Application 정의는 이 레포에 포함되어 있지 않습니다.

## gunicorn 워커를 1개로 둔 이유

`Dockerfile` 주석 기준: `/memory-leak` 재현 시 누수 데이터가 전역 리스트에 쌓이는데, 워커가 여러 개면 요청이 워커별로 나뉘어 전역 상태가 유지되지 않습니다. 그래서 `--workers 1`로 실행합니다.
