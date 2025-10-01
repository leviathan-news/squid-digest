from django.test import TestCase
from digest.clients import LeviathanNewsClient
import json


class LeviathanTestCase(TestCase):
    def test_fetch_top_news(self):
        client = LeviathanNewsClient()
        news = client.fetch_top_news(limit=10)
        with open("news.json", "w") as f:
            json.dump(news, f)
        self.assertEqual(len(news), 10)
        self.assertIsInstance(news[0], dict)
        self.assertIn("headline", news[0])
        self.assertIn("source", news[0])
        self.assertIn("url", news[0])
        self.assertIn("tags", news[0])
