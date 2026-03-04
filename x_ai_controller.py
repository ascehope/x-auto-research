import os
import tweepy
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class XAIController:
    def __init__(self):
        # --- X API 認証 (v1.1: トレンド用, v2: 検索用) ---
        api_key = os.getenv("X_API_KEY")
        api_secret = os.getenv("X_API_KEY_SECRET")
        access_token = os.getenv("X_ACCESS_TOKEN")
        access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
        bearer_token = os.getenv("X_BEARER_TOKEN")

        if not all([api_key, api_secret, access_token, access_token_secret, bearer_token]):
            raise ValueError("X APIの環境変数が不足しています。")

        # v1.1 authentication (for trends)
        auth = tweepy.OAuth1UserHandler(
            api_key, api_secret, access_token, access_token_secret
        )
        self.api_v1 = tweepy.API(auth)

        # v2 authentication (for search)
        self.client_v2 = tweepy.Client(bearer_token=bearer_token)

        # --- Gemini API 認証 ---
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("Gemini APIの環境変数が設定されていません。")
        genai.configure(api_key=gemini_api_key)
        # 傾向分析等の複雑なタスクには pro モデルを使用
        self.model = genai.GenerativeModel('gemini-1.5-pro')

    def get_japan_trends(self) -> list[str]:
        """
        X API v1.1 を利用して日本のトレンド（WOEID: 23424856）を取得する
        """
        try:
            # 日本のWOEID
            JAPAN_WOEID = 23424856
            trends_result = self.api_v1.get_place_trends(id=JAPAN_WOEID)
            
            trends = []
            for trend in trends_result[0]["trends"]:
                trends.append(trend["name"])
            return trends
        except Exception as e:
            print(f"トレンド取得エラー: {e}")
            return []

    def extract_tech_keywords_with_gemini(self, trends: list[str]) -> list[str]:
        """
        トレンド一覧をGeminiに渡し、「AIやテクノロジー関連」のキーワードのみを自動抽出する
        """
        if not trends:
            return []

        prompt = f"""
以下のリストは現在の日本のXトレンドです。
この中から「AI（人工知能）、テクノロジー、IT、プログラミング、最新技術、ガジェット」に関連するキーワードのみを抽出してください。
関連するキーワードが無い場合は空のリストを返してください。
余計な説明は省き、カンマ区切りの文字列（例: ChatGPT,Python,生成AI）のみを出力してください。

[トレンド一覧]
{', '.join(trends)}
"""
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            if not result_text:
                return []
            
            # カンマ区切りなどで返されたテキストをリスト化
            extracted = [kw.strip() for kw in result_text.split(",") if kw.strip()]
            return extracted
        except Exception as e:
            print(f"Gemini API (キーワード抽出) エラー: {e}")
            return []

    def search_buzz_tweets(self, keyword: str, max_results: int = 500) -> list[dict]:
        """
        X API v2 を利用して、昨日のツイートを検索する。Paginatorで複数ページ検索対応。
        """
        from datetime import datetime, timezone, timedelta
        
        # JST(UTC+9)基準で昨日の0時〜23時59分を計算
        JST = timezone(timedelta(hours=+9), 'JST')
        now_jst = datetime.now(JST)
        yesterday_jst = now_jst - timedelta(days=1)
        
        start_time_jst = yesterday_jst.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time_jst = yesterday_jst.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        start_time = start_time_jst.astimezone(timezone.utc)
        end_time = end_time_jst.astimezone(timezone.utc)

        # キーワードが空等の場合はより広範なAI関連で検索
        if not keyword or keyword.strip() == "":
            query = '("AI" OR "ChatGPT" OR "生成AI" OR "LLM" OR "Claude" OR "プロンプト") -is:retweet'
            display_kw = "AI関連全般"
        else:
            query = f'({keyword}) -is:retweet'
            display_kw = keyword

        try:
            results = []
            for tweet in tweepy.Paginator(
                self.client_v2.search_recent_tweets,
                query=query,
                start_time=start_time,
                end_time=end_time,
                max_results=100,
                tweet_fields=['created_at', 'public_metrics', 'author_id']
            ).flatten(limit=max_results):
                like_count = tweet.public_metrics['like_count']
                tweet_url = f"https://twitter.com/i/web/status/{tweet.id}"
                results.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at.strftime("%Y-%m-%d %H:%M:%S") if tweet.created_at else "",
                    "like_count": like_count,
                    "url": tweet_url,
                    "keyword": display_kw
                })
            return results
        except Exception as e:
            print(f"ツイート検索エラー (keyword: {display_kw}): {e}")
            return []

    def generate_post_drafts_with_gemini(self, original_keyword: str, tweets_data: list[dict]) -> list[str]:
        """
        バズツイートのリストから傾向を分析し、今日の投稿案を3つ作成する
        """
        if not tweets_data:
            return []

        # プロンプトに含めるため、ツイートのテキストといいね数をまとめる
        tweets_info = ""
        for i, t in enumerate(tweets_data, 1):
            tweets_info += f"{i}. いいね数: {t['like_count']}件\nテキスト: {t['text']}\n---\n"

        prompt = f"""
私はX（旧Twitter）のアカウントを運用しています。
キーワード「{original_keyword}」について、最近以下のような投稿が反響（いいね100〜200）を呼んでいます。

{tweets_info}

上記のバズツイートの傾向、表現方法、トピックの切り口を分析してください。
そして、その分析に基づき、私が今日投稿するためのオリジナルで魅力的な「投稿案（ドラフト）」を**3つ**作成してください。

【条件】
- 出力はJSON形式などのプログラムで扱いやすい形式を使わず、「1. 」「2. 」「3. 」という番号付きでプレーンテキストで出力してください。
- ハッシュタグを含める場合は適切なものを1〜2個添えてください。
"""
        try:
            response = self.model.generate_content(prompt)
            # 生成されたテキストを「1.」「2.」等のプレフィックスを目安に分割
            drafts_text = response.text.strip()
            
            # 簡易的な分割処理（適宜調整）
            import re
            parts = re.split(r'\n\d+\.\s*', '\n' + drafts_text)[1:]
            
            # 分割に失敗した・あるいは3つない場合は、改行でざっくり分けるかそのまま返すフォールバック
            if len(parts) >= 3:
                return [p.strip() for p in parts[:3]]
            else:
                return [drafts_text, "", ""]
                
        except Exception as e:
            print(f"Gemini API (投稿案生成) エラー: {e}")
            return ["エラーが発生しました", "", ""]

# テスト用コード（直接実行された場合のみ）
if __name__ == "__main__":
    try:
        controller = XAIController()
        # トレンド取得テスト
        trends = controller.get_japan_trends()
        print(f"取得したトレンドの一部: {trends[:5]}")
        
        # キーワード抽出テスト
        tech_keywords = controller.extract_tech_keywords_with_gemini(trends)
        print(f"自動抽出されたテック系キーワード: {tech_keywords}")
    except Exception as e:
        print(f"Error: {e}")
