# 배포

`deploy/docker-compose.yml` 하나로 전체 스택을 띄웁니다. 같은 구성이 노트북, 사내 서버(on-premise), 클라우드 VM에서 그대로 동작하며, 달라지는 것은 **어떤 LLM을 쓰느냐** 뿐입니다.

```
브라우저 ──▶ web (nginx: 정적 UI + /api 프록시, SSE 버퍼링 off)
               │
               ▼
            server (FastAPI · LangGraph · 마이그레이션 자동 적용)
            │      │        │
            ▼      ▼        ▼
       postgres  qdrant   LLM: Ollama(스택 내부 / 호스트) 또는 Gemini·OpenAI·Anthropic
```

| 서비스 | 역할 | 데이터 |
|---|---|---|
| `web` | React 빌드를 서빙하고 `/api`를 server로 프록시 | — |
| `server` | API, 에이전트 실행, 시작 시 Alembic 마이그레이션 | `server_data`(업로드), `model_cache`(리랭커 모델) |
| `postgres` | 메타데이터 + 대화 기록(LangGraph checkpointer) | `postgres_data` |
| `qdrant` | 벡터 검색 | `qdrant_data` |
| `ollama` *(profile)* | 로컬 LLM·임베딩 — 외부 API 없이 운영할 때 | `ollama_models` |

이 스택은 프로젝트 이름(`ragkit-stack`)과 볼륨이 분리되어 있어, 루트의 개발용 구성(SQLite + `../docker-compose.yml`)의 데이터를 건드리지 않습니다.

## 빠른 시작

```bash
cp deploy/.env.example deploy/.env      # JWT_SECRET_KEY, 비밀번호 설정
docker compose -f deploy/docker-compose.yml up -d --build
open http://localhost:8080              # admin@example.com / INITIAL_ADMIN_PASSWORD
```

## LLM 선택

`deploy/.env`에서 하나를 고릅니다. 에이전트별로는 Agent Settings 화면에서 다시 바꿀 수 있습니다.

| 방식 | 설정 | 적합한 환경 |
|---|---|---|
| 스택 내부 Ollama | `--profile ollama`로 기동. 첫 기동 때 `nomic-embed-text`와 `OLLAMA_CHAT_MODEL`을 내려받음 | 폐쇄망·사내 서버(GPU) |
| 호스트의 Ollama | `OLLAMA_BASE_URL=http://host.docker.internal:11434` | 개발 머신, Apple Silicon |
| 호스팅 API | `LLM_PROVIDER=google`, `LLM_MODEL=gemini-3.5-flash`, `GOOGLE_API_KEY=…` | 클라우드 |

임베딩은 Ollama(`nomic-embed-text`)를 쓰므로, 호스팅 API로 채팅하더라도 Ollama 하나는 필요합니다.

NVIDIA GPU가 있는 리눅스 서버에서는 `docker-compose.gpu.yml`을 겹쳐 Ollama에 GPU를 붙입니다:

```bash
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.gpu.yml --profile ollama up -d
```

## 알아둘 것

- **첫 요청이 느립니다.** 리랭커(`BAAI/bge-reranker-base`, 약 1GB)를 첫 검색 때 HuggingFace에서 내려받습니다. `model_cache` 볼륨에 남으므로 이후에는 즉시 로드됩니다. 로컬 검증에서 첫 응답 125초, 두 번째 6초였습니다.
- **이미지 크기.** server 이미지는 약 2.6GB입니다. 리눅스에서는 CPU 전용 torch를 쓰도록 `pyproject.toml`에 설정해 두었습니다(기본 PyPI 휠은 CUDA를 포함해 약 10GB).
- **마이그레이션.** server가 시작할 때 `alembic upgrade head`를 실행합니다. CI가 매 커밋마다 Postgres에서 upgrade → downgrade → upgrade를 검증합니다.

## 백업

```bash
# Postgres (메타데이터 + 대화 기록)
docker compose -f deploy/docker-compose.yml exec postgres pg_dump -U ragkit ragkit > ragkit-$(date +%F).sql
# Qdrant (벡터) — 스냅샷 API
docker compose -f deploy/docker-compose.yml exec server \
  python -c "import urllib.request as u; print(u.urlopen(u.Request('http://qdrant:6333/collections/documents/snapshots', method='POST')).read())"
```

벡터는 원본 문서에서 다시 만들 수 있으므로, 반드시 지켜야 하는 것은 Postgres와 `server_data`(업로드 원본)입니다.

## AWS

가장 단순한 구성은 **EC2 한 대 + 이 compose**입니다. 트래픽이 커지면 web/server를 ECS로, postgres를 RDS로, 업로드를 S3(`storage.kind: s3`, 이미 지원)로 옮기는 순서로 확장합니다.

| 용도 | 인스턴스 | 비고 |
|---|---|---|
| 호스팅 API로 채팅 | `t4g.xlarge` (Graviton, arm64) | 임베딩용 Ollama만 CPU로 실행 |
| 로컬 LLM까지 직접 | `g5.xlarge` (NVIDIA A10G) | 위 GPU 설정 사용 |

Graviton(arm64)을 권장하는 이유: 이 이미지는 arm64에서 로컬 검증되었고, 같은 성능에서 더 저렴합니다.

`aws/user-data.sh`는 Amazon Linux 2023 인스턴스를 만들 때 넣으면 Docker 설치부터 스택 기동까지 수행합니다. 보안 그룹은 80(또는 8080)만 열고, TLS는 앞단 ALB나 Caddy에서 종료하는 것을 권장합니다.

> 검증 범위: 이 스택은 로컬 Docker(arm64)에서 로그인 → 문서 업로드·인덱싱 → nginx 경유 SSE 채팅 → Postgres 대화 기록 복원까지 검증했습니다. AWS 절차는 문서화했지만 실제 AWS 계정에서는 실행해 보지 않았습니다.
