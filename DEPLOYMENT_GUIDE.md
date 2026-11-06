# デプロイ・運用手順書 (DEPLOYMENT_GUIDE.md)

本ドキュメントは、**Google Classroom to Discord Notifier** を Linux サーバー（Ubuntu / Debian 等）の Docker 環境へデプロイし、無人・自動で安全に運用するための手順書です。

---

## 目次
- [STEP 1: 前提要件と準備](#step-1-前提要件と準備)
- [STEP 2: Google Cloud Console での認証情報作成](#step-2-google-cloud-console-での認証情報作成)
- [STEP 3: 初回 OAuth トークンの発行](#step-3-初回-oauth-トークンの発行)
- [STEP 4: Docker Compose によるサーバーデプロイ](#step-4-docker-compose-によるサーバーデプロイ)
- [STEP 5: 動作確認・ヘルスチェック](#step-5-動作確認ヘルスチェック)
- [STEP 6: トラブルシューティング](#step-6-トラブルシューティング)

---

## STEP 1: 前提要件と準備

- **サーバー環境**:
  - Docker 24.0+ および Docker Compose v2+ がインストールされた Linux サーバー
- **必要なアカウント・権限**:
  - Google Workspace for Education（学校アカウント）または Google アカウント
  - Google Cloud Console プロジェクト作成権限
  - 通知先の Discord チャンネルの Webhook URL

---

## STEP 2: Google Cloud Console での認証情報作成

1. [Google Cloud Console](https://console.cloud.google.com/) にアクセスします。
2. 新規プロジェクトを作成します（例: `Classroom-Notifier`）。
3. **API とサービス** > **ライブラリ** から **Google Classroom API** を検索し、**有効にする** をクリックします。
4. **API とサービス** > **OAuth 同意画面**:
   - User Type: **外部 (External)** を選択して「作成」
   - アプリ名: `Classroom Notifier`、連絡先メールアドレスを入力
   - スコープ: 空白のまま次へ
   - **テストユーザー**: 通知対象となる**学校の Google アカウント（`~@ed.jp`, `~@ac.jp` 等）**を必ず追加します。
5. **API とサービス** > **認証情報**:
   - **認証情報を作成** > **OAuth クライアント ID**
   - アプリケーションの種類: **「デスクトップ アプリ」**
   - 名前: `Classroom Notifier Client`
   - 作成後、JSON をダウンロードし、ファイル名を `credentials.json` に変更します。

---

## STEP 3: 初回 OAuth トークンの発行

サーバーは CUI（ブラウザなし）であることが多いため、**初回認証は手元の PC（Windows / Mac）で実行し、生成された `token.json` をサーバーへ転送する**方法を推奨します。

1. **手元の PC でリポジトリをクローンまたはダウンロードし、仮想環境を準備**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **`credentials.json` をルートディレクトリに配置して認証コマンドを実行**:
   ```bash
   python -m src.cli auth
   ```
   ブラウザが自動的に開くので、通知対象の学校アカウントでログインし、権限を承認します。完了すると `token.json` が生成されます。

---

## STEP 4: Docker Compose によるサーバーデプロイ

### 4-1. リポジトリのクローン
サーバー上で作業を行います。

```bash
git clone https://github.com/zyuuuukak1n/discord-classroom-notifier.git
cd discord-classroom-notifier
```

### 4-2. 認証ファイル（`credentials.json`, `token.json`）の配置

手元で作成したファイルをサーバーのプロジェクトルートへ転送（SCP等）します：

```bash
# 所有者のみ読み書きにパーミッション制限（防御的設計）
chmod 0600 credentials.json token.json
```

### 4-3. 環境変数（`.env`）の設定

```bash
cp .env.example .env
vi .env  # または nano .env
```

`DISCORD_DEFAULT_WEBHOOK_URL` に Discord チャンネルの Webhook URL を入力します。

```env
DISCORD_DEFAULT_WEBHOOK_URL=https://discord.com/api/webhooks/123456789012345678/abcdefg_hijklmn_opqrstu
CHECK_INTERVAL_SECONDS=300
INITIAL_SYNC_MARK_AS_READ=true
```

### 4-4. （任意）複数クラスの個別設定

特定のクラスごとに通知先 Webhook やメンション先を変えたい場合は作成します：

```bash
cp config/courses.example.json config/courses.json
vi config/courses.json
```

### 4-5. コンテナのビルドと起動

```bash
# データ・ログディレクトリの作成
mkdir -p data logs

# ビルド & バックグラウンド起動
docker compose up -d --build
```

---

## STEP 5: 動作確認・ヘルスチェック

### 5-1. コンテナログの確認

```bash
docker compose logs -f
```

### 5-2. Webhook テスト通知の送信

コンテナ内でテスト送信を実行します：

```bash
docker compose exec classroom-notifier python -m src.cli test-notify
```
Discord チャンネルにテスト Embed が届けば疎通成功です。

---

## STEP 6: トラブルシューティング

| 症状 | 原因 | 対処法 |
| :--- | :--- | :--- |
| `Valid credentials not found` | `token.json` が未配置または破損 | 手元で `python -m src.cli auth` を再実行し、生成された `token.json` をサーバーへ再転送してください。 |
| `HTTP 429 Too Many Requests` | Discord API の一時的レート制限 | システム内部で自動リトライされます。頻発する場合は監視コース数やポーリング間隔（`CHECK_INTERVAL_SECONDS` を300秒以上）を見直してください。 |
| `Another instance is already running` | 前回のバッチがロック中 | 処理完了を待つか、異常終了した場合は `rm data/notifier.lock` でロックを解除してください。 |
| 提出期限がズレている | UTC と JST の差異 | 最新版では日本標準時（JST）への自動変換が内包されています。リポジトリを最新に更新してください。 |
