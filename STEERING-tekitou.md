# STEERING-tekitou

tekitou 全体に関わるインフラ・横断的な決定事項のメモ。テーマ固有の議論は各テーマ直下の `STEERING-<topic>.md` に書く。

## 計算資源

### GPU 環境（Mac → Windows デスクトップ `ky`）

GPU を使う実験は **`E:/ml-playground/`** 配下の uv 仮想環境を流用する。tekitou 配下に独立した venv は作らない。

- **接続**: Mac から `ssh yk097@ky`（Tailscale MagicDNS 経由，鍵認証）
- **環境**: PyTorch 2.6.0+cu124, torchvision, torchaudio（CUDA 12.4 ビルド），Python 3.12
- **実行例**:
  ```sh
  ssh yk097@ky
  E:/ml-playground/.venv/Scripts/python.exe <スクリプト>
  ```
- **開発**: VS Code Remote-SSH で `Host: ky` に接続 → リモートで `E:/ml-playground/` を開く
- **詳細**: [E:/ml-playground/SETUP.md](../ml-playground/SETUP.md)（構築手順・トラブルシューティング・ハマりポイント記録）

注意：
- 新しい実験コードはまず `E:/ml-playground/` 側に置く。tekitou 配下から GPU を呼ぶ場合は SSH 経由で ml-playground のスクリプトを叩く形にする
- Windows がスリープすると接続が切れる（`powercfg /change standby-timeout-ac 0` で抑止可能）
- 長時間ジョブは PowerShell の `Start-Job` か `Start-Process` でバックグラウンド化する

## ステアリングファイルの方針

- 各テーマのディレクトリ直下に `STEERING-<topic>.md`（topic はディレクトリ名）を置く
- 子テーマのステアリングは冒頭で親テーマの相対リンクを張る
- 本ファイル（`STEERING-tekitou.md`）は全テーマに共通する事項のみ扱う
