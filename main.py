import sys
import datetime
from sheets_controller import GoogleSheetsController
from x_ai_controller import XAIController

def main():
    print("=== 自動リサーチ＆投稿案作成システム 開始 ===")
    
    try:
        # 1. 各コントローラーの初期化
        print("初期化中...")
        sheets_api = GoogleSheetsController()
        xai_api = XAIController()
        
        # 2. 対象アカウント名の取得と設定
        print("\n--- 1. アカウントリスト取得・設定 ---")
        # 設定シートのA列をアカウントIDとみなして取得
        manual_keywords = sheets_api.get_manual_keywords()
        print(f"設定シートから取得したアカウントリスト: {manual_keywords}")
        
        target_accounts = [acc for acc in manual_keywords if acc.strip()]
        
        if not target_accounts:
            print("設定シートに検索対象のアカウント（@ID）が入力されていません。終了します。")
            return
            
        print(f"最終検索対象アカウント: {target_accounts}")
        
        # 3. 各キーワードでバズツイートを検索・フィルタリングし、投稿案を生成
        print("\n--- 2. 昨日のAI関連バズツイート検索と投稿案の生成 ---")
        
        research_data_to_append = []
        draft_data_to_append = []
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        for account in target_accounts:
            display_name = account
            print(f"\n[Account: {display_name}] が昨日投稿したツイートを検索しています...")
            
            # 最大500件まで（ただし1個人の1日のツイートなので実際は数件〜数十件）
            tweets = xai_api.search_buzz_tweets(account, max_results=500)
            
            # 指定アカウントの全ツイートを対象にするためフィルタを撤廃
            filtered_tweets = tweets
            
            # いいね数が多い順に並び替え、上位のものを優先して分析に回す
            filtered_tweets = sorted(filtered_tweets, key=lambda x: x['like_count'], reverse=True)
            
            print(f"検索結果: {len(tweets)}件取得 (いいね数降順で処理)")
            
            if not filtered_tweets:
                print(f"  昨日のツイートが無かったためスキップします。")
                continue
                
            # リサーチ結果の記録用データを構築
            for t in filtered_tweets:
                # [取得日時, 元アカウント, 投稿テキスト, URL, いいね数, リポスト数(RT+引用), 返信数, 保存数]
                total_reposts = t['retweet_count'] + t['quote_count']
                row = [now_str, account, t['text'], t['url'], t['like_count'], total_reposts, t['reply_count'], t['bookmark_count']]
                research_data_to_append.append(row)
                
            print(f"  話題の要約と投稿案 (ドラフト) を生成中...")
            # Geminiに全部渡すとノイズになり文字数制限に引っかかるリスクがあるため、いいね上位最大5件に絞って渡す
            top_tweets_for_gemini = filtered_tweets[:5]
            drafts = xai_api.generate_post_drafts_with_gemini(display_name, top_tweets_for_gemini)
            
            # ドラフト結果の記録用データを構築
            # [作成日, 元アカウント, 要約, 案1(速報), 案2(解説), 案3(煽り)]
            draft_row = [date_str, display_name] + drafts
            draft_data_to_append.append(draft_row)

        # 4. スプレッドシートへの記録処理
        print("\n--- 3. スプレッドシートへの記録 ---")
        if research_data_to_append:
            sheets_api.append_research_results(research_data_to_append)
        else:
            print("記録するリサーチデータがありませんでした。")
            
        if draft_data_to_append:
            sheets_api.append_draft_results(draft_data_to_append)
        else:
            print("記録するドラフトデータがありませんでした。")

        print("\n=== システム正常終了 ===")
        
    except Exception as e:
        print(f"\n[ERROR] 実行中にエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
