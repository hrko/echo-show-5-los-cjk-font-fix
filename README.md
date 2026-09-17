# Echo Show 5 日本語フォント拡張

配置済みの `lineage-18.1-20260904-UNOFFICIAL-cronos.zip` を元に、
Echo Show 5 **第2世代（cronos）** / LineageOS 18.1 向けの TWRP ZIP を作成します。
ゴシック体は **100〜900 の9段階**、明朝体は **200〜900 の8段階**です。
明朝体の100は公式フォントの範囲外なので追加せず、要求時は200へのマッチングになります。

## 成果物

- `dist/cronos-jp-fonts-install.zip`: 日本語ゴシック体・明朝体を導入。
- `dist/cronos-jp-fonts-restore.zip`: この ROM の元の fonts.xml に復元。
- `dist/SHA256SUMS.txt`: ZIP の SHA-256。
- `dist/verification.json`: 入力のハッシュ、軸の範囲、字形検証結果。
- `font-test.html`: 外部フォントを使わない表示確認ページ。

**実機へのフラッシュ・起動・表示は未検証です。** PC 上の検証と実機での確認を区別してください。
他の ROM・他の世代向けの汎用 ZIP ではありません。

## 再作成

mise と Python 3.14 が使用できる環境で実行します。uv は `mise.toml` に固定し、
Python バージョンは `.python-version`、依存関係は `pyproject.toml` と `uv.lock` で管理します。
`uv sync` / `uv run` がプロジェクトの `.venv` を管理します。pip での手動導入は不要です。

```powershell
mise install
mise exec -- uv sync --locked --cache-dir .uv-cache
mise run build
mise run test
```

入力はリポジトリ直下の次の3ファイルです。

- `lineage-18.1-20260904-UNOFFICIAL-cronos.zip`
- `NotoSansCJKjp-VF.ttf`（配置済み、公式 Version 2.004 と一致確認済み）
- `NotoSerifCJKjp-VF.ttf`（公式から取得した Version 2.003）

フォントの取得元・版は [検証記録](VERIFICATION.md) に記載しています。
大きい入力、`build/`、`dist/`、仮想環境は Git 管理対象外です。
初回は Brotli をストリーム展開して約3.25 GBの ext4 イメージを `build/system.img` に生成します。
ZIP 等を含め、少なくとも4 GB程度の追加空き容量を確保してください。
2回目以降は入力 ROM の SHA-256 が一致する場合に展開済みイメージを再利用します。
キャッシュを手作業で編集した場合は `build/system.img` を削除して再作成してください。

`scripts/build_zip.py` が標準ライブラリの `zipfile` で ZIP を作成します。
XML の日本語 family 以外は元のバイト列を保持し、元の中国語・韓国語や既存フォントは残します。
同じ入力・Python/依存関係での再作成では ZIP の順序・時刻・権限も一定です。

## TWRP で導入

1. この ZIP の元と同じ ROM が入っていることを確認します。インストーラーも build fingerprint を照合します。
2. TWRP で System のバックアップを取得し、インストール用・復元用の両 ZIP を端末へ転送します。
3. TWRP の Mount で System をアンマウントし、Install から `cronos-jp-fonts-install.zip` を選びます。
   生成 ZIP は署名していないため、TWRP の ZIP signature verification を有効にしている場合は解除が必要です。
4. 成功表示を確認して System を再起動します。失敗した場合はエラーメッセージを確認し、成功扱いにしないでください。

TWRP の `/sbin/sh` と、`sha256sum` を利用できる `/sbin/busybox` が必要です。
フォント追加量は約92 MiBです。再インストール時は一時ファイルも必要なため、
System に少なくとも約150 MiBの空きを推奨します。

system パーティションは専用の `/tmp/jp-font-system` にマウントし、
ROM で確認した `/system/etc/fonts.xml` と `/system/fonts/` をその中から参照します。
デバイス、ROM、現在の XML のハッシュが想定と異なると中止します。
導入時は同名の異なるフォントも上書きしません。
各ファイルを一時名に展開してハッシュ・権限・SELinux ラベルを設定し、rename で置き換えます。
XML の置換は両フォントの配置後です。失敗時は専用マウントや一時ファイルが残る場合があります。
リカバリー再起動でマウントは解除されます。一時ファイルは同じ処理の再実行で上書きされます。

## 表示確認と復元

端末の言語を日本語にして `font-test.html` をブラウザで開き、各段階の太さを確認します。
必要なら PC 側で `mise exec -- uv run --locked --cache-dir .uv-cache python -m http.server 8000 --bind 0.0.0.0`
を起動し、同じネットワークの端末から `http://PCのIPアドレス:8000/font-test.html` にアクセスします。
この HTTP サーバーはカレントディレクトリを公開するので、確認後は Ctrl+C で終了してください。
ブラウザ固有のフォント選択も影響するため、設定アプリなどの日本語表示も確認します。
HTML での表示だけでは Android 全体の適用や全字形の正しさの証明にはなりません。

戻す場合は TWRP で `cronos-jp-fonts-restore.zip` をフラッシュします。
元の XML を先に復元し、このパッチとハッシュが一致する追加フォントだけを削除します。
欠落・変更済みの追加フォントは復元を妨げず、変更済みファイルは残します。
XML 自体が別の内容に変更されている場合は拒否するため、取得しておいた System バックアップで復元してください。
ROM 更新への自動追従・維持処理は含めていません。
