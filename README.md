# Echo Show 5 CJK 可変フォント

Echo Show 5 **第2世代（cronos）/ LineageOS 18.1** の CJK フォントを、公式 Noto CJK 可変フォントへ置き換える TWRP ZIP です。

- 対象 ROM: `lineage-18.1-20260904-UNOFFICIAL-cronos.zip`。他の ROM・世代には対応しません。
- 対応言語: 日本語・韓国語・簡体字・繁体字（注音を含む）・香港繁体字。
- ウェイト: ゴシック体は100〜900の9段階、明朝体は200〜900の8段階（100の指定は200にマッチ）。

対象実機で導入 → 復元 → 再導入と正常起動を確認済みです。日本語の全ウェイトの描画は検証済みですが、他の言語は未検証です。

## 導入・復元

1. 対象 ROM が入っていることを確認し、**TWRP で System をバックアップ**します。
2. `cronos-cjk-fonts-install.zip` と `cronos-cjk-fonts-restore.zip` を端末へ転送します。
3. TWRP の Mount で System をアンマウントし、Install から `cronos-cjk-fonts-install.zip` を選びます。
   ZIP は未署名のため、ZIP signature verification が有効なら解除してください。
4. 成功表示を確認して System へ再起動します。

System の空き容量は**約160 MiB以上**を推奨します。
TWRP の `/sbin/sh` と、`sha256sum` が使える `/sbin/toybox` または `/sbin/busybox` が必要です。
想定外のデバイス・ROM・設定では処理を中止します。

戻す場合は TWRP で **`cronos-cjk-fonts-restore.zip`** をフラッシュします。
`fonts.xml` が別の内容に変更されて復元を拒否された場合は、System バックアップで復元してください。
処理に失敗した場合はエラーを確認し、再試行前にリカバリーを再起動してください。
ROM 更新後の自動維持には対応していません。

## ビルド

mise と Python 3.14 が使用できる環境で実行します。依存関係は uv で管理します。
初回は約585 MBのダウンロードと、少なくとも約4 GBの追加空き容量が必要です。

```powershell
mise install
mise exec -- uv sync --locked --cache-dir .uv-cache
mise run fetch-assets
mise run build
mise run test
```

`fetch-assets` は対象 ROM と Noto Sans CJK / Serif CJK の可変 TTC を取得し、固定ハッシュを検証します。
一致する既存ファイルは再利用し、異なるファイルがある場合は上書きせず中止します。

出力先は `dist/` です。

| ファイル | 用途 |
| --- | --- |
| `cronos-cjk-fonts-install.zip` | 可変フォントの導入と旧フォントの削除 |
| `cronos-cjk-fonts-restore.zip` | 元 ROM のフォントと設定への復元 |
| `SHA256SUMS.txt` | ZIP の SHA-256 |
| `cjk-verification.json` | 入力ハッシュ・ウェイト範囲・字形の検証結果 |

入力・`build/`・`dist/`・仮想環境は Git 管理対象外です。
展開済みの `build/system.img` は再利用されます。手動で変更した場合は削除して再ビルドしてください。

## リリース（メンテナー向け）

[release.yml](.github/workflows/release.yml) をタグ指定で手動実行すると、ビルド・テスト・ビルド証明の作成を経て、上記4ファイルをリリースに公開します。
初回はワークフローをデフォルトブランチへマージし、Settings → General → Releases の **Enable release immutability** を有効にしてください。

`v0.1.0` を公開するバージョンに置き換えて実行します。

```sh
git tag v0.1.0
git push origin v0.1.0
gh workflow run release.yml --ref v0.1.0
```

本文や prerelease 設定を指定する場合は、同じタグのドラフトを先に作成してください。
失敗時はドラフトのまま残り、同じタグで再実行できます（同名アセットは置換）。公開済みリリースへの再実行はできません。
実行中はタグやドラフトを編集・公開せず、アセットを手動追加しないでください。

ダウンロードした ZIP のビルド証明は次のコマンドで検証できます（`OWNER/REPO` はリポジトリ名に置換）。
この証明は TWRP の ZIP 署名とは別です。

```sh
gh attestation verify cronos-cjk-fonts-install.zip --repo OWNER/REPO
gh attestation verify cronos-cjk-fonts-restore.zip --repo OWNER/REPO
```
