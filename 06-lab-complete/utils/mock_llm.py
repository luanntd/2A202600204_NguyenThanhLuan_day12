"""
Mock LLM — dùng cho lab khi chưa có API key thật.
"""
import random
import time


MOCK_RESPONSES = {
    "default": [
        "Đây là câu trả lời từ AI agent (mock).",
        "Agent đang hoạt động tốt! (mock response)",
        "Tôi là AI agent được deploy lên cloud.",
    ],
    "docker": ["Container là cách đóng gói app để chạy ở mọi nơi."],
    "deploy": ["Deployment là quá trình đưa code từ máy bạn lên server để người khác dùng được."],
    "health": ["Agent đang hoạt động bình thường. All systems operational."],
}


def ask(question: str, delay: float = 0.1) -> str:
    time.sleep(delay + random.uniform(0, 0.05))

    question_lower = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in question_lower:
            return random.choice(responses)

    return random.choice(MOCK_RESPONSES["default"])
