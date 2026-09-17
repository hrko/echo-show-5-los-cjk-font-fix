# Serif / Mono パッチの実機検証（2026-09-18）

対象: Echo Show 5 第2世代 cronos（ADB `G091P308301603TS`）、TWRP `3.7.0_9-0`、Android 11 / LineageOS 18.1。
System fingerprint: `google/lineage_cronos/cronos:11/RQ3A.211001.001/r0rt1z209050214:userdebug/test-keys`。

証跡は `build/device-validation/20260918-serif-mono/`（Git 管理対象外）に保存しています。`tested-source.zip` と SHA-256 一覧、HEAD・作業ツリー差分・未追跡ファイル一覧、各段階の TWRP ログ・XML・フォントハッシュ・属性・Android 起動ログを含みます。未コミットのコードも対象です。ビルド時の `device_tested: false` は変更せず、実機で確認した ZIP と項目を本記録で区別します。

## 対象 ZIP

```text
3e1c697e86b4bd78b0228d5966ee2df0ec17dca03ea56e7de19c4afea39bb565  cronos-cjk-fonts-install.zip
7e5b2a9b53217ad4980e2c0502873ee24ba4e14a381fa377f7ca4cccccc622ac  cronos-cjk-fonts-restore.zip
8f94a7adbd9c954f7bc475c6655c41699ba24a70bfc9f15a9c7acaf3e9383e4a  cronos-latin-fonts-install.zip
215404b1dabad8dbc8f167c58a6583329b825f899492acd66a845a7cd9cd371f  cronos-latin-fonts-restore.zip
f51d148ba888192b2a5676177349816fdb99f28f9c4a9ee364856973cf68e564  cronos-serif-fonts-install.zip
f70763cde3b7c7f1d16ba00f0041b31e72345a5b1316a64c710da40f81ccf316  cronos-serif-fonts-restore.zip
91ce965f55a4bbe7b55c33541312dce568d434a83d5005ea5cd9ffe7d30d6953  cronos-mono-fonts-install.zip
c95353c85b72c4d1f209f27092d748897f3a168a527f7a283434c122c49c7d82  cronos-mono-fonts-restore.zip
```

PC 側の `SHA256SUMS.txt` と照合し、転送後・各フラッシュ直前にも端末側の SHA-256 を照合しました。

## 初期状態とバックアップ

初期状態は CJK＋欧文（CL）。XML SHA-256 は `118a64a407779fac7f991a383d3d087f84d05d866e4fcd0c8f5e5025cf8bab14`、System の空き容量は約1.7 GiBでした。

今回の初期状態を TWRP で PC にバックアップしました。

- 保存先: `build/device-validation/20260918-serif-mono/system-before.ab`
- サイズ: 550,504,448 bytes
- SHA-256: `7a4ed545d6724ab35ac57c718b4cd80595b9c2196fb9c185c52893cb2d6b0a71`
- System 1エントリー。TWRP v3 制御ブロック・終端・MD5・gzip CRC の検証に成功。
- 元 ROM 状態のバックアップではありません。バックアップからの復元実行は未実施です。[復元方法](twrp-pc-backup.md)の保存先を上記へ変更して使用します。

## 導入・個別復元

C＝CJK、L＝Google Sans Flex、R＝Noto Serif VF、M＝Google Sans Code VF。

| 証跡ディレクトリ | 操作 | 遷移 | ファイル・属性・Android 起動 |
| --- | --- | --- | --- |
| 01-CL-to-CLR | serif install | CL → CLR | 成功 |
| 02-CLR-to-CLRM | mono install | CLR → CLRM | 成功 |
| 03-CLRM-to-CLM | serif restore | CLRM → CLM | 成功 |
| 04-CLM-to-CL | mono restore | CLM → CL | 成功 |
| 05-CL-to-CLM | mono install | CL → CLM | 成功 |
| 06-CLM-to-CLRM | serif install | CLM → CLRM | 成功 |
| 07-CLRM-to-CLR | mono restore | CLRM → CLR | 成功 |
| 08-CLR-to-CL | serif restore | CLR → CL | 成功 |

各段階で XML 全体が期待値とバイト単位で一致し、対象フォント28〜32ファイルのハッシュ・不要VFの不在、所有者 `0:0`、モード `0644`、SELinux `u:object_r:system_file:s0` を TWRP と Android の両方で確認しました。元 Roboto / RobotoCondensed 20ファイル、Noto Serif 4ファイル、DroidSansMono を保持しています。

Android の `sys.boot_completed=1`、system_server / SystemUI の存在を確認しました。8起動の crash buffer は空で、保存したログのフォント・SELinux 関連候補はランチャーの時計フォントサイズの通知のみでした。

初回の Android → TWRP 再接続はユーザーの再試行指示後に成功。1段階目の起動確認後にもPC側のADBデーモン接続が一時的に失敗しましたが、端末の正常起動・XML一致を再確認して2段階目から再開しました。これらは ZIP 適用エラーではありません。

## 再適用

同じ TWRP 起動中に Serif / Mono それぞれ install を2回、restore を2回実行し、計8適用が成功しました。各操作後の XML・フォント・属性も一致し、`/tmp` のランタイム・作業領域を再利用できました。証跡は `repeat-serif-1`〜`4` と `repeat-mono-1`〜`4` です。

2回目の restore に出る `Keeping absent, modified or referenced font` は、1回目で削除済みのVFに対するメッセージです。実際にファイルが存在しないことを別途確認しています。

## 既存パッチ側からの独立復元

Serif / Mono を再導入した後、次の4操作でも XML・全対象フォント・属性が一致しました。

| 証跡ディレクトリ | 操作 | 遷移 |
| --- | --- | --- |
| compat-latin-restore | latin restore | CLRM → CRM |
| compat-cjk-restore | cjk restore | CRM → RM |
| compat-latin-install | latin install | RM → LRM |
| compat-cjk-install | cjk install | LRM → CLRM |

RM（Serif＋Monoのみ）と最後の CLRM で Android 起動も成功し、各起動時の crash buffer は空でした。CRM / LRM の中間状態は TWRP 上のファイル検証のみです。導入・復元・再適用は合計22回で、すべて成功しました。

## Android のネイティブ描画

`app_process` で検証用 `FontProbe` を起動し、Android の `Typeface.create(ファミリー名, …)`、`Paint`、`Canvas` で端末上のビットマップへ描画しました。フォントを同梱した APK や Web フォントは使っていません。検証対象はシステムの `serif` / `monospace`。参照側に限って実ファイル・可変軸を明示指定し、同じ座標・サイズ・文字列のピクセルを比較しました。

- Noto Serif: 100〜900 × 通常・イタリックの18設定で参照描画と完全一致。全18設定の画像ハッシュが異なり、ウェイト・スタイル差を確認。
- Google Sans Code: 300〜800 × 通常・イタリックの12設定で参照描画と完全一致。全12設定の画像ハッシュが異なり、全設定でASCII 95文字（U+0020〜U+007E）の個別送り幅が一致（許容差0.01 px）。
- Mono の100・200指定は300、900指定は800の描画と一致（通常・イタリック両方）。
- `monaco` / `sans-serif-monospace` は `monospace`、`times` は `serif` の400通常体と一致。
- 30設定と日欧混植サンプルの画像を保存・確認。確認画像内に欠落文字や明らかな描画崩れはありません。

証跡: `probe/stdout.txt`（画像ハッシュ・判定）、`probe/native-rasterization.png`（比較用一覧）、`probe/final-screen.png`（実際の端末画面）、`probe/FontProbe.java` / `classes.dex`。検証補助コードは `validation-tools.zip` と SHA-256 一覧にも保存しています。

### フォールバックと言語指定

端末の `Paint` の既定ロケールは `ja_JP` でした。元フォントを保持していても、すべての不足文字で元フォントが最優先になるとは限りません。

| ファミリー | サンプル | ja_JP の参照描画と一致したフォント | en_US の参照描画と一致したフォント |
| --- | --- | --- | --- |
| serif | U+03E2 / U+03E3 | 元 NotoSerif-Regular | 元 NotoSerif-Regular |
| serif | U+2190 / U+2211 / U+2500 | Noto Serif CJK JP VF（400） | 元 NotoSerif-Regular |
| monospace | U+0108 / U+011C | 元 DroidSansMono | 元 DroidSansMono |
| monospace | U+0391 / U+03A9 / U+0416 | Noto Sans CJK JP VF（400） | 元 DroidSansMono |

各サンプルの `Paint.hasGlyph` が成功し、上表の参照描画との一致を確認しました。en_US は検証用 Paint にだけ設定し、端末の言語設定は変更していません。フォールバック先を含めた全Unicode文字の等幅性や、常に元フォントの字形になることは保証しません。

初回の描画テストは「不足文字がすべて元フォントと一致する」という誤った検証条件で停止し、検証プロセス自身の `AssertionError` が crash buffer に残りました。文字ごと・ロケールごとの比較で上記の選択を確認し、検証条件を修正しました。初回のソース・DEX・出力・ログは `probe/attempt-1/` に保持しています。パッチや端末のフォント設定の修正は行っていません。

コンパイルは既存の Java 8、[Eclipse ECJ 3.26.0](https://repo.maven.apache.org/maven2/org/eclipse/jdt/ecj/3.26.0/ecj-3.26.0.jar)、[Google D8 2.2.66](https://storage.googleapis.com/r8-releases/raw/2.2.66/r8.jar) を使用。取得ファイルの SHA-256 は `probe/file-sha256.json` に記録しています。

## 未確認範囲

全Unicode文字、全言語・アプリのレイアウト、全フォールバックのスタイル・ウェイト、実機の電源断・容量枯渇・ファイル破壊、バックアップからの復元は未検証です。既存 CJK・欧文の全描画設定を今回再検証したわけではありません。画像による確認はオフスクリーンのネイティブ Canvas と採取時の端末画面に限定します。

## 最終状態

ユーザー指定どおり、**CJK＋欧文＋Serif＋Mono の4種類すべてを適用して Android 起動済み**です。

最後に Android を再起動し（`final-clean-boot/`）、ロケール別の参照描画を判定条件にした修正版テストが成功しました。再起動後・テスト終了後とも crash buffer は空で、採取したログにフォント読み込みエラーや SELinux denial はありません。最終32フォントのハッシュ・XML・属性も再照合済みです。テストプログラムの `app_process` は終了しており、検証 APK は追加していません。

最終 XML SHA-256: `b72efb6e4b62c1e1c316119951aceb593933abb68e8228bd4fab0d3df2fa94e3`。
