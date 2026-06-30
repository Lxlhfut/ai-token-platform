from openai import OpenAI

client = OpenAI(
    api_key="sk-616ff4afd3b6e05e637e5f1dd4574e1ee1105b7683913a85",
    base_url="http://127.0.0.1:8000/v1"
)

response = client.chat.completions.create(
    model="meta-llama",
    messages=[{"role": "user", "content": "你是谁"}]
)
print(response.choices[0].message.content)