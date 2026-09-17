# Recovery 用 Python ランタイム

各パッチの導入・復元 ZIP に、同じ ARMv7 CPython を同梱します。展開先は TWRP の RAM 上にある `/tmp/jp-font-python` です。System にはインストールせず、展開したランタイムはリカバリーの再起動で消えます。

XML の担当範囲の定義・分解・再合成には、ホストと同じ `scripts/font_slots.py` を使います。このファイルを ZIP の `patch/font_slots.py` に変更せず同梱し、`recovery/font_patch.py` から利用します。端末側では担当スロット・共通構造・フォントファイルを検証し、書き込み準備後に入力が変わっていないことも確認します。

マウント、フォントの展開、SELinux 属性の設定、ファイル名の変更・削除は、基準の cronos ROM 付属の ARM32 updater が Edify スクリプトに従って行います。3機種共通 ZIP にも同じ updater を同梱します。シェルスクリプトは Python の起動だけを担当し、awk は使いません。

## 固定入力と再取得

[Alpine v3.23 / main / armv7 の Python](https://pkgs.alpinelinux.org/package/v3.23/main/armv7/python3) と musl を使用し、ソースからのクロスコンパイルは行いません。取得・検証・抽出は [scripts/python_runtime.py](../scripts/python_runtime.py) に実装しています。

| 入力 | バージョン | SHA-256 |
| --- | --- | --- |
| python3 APK | 3.12.14-r0 | `0d1162d728d9f0f6e71447294139e1950d62a7a5f03ea78468bf6490cb82eb42` |
| musl APK | 1.2.5-r23 | `0f2f5029a9f401a4f10ca8c6ef03afe3aa4b521fc0ed44f1d6a2c6911eedc329` |
| musl ソース（COPYRIGHT 取得用） | 1.2.5 | `a9a118bbe84d8764da0ea0d28b3ab3fae8477fc7e4085d90102b8596fc7c75e4` |

APK の取得元は `https://dl-cdn.alpinelinux.org/alpine/v3.23/main/armv7/`、musl ソースは `https://musl.libc.org/releases/musl-1.2.5.tar.gz` です。Alpine のビルドレシピのコミットは Python が `5cdca2ceaf5c9a15f0634eee73024384322361a4`、musl が `8aef0c37b0ad23dc4137f0e4755b97a59dc698b8`（取得時の APKINDEX 記録）。配布元 HTTPS と固定 SHA-256 を使い、APK 署名の検証を行ったとは扱いません。

`mise run fetch-assets` で `build/python-runtime/` に取得します。既存入力が異なるハッシュなら上書きせず中止します。`mise run build` はネットワークを使わず、すべての入力ハッシュを再検証します。固定バージョンが配布元から削除された場合も、自動的に別バージョンへ切り替えません。取得済み入力は保管してください。

同じ入力からは、ZIP 内のファイル名・バイト列・時刻・モードが同じになるように生成します。再現性の確認範囲は、配布済みバイナリの取得・抽出と ZIP への同梱です。Alpine のコンパイラーを含む、ソースからのビルド全体の再現性は検証していません。

## 内容と依存関係

- `python3.12`、`libpython3.12.so.1.0`、標準ライブラリの `.py` と Python の `LICENSE.txt`。
- `_md5`、`_sha1`、`_sha2`、`_sha3`、`_blake2` のハッシュ拡張。`hashlib` はこれらを利用します。
- musl の `ld-musl-armhf.so.1`。`libc.musl-armv7.so.1` は同じ内容を通常ファイルとして同梱し、ZIP の symlink 展開に依存しません。
- `runtime/verification.json` に配布物 URL・ハッシュ、全同梱ファイルの SHA-256 と ELF の `DT_NEEDED` を記録します。

ビルド時には、同梱する ELF ファイルが ARM32 のリトルエンディアン形式であることを検査します。同梱の libc / libpython 以外の共有ライブラリが必要な場合は、ビルドを中止します。

このランタイムはフォント処理に用途を限定しています。OpenSSL・圧縮・SQLite・ネットワークなどの拡張は同梱しないため、Python 標準ライブラリの全機能は利用できません。ホストで使用する fontTools / ext4 / uv も、端末側には不要です。

`run-python.sh` は `/sbin/toybox` または `/sbin/busybox` の `env -i` で環境変数を初期化し、musl のローダーを直接起動します。`--library-path` と `PYTHONHOME` には、`/tmp` に展開した同梱ディレクトリを指定します。`-s -S -B` でユーザーの site-packages、`site` による初期化、バイトコードの書き込みを無効にします。必要なモジュールの読み込みと SHA-256 の既知値テストは、System のマウント前に実行します。

ランタイム本体は展開後15,850,654 bytes（約15.1 MiB）、ZIP 内の圧縮データは5,242,709 bytes（約5.0 MiB、ZIP ヘッダー等を除く）です。TWRP の `/tmp` にこれと XML 作業領域の空きが必要です。

## ライセンス

Python APK の `LICENSE.txt` を変更せず `licenses/Python-LICENSE.txt` に同梱します。PSF-2.0 と、Python 内に含まれるコードの各通知を含みます。musl 1.2.5 の `COPYRIGHT` は `licenses/musl-COPYRIGHT.txt` に同梱し、MIT とファイル内の追加通知を保持します。これらも固定入力から取り出し、ZIP の runtime manifest でハッシュを記録します。

## 検証

ホストでは、ZIP に同梱する Python スクリプトを実行して、4パッチの全24通りの導入順序・復元・再適用をテストします。担当外のバイト列の保持、未知の変更の拒否、ステージングに加え、破損した断片・改変された準備済み出力・不正なマニフェストを拒否することも確認します。生成 ZIP と対象 ROM の XML を使う統合テストもあります。

2026-09-18 に、cronos / TWRP `3.7.0_9-0` / Linux `4.9.77` armv7l の `/tmp` で CPython `3.12.14` を起動し、SHA-256 の既知値テストに成功しました。ZIP の適用と Android の起動を確認した結果は、[実機検証記録](python-device-validation.md)に記載しています。
