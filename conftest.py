import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# 測試一律走離線規則路，不打 API。只 pop 環境變數不夠——
# _load_dotenv 會把 .env 重新讀回來，所以要用明確的強制離線旗標。
os.environ.pop("OPENAI_API_KEY", None)
os.environ["HONGYU_FORCE_OFFLINE"] = "1"
