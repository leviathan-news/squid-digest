from squid_digest.clients import LeviathanNewsClient
import json

client = LeviathanNewsClient()

result = client.fetch_top_news(limit=10)

with open("result.json", "w") as f:
    json.dump(result, f)
