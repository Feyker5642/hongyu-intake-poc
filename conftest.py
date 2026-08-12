import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 測試一律走離線規則路，不打 API
os.environ.pop("OPENAI_API_KEY", None)
