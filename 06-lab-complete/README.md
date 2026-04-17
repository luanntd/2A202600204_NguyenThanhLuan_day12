# Lab 12 — Complete Production Agent

Kết hợp TẤT CẢ những gì đã học trong 1 project hoàn chỉnh.

## Checklist Deliverable

- [x] Dockerfile (multi-stage, < 500 MB)
- [x] docker-compose.yml (agent + redis)
- [x] .dockerignore
- [x] Health check endpoint (`GET /health`)
- [x] Readiness endpoint (`GET /ready`)
- [x] API Key authentication
- [x] Rate limiting
- [x] Cost guard
- [x] Config từ environment variables
- [x] Structured logging
- [x] Graceful shutdown
- [x] Redis-backed stateless conversation history
- [x] JWT endpoint (bonus)
- [x] Public URL ready (Railway / Render config)

---

## Cấu Trúc

```
06-lab-complete/
├── app/
│   ├── main.py         # Entry point — kết hợp tất cả
│   ├── config.py       # 12-factor config
│   ├── auth.py         # API Key + JWT
│   ├── rate_limiter.py # Rate limiting
│   └── cost_guard.py   # Budget protection
├── Dockerfile          # Multi-stage, production-ready
├── docker-compose.yml  # Full stack
├── railway.toml        # Deploy Railway
├── render.yaml         # Deploy Render
├── .env.example        # Template
├── .dockerignore
└── requirements.txt
```

---

## Chạy Local

```bash
# 1. Setup
cp .env.example .env

# 2. Chạy với Docker Compose
docker compose up

# 3. Test
curl http://localhost/health

# 4. Lấy API key từ .env, test endpoint
API_KEY=$(grep AGENT_API_KEY .env | cut -d= -f2)
curl -H "X-API-Key: $API_KEY" \
     -X POST http://localhost/ask \
     -H "Content-Type: application/json" \
     -d '{"user_id": "test-user", "question": "What is deployment?"}'

# 5. Test conversation history
curl -H "X-API-Key: $API_KEY" \
     -X POST http://localhost/ask \
     -H "Content-Type: application/json" \
     -d '{"user_id": "alice", "question": "My name is Alice"}'

curl -H "X-API-Key: $API_KEY" \
     -X POST http://localhost/ask \
     -H "Content-Type: application/json" \
     -d '{"user_id": "alice", "question": "What is my name?"}'
```

### Bonus JWT

```bash
# Get token
curl -X POST http://localhost/token \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'

# Use token
TOKEN="<paste-token>"
curl -X POST http://localhost/ask \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "jwt-user", "question": "hello"}'
```

---

## Deploy Railway (< 5 phút)

```bash
# Cài Railway CLI
npm i -g @railway/cli

# Login và deploy
railway login
railway init
railway variables set OPENAI_API_KEY=sk-...
railway variables set AGENT_API_KEY=your-secret-key
railway up

# Nhận public URL!
railway domain
```

---

## Deploy Render

1. Push repo lên GitHub
2. Render Dashboard → New → Blueprint
3. Connect repo → Render đọc `render.yaml`
4. Set secrets: `OPENAI_API_KEY`, `AGENT_API_KEY`
5. Deploy → Nhận URL!

---

## Kiểm Tra Production Readiness

```bash
python check_production_ready.py
```

Script này kiểm tra tất cả items trong checklist và báo cáo những gì còn thiếu.

## Notes quan trọng

- `/ask` yêu cầu `user_id` trong payload để rate limit + budget + history hoạt động theo từng user.
- Rate limit mặc định: `10 req/min` mỗi user (`RATE_LIMIT_PER_MINUTE`).
- Cost guard mặc định: `$10/tháng/user` (`MONTHLY_BUDGET_USD`).
