# Deployment Information

## Public URL
https://2a202600204-day12-production.up.railway.app

## Platform
Railway

## Test Commands

### Health Check
```bash
curl https://2a202600204-day12-production.up.railway.app/health
# Expected: 200 with status payload
```

### Readiness Check
```bash
curl https://2a202600204-day12-production.up.railway.app/ready
# Expected: 200 when Redis ready, otherwise 503
```

### API Test (with authentication)
```bash
curl -X POST https://2a202600204-day12-production.up.railway.app/ask \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
```

### Authentication Required Test
```bash
curl -X POST https://2a202600204-day12-production.up.railway.app/ask \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
# Expected: 401
```

### Rate Limiting Test
```bash
for i in {1..15}; do
  curl -X POST https://2a202600204-day12-production.up.railway.app/ask \
    -H "X-API-Key: YOUR_KEY" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "rate-test", "question": "test"}'
done
# Expected: eventually returns 429
```
