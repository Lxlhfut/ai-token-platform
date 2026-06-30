from openai import OpenAI

client = OpenAI(
<<<<<<< HEAD
    api_key="sk-616ff4afd3b6e05e637e5f1dd4574e1ee1105b7683913a85",
    base_url="http://127.0.0.1:8000/v1"
)

response = client.chat.completions.create(
    model="meta-llama",
=======
    api_key="sk-74aab4b4e384b61260fd16f8972591a1f706910c9d59d225",
    base_url="http://120.26.162.115/v1"
)

response = client.chat.completions.create(
    model="deepseek-v4-pro",
>>>>>>> 9917b3d52cb41738996b4ce0f28b48cbbf2f6a03
    messages=[{"role": "user", "content": "你是谁"}]
)
print(response.choices[0].message.content)