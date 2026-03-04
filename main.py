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
        
        # 2. キーワードの取得と結合
        print("\n--- 1. キーワード取得・抽出 ---")
        manual_keywords = sheets_api.get_manual_keywords()
        print(f"手動設定キーワード: {manual_keywords}")
        
        trends = xai_api.get_japan_trends()
        print(f"現在の日本のXトレンド: {len(trends)}件取得")
        
        trend_keywords = xai_api.extract_tech_keywords_with_gemini(trends)
        print(f"Geminiによる抽出トレンドキーワード: {trend_keywords}")
        
        # リストを結合して重複を排除
        all_keywords = list(set(manual_keywords + trend_keywords))
        print(f"最終検索キーワード ({len(all_keywords)}件): {all_keywords}")
        
        # 3. 各キーワードでバズツイートを検索・フィルタリングし、投稿案を生成
        print("\n--- 2. バズツイート検索と投稿案の生成 ---")
        
        research_data_to_append = []
        draft_data_to_append = []
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")

        for kw in all_keywords:
            if not kw.strip():
                continue
                
            print(f"\n[Keyword: {kw}] を検索しています...")
            tweets = xai_api.search_buzz_tweets(kw, max_results=50) # APIコスト制限
            
            # 要件「いいね数が100〜200の範囲」の投稿のみに絞り込む
            filtered_tweets = [t for t in tweets if 100 <= t['like_count'] <= 200]
            print(f"検索結果: {len(tweets)}件 -> 条件(いいね100~200)合致: {len(filtered_tweets)}件")
            
            if not filtered_tweets:
                print(f"  条件に合うツイートが無かったためスキップします。")
                continue
                
            # リサーチ結果の記録用データを構築
            for t in filtered_tweets:
                # [取得日時, 投稿テキスト, URL, いいね数]
                row = [now_str, t['text'], t['url'], t['like_count']]
                research_data_to_append.append(row)
                
            print(f"  投稿案 (ドラフト) を生成中...")
            drafts = xai_api.generate_post_drafts_with_gemini(kw, filtered_tweets)
            
            # ドラフト結果の記録用データを構築
            # [作成日, 元キーワード, 投稿案1, 投稿案2, 投稿案3]
            draft_row = [date_str, kw] + drafts
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
