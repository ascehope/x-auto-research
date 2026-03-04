import os
import json
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

class GoogleSheetsController:
    def __init__(self):
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.client = self._authenticate()
        self.spreadsheet_key = os.getenv("SPREADSHEET_KEY")
        if not self.spreadsheet_key:
            raise ValueError("環境変数 SPREADSHEET_KEY が設定されていません。")
        self.sheet = self.client.open_by_key(self.spreadsheet_key)

    def _authenticate(self):
        """
        環境変数に設定されたJSON情報から認証を行う
        """
        credentials_json_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not credentials_json_path:
            raise ValueError("環境変数 GOOGLE_APPLICATION_CREDENTIALS が設定されていません。")

        # ファイルパスが指定されているか、JSON文字列が直接指定されているかを判定
        if os.path.exists(credentials_json_path):
            credentials = Credentials.from_service_account_file(
                credentials_json_path, scopes=self.scopes
            )
        else:
            try:
                # GitHub Actions などを考慮し、JSON文字列を直接パースする
                creds_dict = json.loads(credentials_json_path)
                credentials = Credentials.from_service_account_info(
                    creds_dict, scopes=self.scopes
                )
            except json.JSONDecodeError:
                raise ValueError("GOOGLE_APPLICATION_CREDENTIALS には有効なファイルパスまたはJSON文字列を指定してください。")
        
        return gspread.authorize(credentials)

    def get_manual_keywords(self) -> list[str]:
        """
        「設定シート」のA2以降から手動設定されたキーワードのリストを取得する
        """
        try:
            worksheet = self.sheet.worksheet("設定")
            # A列のすべての値を取得
            values = worksheet.col_values(1)
            # A1はヘッダー（「検索キーワード」等）なので除外、空文字も除外
            keywords = [val.strip() for val in values[1:] if val.strip()]
            return keywords
        except gspread.exceptions.WorksheetNotFound:
            print("エラー: '設定' シートが見つかりません。")
            return []

    def append_research_results(self, research_data: list[list]):
        """
        「リサーチ」シートの末尾に検索結果（複数行）を追記する
        research_data: [[取得日時, 投稿テキスト, URL, いいね数], ...]
        """
        if not research_data:
            return
        
        try:
            worksheet = self.sheet.worksheet("リサーチ")
            worksheet.append_rows(research_data)
            print(f"リサーチシートに {len(research_data)} 件のデータを追記しました。")
        except gspread.exceptions.WorksheetNotFound:
            print("エラー: 'リサーチ' シートが見つかりません。")

    def append_draft_results(self, draft_data: list[list]):
        """
        「ドラフト」シートの末尾に生成された投稿案（複数行）を追記する
        draft_data: [[作成日, 元キーワード, 投稿案1, 投稿案2, 投稿案3], ...]
        """
        if not draft_data:
            return
            
        try:
            worksheet = self.sheet.worksheet("ドラフト")
            worksheet.append_rows(draft_data)
            print(f"ドラフトシートに {len(draft_data)} 件の投稿案を追記しました。")
        except gspread.exceptions.WorksheetNotFound:
            print("エラー: 'ドラフト' シートが見つかりません。")

# テスト用コード（直接実行された場合のみ）
if __name__ == "__main__":
    try:
        controller = GoogleSheetsController()
        keywords = controller.get_manual_keywords()
        print(f"取得した手動キーワード: {keywords}")
    except Exception as e:
        print(f"Error: {e}")
