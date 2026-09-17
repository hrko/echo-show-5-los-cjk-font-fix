# Echo Show 5 CJK 可変フォント

配置済みの `lineage-18.1-20260904-UNOFFICIAL-cronos.zip` を元に、
Echo Show 5 **第2世代（cronos）** / LineageOS 18.1 向けの TWRP ZIP を作成します。
ゴシック体は **100〜900 の9段階**、明朝体は **200〜900 の8段階**です。
明朝体の100は公式フォントの範囲外なので追加せず、要求時は200へのマッチングになります。

日本語・韓国語・簡体字・繁体字・香港繁体字の両書体を公式の可変 TTC に切り替えます。
`NotoSansCJK-Regular.ttc` と `NotoSerifCJK-Regular.ttc` は設定の切り替え後に削除します。

| XML の言語 | 可変 TTC の index | 字形 |
| --- | ---: | --- |
| `ja` | 0 | JP |
| `ko` | 1 | KR |
| `zh-Hans` | 2 | SC |
| `zh-Hant,zh-Bopo` | 3 | TC（注音も維持） |
| `zh-Hant-HK` | 4 | HK（今回追加） |

## 成果物

- `dist/cronos-cjk-fonts-install.zip`: 全 CJK の可変ゴシック体・明朝体を導入し、旧 TTC を削除。
- `dist/cronos-cjk-fonts-restore.zip`: この ROM の元の TTC 2ファイルと fonts.xml を復元。
- `dist/SHA256SUMS.txt`: ZIP の SHA-256。
- `dist/cjk-verification.json`: 入力のハッシュ、軸の範囲、各ロケールの字形検証結果。
- `font-test.html`: 言語を切り替えられる、外部フォントを使わない表示確認ページ。

**2026-09-17、全 CJK 版の実機適用・旧 TTC 削除・Android 正常起動を確認しました。**
各ロケールの全ウェイト描画と、全 CJK 版の復元 ZIP の実行は未検証です。
以前の日本語単独版での導入・復元・再起動の結果は [実機検証記録](DEVICE_VALIDATION.md) にあります。
旧日本語版の `cronos-jp-*` ZIP が dist に残っていても、全 CJK 版の復元には使用しないでください。
他の ROM・他の世代向けの汎用 ZIP ではありません。

## 再作成

mise、Python 3.14、GitHub CLI (`gh`) が使用できる環境で実行します。uv は `mise.toml` に固定し、
Python バージョンは `.python-version`、依存関係は `pyproject.toml` と `uv.lock` で管理します。
`uv sync` / `uv run` がプロジェクトの `.venv` を管理します。pip での手動導入は不要です。

```powershell
mise install
mise exec -- uv sync --locked --cache-dir .uv-cache
mise run fetch-assets
mise run build
mise run test
```

入力はリポジトリ直下の次の3ファイルです。

- `lineage-18.1-20260904-UNOFFICIAL-cronos.zip`
- `NotoSansCJK-VF.ttf.ttc`（公式 Version 2.004、5ロケール共有）
- `NotoSerifCJK-VF.ttf.ttc`（公式 Version 2.003、5ロケール共有）

`fetch-assets` は必要な外部アセット3ファイルをすべて取得・検証します。
ROM は [公式リリース lineage-18.1-cronos-v0.4](https://github.com/amazon-oss/releases/releases/tag/lineage-18.1-cronos-v0.4)
から `gh release download` で取得し、固定 SHA-256 を照合します。
ダウンロード中や検証失敗の ROM を正式な入力ファイル名で残さない構成です。
フォントは `gh api` で固定コミットから取得し Git blob ハッシュを照合します。
既存ファイルが異なる場合は上書きせず中止します。旧日本語 TTF はビルドには不要です。
一致する既存ファイルは再ダウンロードしません。初回の総ダウンロード量は約585 MBです。
フォントだけを取得する既存の `mise run fetch-fonts` も利用できます。
ライセンス類は Git に同梱済みで、fonts.xml・update-binary・復元用 TTC はビルド時に ROM から抽出します。
取得元・版は [全 CJK 版の検証記録](CJK_VALIDATION.md) に記載しています。
大きい入力、`build/`、`dist/`、仮想環境は Git 管理対象外です。
初回は Brotli をストリーム展開して約3.25 GBの ext4 イメージを `build/system.img` に生成します。
ZIP 等を含め、少なくとも4 GB程度の追加空き容量を確保してください。
2回目以降は入力 ROM の SHA-256 が一致する場合に展開済みイメージを再利用します。
キャッシュを手作業で編集した場合は `build/system.img` を削除して再作成してください。

`scripts/build_zip.py` が標準ライブラリの `zipfile` で ZIP を作成します。
既存4つの CJK family を置換し、香港用を追加します。その他の XML は元のバイト列を保持します。
削除する TTC が他の XML から参照されていないことも元 ROM 全体で検査します。
同じ入力・Python/依存関係での再作成では ZIP の順序・時刻・権限も一定です。

## TWRP で導入

1. この ZIP の元と同じ ROM が入っていることを確認します。インストーラーも build fingerprint を照合します。
2. TWRP で System のバックアップを取得し、インストール用・復元用の両 ZIP を端末へ転送します。
3. TWRP の Mount で System をアンマウントし、Install から `cronos-cjk-fonts-install.zip` を選びます。
   生成 ZIP は署名していないため、TWRP の ZIP signature verification を有効にしている場合は解除が必要です。
4. 成功表示を確認して System を再起動します。失敗した場合はエラーメッセージを確認し、成功扱いにしないでください。

TWRP の `/sbin/sh` と、`sha256sum` を利用できる `/sbin/toybox` または `/sbin/busybox` が必要です。
可変 TTC 2ファイルは合計約95.5 MiBです。旧 TTC の削除は最後に行うため、
System に少なくとも約160 MiBの空きを推奨します。
未変更の元 ROM、本プロジェクトの日本語単独版、同じ全 CJK 版から導入できます。
既存の日本語単独版 TTF は切り替え後、既知のハッシュと一致するものだけ削除します。

system パーティションは専用の `/tmp/jp-font-system` にマウントし、
ROM で確認した `/system/etc/fonts.xml` と `/system/fonts/` をその中から参照します。
デバイス、ROM、現在の XML のハッシュが想定と異なると中止します。
導入時は同名の異なるフォントも上書きしません。
各ファイルを一時名に展開してハッシュ・権限・SELinux ラベルを設定し、rename で置き換えます。
XML の置換は両フォントの配置後、旧 TTC の削除は XML 置換後です。
同名の旧 TTC が元 ROM と異なる場合は削除せず中止します。
失敗時は専用マウントや一時ファイルが残る場合があります。
リカバリー再起動でマウントは解除されます。一時ファイルは同じ処理の再実行で上書きされます。

## 表示確認と復元

`font-test.html` をブラウザで開き、言語セレクターで5ロケールの各段階の太さを確認します。
サンプル部分の `lang` 属性も選択した言語に切り替わります。
必要なら PC 側で `mise exec -- uv run --locked --cache-dir .uv-cache python -m http.server 8000 --bind 0.0.0.0`
を起動し、同じネットワークの端末から `http://PCのIPアドレス:8000/font-test.html` にアクセスします。
この HTTP サーバーはカレントディレクトリを公開するので、確認後は Ctrl+C で終了してください。
ブラウザ固有のフォント選択も影響するため、設定アプリなどの日本語表示も確認します。
HTML での表示だけでは Android 全体の適用や全字形の正しさの証明にはなりません。

戻す場合は TWRP で **`cronos-cjk-fonts-restore.zip`** をフラッシュします。
復元 ZIP に同梱した元の TTC 2ファイルを先に復元し、元の XML に戻してから追加フォントを削除します。
日本語単独版へ戻すのではなく、元 ROM の設定に戻ります。
欠落・変更済みの追加フォントは復元を妨げず、変更済みファイルは残します。
XML 自体が別の内容に変更されている場合は拒否するため、取得しておいた System バックアップで復元してください。
ROM 更新への自動追従・維持処理は含めていません。
