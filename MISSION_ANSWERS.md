# Day 12 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. Hardcoded secrets trong source code.
2. Port hardcode, không đọc từ environment.
3. Không có health check endpoint cho orchestrator.
4. Không có readiness check cho dependency health.
5. Không có graceful shutdown khi nhận SIGTERM.
6. Logging chưa structured, khó parse trên cloud logs.
7. Config và runtime behavior không tách rõ dev/prod.

### Exercise 1.3: Comparison table
| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config | Hardcode trong file | Environment variables | Tránh commit secrets, dễ đổi theo môi trường |
| Health check | Thiếu hoặc đơn giản | `/health` và `/ready` đầy đủ | Platform tự restart và routing đúng instance healthy |
| Logging | `print()` đơn lẻ | JSON structured logs | Dễ filter/alert/trace trên cloud |
| Shutdown | Dừng đột ngột | Graceful shutdown | Giảm rớt request khi deploy/scale down |
| Security | Không auth hoặc auth đơn giản | API key bắt buộc, thêm JWT bonus | Giảm abuse và rò rỉ chi phí |
| State | In-memory | Redis-backed stateless | Scale ngang nhiều instance vẫn giữ hội thoại |

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. Base image: `python:3.11-slim`.
2. Working directory: `/app`.

### Exercise 2.3: Image size comparison
- Develop: chưa đo được do Docker Hub unauthenticated rate limit khi pull `python:3.11` (HTTP 429).
- Production: `309MB`.
- Difference: multi-stage + slim base giúp giảm đáng kể kích thước image.

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment
- URL: https://2a202600204-day12-production.up.railway.app
- Screenshot: `screenshots/`.

### Exercise 3.2: Railway vs Render config
- Railway (`railway.toml`): tập trung `startCommand`, healthcheck và restart policy.
- Render (`render.yaml`): khai báo service blueprint + env vars + region/plan.
- Cả hai đều cần set secrets/env vars từ dashboard để tránh hardcode.

## Part 4: API Security

### Exercise 4.1-4.3: Test results
1. Không gửi auth header: `/ask` trả về `401`.
2. Gửi `X-API-Key` hợp lệ: `/ask` trả `200`.
3. Gửi quá limit: trả `429`.
4. Có thêm endpoint `/token` và Bearer token flow (bonus).

### Exercise 4.4: Cost guard implementation
- Dùng Redis lưu spending theo key tháng: `budget:{user_id}:{YYYY-MM}`.
- Ước lượng token input/output theo số từ để tính cost.
- Từ chối request với `402` khi vượt `MONTHLY_BUDGET_USD`.
- TTL key > 1 tháng để tự cleanup nhẹ.

## Part 5: Scaling & Reliability

### Exercise 5.1-5.5: Implementation notes
1. `/health` trả trạng thái sống của service và metadata runtime.
2. `/ready` ping Redis, fail thì trả `503`.
3. Stateless design: history conversation nằm trong Redis list, không giữ ở RAM.
4. Docker Compose có Nginx + Agent + Redis để test LB local.
5. Có graceful shutdown qua lifespan + signal handler.
