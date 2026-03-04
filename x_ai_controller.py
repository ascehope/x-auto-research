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
        # コストパフォーマンスが良く速い最新安定モデルを指定
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def get_account_display_name(self, account_id: str) -> str:
        """
        @アカウントIDからX上の表示名（名前）を取得する
        """
        try:
            clean_username = account_id.lstrip("@")
            # ユーザー情報を取得
            user = self.client_v2.get_user(username=clean_username)
            if user and user.data:
                return user.data.name
            return account_id
        except Exception as e:
            print(f"アカウント名取得エラー ({account_id}): {e}")
            return account_id

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

        # アカウント指定検索の場合は from:ユーザー名 というクエリを使う
        if keyword and not keyword.startswith("from:"):
            # 先頭に @ がついている場合は削除しておく
            clean_username = keyword.lstrip("@")
            query = f'from:{clean_username} -is:retweet -is:reply'
            display_kw = f"@{clean_username}"
        else:
            query = f'{keyword} -is:retweet -is:reply'
            display_kw = keyword

        # 念のため、キーワードが空の場合は安全に空リストを返す
        if not keyword or keyword.strip() == "":
            print("検索対象アカウントが指定されていません。")
            return []

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
                metrics = tweet.public_metrics
                like_count = metrics.get('like_count', 0)
                retweet_count = metrics.get('retweet_count', 0)
                reply_count = metrics.get('reply_count', 0)
                quote_count = metrics.get('quote_count', 0)
                # v2 APIの仕様上 bookmark_count が取得できる場合は取得
                bookmark_count = metrics.get('bookmark_count', 0)
                
                tweet_url = f"https://twitter.com/i/web/status/{tweet.id}"
                results.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at.strftime("%Y-%m-%d %H:%M:%S") if tweet.created_at else "",
                    "like_count": like_count,
                    "retweet_count": retweet_count,
                    "reply_count": reply_count,
                    "quote_count": quote_count,
                    "bookmark_count": bookmark_count,
                    "url": tweet_url,
                    "keyword": display_kw
                })
            return results
        except Exception as e:
            print(f"ツイート検索エラー (keyword: {display_kw}): {e}")
            return []

    def generate_post_drafts_with_gemini(self, original_account: str, tweets_data: list[dict]) -> list[str]:
        """
        バズツイートのリストから傾向を分析し、要約と今日の投稿案3パターンを作成する
        戻り値のリスト構成: [要約, 速報案, 解説案, 煽り案]
        """
        if not tweets_data:
            return []

        # プロンプトに含めるため、ツイートのテキストといいね数をまとめる
        tweets_info = ""
        for i, t in enumerate(tweets_data, 1):
            tweets_info += f"{i}. いいね数: {t['like_count']}件\nテキスト: {t['text']}\n---\n"

        prompt = f"""
私はX（旧Twitter）でAI関連の最新情報を発信しているアカウントです。
注目しているインフルエンサー「{original_account}」が昨日投稿し、反響（いいね100〜300）を呼んだ以下のツイート群があります。

{tweets_info}

上記のツイート群の内容を読み込み、日本のAIユーザーに向けて以下の【4つの要素】を出力してください。
出力形式は必ず指定されたプレフィックスから始めてください。

【出力要素と条件】
[要約]: 元のツイートが英語等の場合は日本語に翻訳し、最新ツール情報やその話題の「一番の要点は何か」を1〜2文で簡潔に解説してください。
[速報]: いち早く新しいニュースやツールが出たことをシンプルに伝える、速報・ニューススタイルの投稿案（140字程度）。
[解説]: なぜそのAIツールや話題が凄いのか、仕事でどう使えるのか等を自分なりの意見を交えて深掘りする解説スタイルの投稿案（長文OK）。
[煽り]: 「このAIツール、もう使ってる？」など、フォロワーに問いかけてエンゲージメント（リプライ等）を促す煽りスタイルの投稿案。

※各投稿案には必要に応じて適切なハッシュタグ（#AI #ChatGPT など）を1〜2個添えてください。
"""
        try:
            response = self.model.generate_content(prompt)
            drafts_text = response.text.strip()
            
            # プレフィックスによるパース
            import re
            
            # 各要素を抽出するための正規表現
            summary_match = re.search(r'\[要約\]:?(.*?)(?=\[速報\]|$)', drafts_text, re.DOTALL)
            news_match = re.search(r'\[速報\]:?(.*?)(?=\[解説\]|$)', drafts_text, re.DOTALL)
            explain_match = re.search(r'\[解説\]:?(.*?)(?=\[煽り\]|$)', drafts_text, re.DOTALL)
            engaging_match = re.search(r'\[煽り\]:?(.*?)$', drafts_text, re.DOTALL)
            
            summary = summary_match.group(1).strip() if summary_match else "要約の抽出に失敗しました"
            news = news_match.group(1).strip() if news_match else ""
            explain = explain_match.group(1).strip() if explain_match else ""
            engaging = engaging_match.group(1).strip() if engaging_match else ""
            
            return [summary, news, explain, engaging]
                
        except Exception as e:
            error_msg = str(e)
            print(f"Gemini API (要約・投稿案生成) エラー: {error_msg}")
            return [f"エラーが発生しました: {error_msg[:100]}", "", "", ""]

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
