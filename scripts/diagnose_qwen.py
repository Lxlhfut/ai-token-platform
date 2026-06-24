from openai import OpenAI

client = OpenAI(
    api_key="sk-74aab4b4e384b61260fd16f8972591a1f706910c9d59d225",
    base_url="http://120.26.162.115/v1"
)

response = client.chat.completions.create(
    model="deepseek-v4-pro",
    messages=[{"role": "user", "content": "你是谁"}]
)
print(response.choices[0].message.content)