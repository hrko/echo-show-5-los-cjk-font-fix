# Recovery 用 Python ランタイム

4種類の ZIP に同じ ARMv7 CPython を同梱します。展開先は TWRP の RAM 上の `/tmp/jp-font-python`。System へ Python をインストールせず、リカバリーの再起動で消えます。

XML の所有権・分解・再合成はホストと同じ `scripts/font_slots.py` を ZIP の `patch/font_slots.py` にそのまま入れて実行します。`recovery/font_patch.py` が担当スロット、共通構造、フォントファイル、準備後の変更を検証します。mount、フォント展開、SELinux 属性設定、rename と削除順序は ROM 付属 updater の Edify に残しています。shell は Python 起動用の短いラッパーのみです。awk は使用しません。

## 固定入力と再取得

[Alpine v3.23 / main / armv7 の Python](https://pkgs.alpinelinux.org/package/v3.23/main/armv7/python3) と musl を使用し、ソースからのクロスコンパイルは行いません。取得・検証・抽出は [scripts/python_runtime.py](../scripts/python_runtime.py) に実装しています。

| 入力 | バージョン | SHA-256 |
| --- | --- | --- |
| python3 APK | 3.12.14-r0 | `0d1162d728d9f0f6e71447294139e1950d62a7a5f03ea78468bf6490cb82eb42` |
| musl APK | 1.2.5-r23 | `0f2f5029a9f401a4f10ca8c6ef03afe3aa4b521fc0ed44f1d6a2c6911eedc329` |
| musl ソース（COPYRIGHT 取得用） | 1.2.5 | `a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4` |

APK の取得元は `https://dl-cdn.alpinelinux.org/alpine/v3.23/main/armv7/`、musl ソースは `https://musl.libc.org/releases/musl-1.2.5.tar.gz` です。Alpine のビルドレシピのコミットは Python が `5cdca2ceaf5c9a15f0634eee73024384322361a4`、musl が `8aef0c37b0ad23dc4137f0e4755b97a59dc698b8`（取得時の APKINDEX 記録）。配布元 HTTPS と固定 SHA-256 を使い、APK 署名の検証を行ったとは扱いません。

`mise run fetch-assets` で `build/python-runtime/` に取得します。既存入力が異なるハッシュなら上書きせず中止します。`mise run build` はネットワークを使わず、すべての入力ハッシュを再検証します。固定バージョンが配布元から削除された場合も、自動的に別バージョンへ切り替えません。取得済み入力は保管してください。

同じ入力から ZIP 内のファイル名、バイト列、時刻、モードを固定して生成します。これは配布済みバイナリの再取得・抽出の再現性であり、Alpine のコンパイラーを含むソースビルド全体の再現性を検証したものではありません。

## 内容と依存関係

- `python3.12`、`libpython3.12.so.1.0`、標準ライブラリの `.py` と Python の `LICENSE.txt`。
- `_md5`、`_sha1`、`_sha2`、`_sha3`、`_blake2` のハッシュ拡張。`hashlib` はこれらを利用します。
- musl の `ld-musl-armhf.so.1`。`libc.musl-armv7.so.1` は同じ内容を通常ファイルとして同梱し、ZIP の symlink 展開に依存しません。
- `runtime/verification.json` に配布物 URL・ハッシュ、全同梱ファイルの SHA-256 と ELF の `DT_NEEDED` を記録します。

同梱 ELF が ARM32 little-endian であることを検査し、必要な共有ライブラリが同梱の libc / libpython 以外ならビルドを拒否します。OpenSSL、圧縮、SQLite、ネットワーク等の拡張は同梱しません。これはフォント処理用の限定ランタイムで、標準ライブラリの全機能を利用できる一般用途の Python 環境ではありません。ホスト側 fontTools / ext4 / uv も不要です。

`run-python.sh` は `/sbin/toybox` または `/sbin/busybox` の `env -i` で環境を初期化し、musl loader を直接起動します。`--library-path` と `PYTHONHOME` は `/tmp` の同梱ディレクトリを指定します。`-s -S -B` でユーザー site、site 初期化、bytecode 書き込みを無効にします。必要モジュールの import と SHA-256 の既知値テストを **System mount 前**に実行します。

ランタイム本体は展開後15,850,654 bytes（約15.1 MiB）、ZIP 内の圧縮データは5,242,709 bytes（約5.0 MiB、ZIP ヘッダー等を除く）です。TWRP の `/tmp` にこれと XML 作業領域の空きが必要です。

## ライセンス

Python APK の `LICENSE.txt` を変更せず `licenses/Python-LICENSE.txt` に同梱します。PSF-2.0 と、Python 内に含まれるコードの各通知を含みます。musl 1.2.5 の `COPYRIGHT` は `licenses/musl-COPYRIGHT.txt` に同梱し、MIT とファイル内の追加通知を保持します。これらも固定入力から取り出し、ZIP の runtime manifest でハッシュを記録します。

## 検証

ホストでは実際に同梱する Python スクリプトを実行し、全24導入順序、復元、担当外バイト列保持、再適用、未知変更拒否、ステージング、破損断片・準備済み出力・不正 manifest の拒否をテストします。生成 ZIP の実 ROM XML に対する統合テストもあります。

2026-09-18、cronos / TWRP `3.7.0_9-0` / Linux `4.9.77` armv7l の `/tmp` で CPython `3.12.14` の起動と SHA-256 の既知値を確認しました。ZIP 適用と Android の確認結果は [実機検証記録](python-device-validation.md) にまとめます。
