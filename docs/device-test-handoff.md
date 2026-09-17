# 次セッションへの依頼：独立フォントパッチの実機検証

この資料を引き継ぎとして、以下のリポジトリのフォント置換パッチを実機で検証してください。ホスト側の実装・ビルド・自動テストは完了しています。今回は自動テストで確認できない TWRP 上の導入処理、Android の起動・フォント選択・描画、独立復元を確認したいです。

## 作業環境と前提

- 作業ディレクトリ: `C:\Users\haruki\Documents\repo\github.com\hrko\echo-show-5-jp-font-fix`
- Windows / PowerShell。作業中の GitHub 通信は **gh コマンド**を使ってください（作成するスクリプトは例外）。
- 端末: Echo Show 5 第2世代、`cronos`。
- OS: LineageOS 18.1 / Android 11。
- 対象 ROM: `lineage-18.1-20260904-UNOFFICIAL-cronos.zip`。
- ROM SHA-256: `4c355998061a454792128d4b730932b47ed05a3d2a6d2628599218f44cc84678`。
- 対象 system fingerprint: `google/lineage_cronos/cronos:11/RQ3A.211001.001/r0rt1z209050214:userdebug/test-keys`。
- 引き継ぎ作成日: 2026-09-18。作成時 HEAD: `51d7f72a28a850100e60c4f4edb21e087cfaa7f9`。
- **今回の実装は未コミットの作業ツリーにあります。HEAD だけでは再現できません。** 最初に `git status --short` と差分を確認し、既存変更を保持してください。
- 端末の接続状態、現在が Android / TWRP のどちらか、現在適用されているパッチ、ADB 権限、TWRP バージョンは未確認です。元 ROM の状態と決めつけないでください。

まず `README.md`、`docs/patch-format.md`、`scripts/`、`recovery/`、`tests/` を読んでください。証跡は Git 管理対象外の `build/device-validation/<実施日時>/` に保存してください。

## 実装済みの内容

欧文と CJK は別々の install / restore ZIP です。欧文は `sans-serif` と `sans-serif-condensed` だけを対象とします。

- Google Fonts 公式公開版 Google Sans Flex、`Version 4.005;[3fe7d0b9f]`、SIL OFL 1.1。
- 公式配布コミット: `3dc14e61f108f036db84188b9b405a67df9b7c88`（`google/fonts` の `ofl/googlesansflex`）。
- TTF SHA-256: `c31a482fbecbf2e07e6890134d20078723aadf732c9b9c6c9a44f86f8265b6fe`。
- 保存名: `GoogleSansFlex-Regular.ttf`。配布バイナリの内容は変更していません。
- 両ファミリーとも `wght=100〜900` を100刻み、normal / italic の計18設定ずつ。
- 幅: 標準 `wdth=100`、condensed `wdth=75`。傾斜: 通常 `slnt=0`、italic `slnt=-10`。
- 固定軸: `opsz=18 / GRAD=0 / ROND=0`。すべて公開版の軸範囲内です。
- 公開版にない文字を補うため、元の Roboto / RobotoCondensed 全20ファイルを残し、各対象ファミリー専用の `fallbackFor` を追加しています。
- 既存 CJK は Noto Sans CJK / Serif CJK の可変 TTC。言語・ウェイト・フォールバック順序を維持しています。
- `serif` / `monospace` の独立置換は未実装です。将来用の担当範囲だけ予約しています。今回、仮の serif/mono フォントを端末に導入する必要はありません。

Android 11 の family / font / axis / fallbackFor 形式を使い、Android 17 の family-list / supportedAxes は使っていません。

XML の共通構造をハッシュ検証し、自分の担当部分だけを置換・復元します。他の担当部分は保持します。担当外スロットの内容そのものを検証する方式ではありません。永続的な共有バックアップ・導入履歴は作りません。

## 既に確認したこと／まだ確認していないこと

前セッションでは `mise run fetch-assets`、`mise run build` が成功しました。`mise run test` の23件と、その後追加した生成 ZIP の統合テスト2件が成功しています（計25件）。

確認済み:

- 固定入力のハッシュ、公開 TTF のバージョン・軸・36設定のサンプル字形差。
- XML の担当外保持、エイリアス保持、CJK との可換性。
- ホストの shell/awk を使った実際の合成スクリプトの実行。
- 将来の serif/mono を模した4コンポーネントの全24導入順序と復元。
- 再適用、競合・未知の担当部分・共通構造変更の拒否。
- 生成した ZIP の内容・ハッシュと、元 ROM の実 XML に対する合成・作業ディレクトリ再利用。

**未確認:** ARM32 update-binary / Edify の端末上の実行、TWRP の本物の Toybox/BusyBox、mount・rename・SELinux 属性、Android の XML 読み込み、Minikin/FreeType による実描画、起動・ネイティブ UI・実機での独立復元。

従来の CJK 版だけは過去に実機の導入→復元→再導入、正常起動、日本語全ウェイトを確認しています。今回変更した共通導入処理や今回生成した CJK ZIP まで実機検証済みとは扱わないでください。

## 使用する成果物

`dist/` にある以下の4ファイルだけを使ってください。旧 `cronos-jp-fonts-*` など別名の過去成果物が残っている場合があります。

```text
5f477192c451b2ca834118e466f8ce1b3183a20e991f7e964a592ba9d8e12963  cronos-cjk-fonts-install.zip
6e983b470c834a12aca874d2d5994935db038d6375fe07c9b00750a941ea6d8f  cronos-cjk-fonts-restore.zip
a131a918572ace3c1c6ae96398a4f9f8925d82c553ed347fa9bee34f2ab08317  cronos-latin-fonts-install.zip
3d39ab81ac0a1d9ebbf96696ad1951e81139b49dc1fcb4d5cedf139197f6c32a  cronos-latin-fonts-restore.zip
```

資料作成時に実ファイルを再ハッシュし、`dist/SHA256SUMS.txt` と一致しています。使用前に PC 側と転送後の端末側でも照合してください。実装を修正・再ビルドした場合は新しい成果物のハッシュを記録し、ここにある旧ハッシュと混同しないでください。

補助資料:

- `dist/cronos-cjk-fonts-verification.json`、`dist/cronos-latin-fonts-verification.json`: 元・追加フォントのハッシュ、軸、字形等。
- `build/fonts.original.xml`、`build/fonts.cjk.xml`（CJK のみ）、`build/fonts.latin.xml`（欧文のみ）。
- `font-test.html`、`latin-font-test.html`: 外部フォントを読み込まない目視確認ページ。
- `build/pixel-research/`: Pixel の参考資料。再ダウンロード不要。Pixel の標準 sans-serif は Roboto で、今回の設定はその再現ではありません。抽出 TTF を端末へ配布しないでください。

## 開始時の確認

1. `adb devices -l` などで対象を確認し、複数台が接続されている場合は以降 `adb -s <serial>` で明示的に選択してください。
2. 現在のモード・端末・system fingerprint・fonts.xml・フォントファイル・空き容量を読み取り、初期状態を記録してください。TWRP 自身の getprop とインストール済み system/build.prop は区別してください。
3. **書き込み前に TWRP の System バックアップを取得し、保存先と復元方法を確認してください。** 現在状態のバックアップは、元 ROM 状態のバックアップとは限りません。
4. 正しい4 ZIP を転送し、端末上のハッシュを照合。失敗時にも restore ZIP とバックアップにアクセスできる状態にしてください。
5. CJK 用約160 MiB、欧文用約10 MiBの System 空き容量を目安に、併用時は両方の余裕を確認。TWRP の `/sbin/sh`、sha256sum / cp / mkdir / grep と awk の実体・動作を確認してください。2026-09-18 の実機確認では Toybox 内に awk がなく、単独の `/sbin/awk` がありました。単独 awk 対応後の ZIP は本資料の旧ハッシュとは異なります。[PC 直接バックアップ手順](twrp-pc-backup.md)も参照してください。
6. フラッシュ前に TWRP の System をアンマウント。ZIP は未署名のため署名検証が有効なら解除。通常は TWRP UI で実行し、UI 操作はユーザーと連携してください。

端末のマウント位置は実際に確認してください。インストーラー専用マウント先は `/tmp/jp-font-system`、その配下の対象は `/tmp/jp-font-system/system` です。成功後はアンマウントするため、事後の採取にそのパスが使えるとは限りません。Android 起動後の `/system/etc/fonts.xml` など、確認したパスから採取してください。

## 4状態の判定

他の担当範囲に独自変更がない場合、fonts.xml の SHA-256 は以下になります。

| 状態 | 記号 | SHA-256 |
| --- | --- | --- |
| 元 ROM | S | `6a44c329b05d78eac0fc9f8a49edfbaaa6c8ebd13b80af09e26e1dab1163f6da` |
| CJK のみ | C | `d511966983c2fc98dfbb5633b336b74709806c4a7315efa10616e78536ce8e55` |
| 欧文のみ | L | `ec1b09901464c884712bd62a7a6f2250d098c4daaa2d5d3815dfbd8beff17ec7` |
| CJK＋欧文 | B | `118a64a407779fac7f991a383d3d087f84d05d866e4fcd0c8f5e5025cf8bab14` |

未知のハッシュなら XML を採取して担当部分ごとに調べてください。安全ガードを外したり、XML 全体を強制上書きして進めないでください。

## 導入・復元の検証順序

現在状態を記録・バックアップしたうえで、今回の restore ZIP を必要に応じて使い、S を確認してから始めてください。**旧 CJK ZIP は欧文併用状態に対応しません。必ず上記の新しい CJK ZIP を使います。**

各行は TWRP でフラッシュし、ログとファイルを確認した後、Android を起動して期待状態を確認します。成功表示だけで合格としないでください。

| 順番 | 操作 | 遷移 | 特に確認する点 |
| --- | --- | --- | --- |
| 1 | 欧文 install | S → L | 欧文単独で起動・描画、CJK は元のまま |
| 2 | CJK install | L → B | 先に入れた欧文が維持される |
| 3 | 欧文 restore | B → C | CJK を残して欧文だけ元へ戻る |
| 4 | CJK restore | C → S | XML と元フォントが元 ROM と一致 |
| 5 | CJK install | S → C | 新しい共通処理で CJK 単独導入が動く |
| 6 | 欧文 install | C → B | 逆順でも同じ併用状態になる |
| 7 | CJK restore | B → L | 欧文を残して CJK だけ元へ戻る |
| 8 | 欧文 restore | L → S | 最終的に元 ROM へ戻る |

基本の8遷移が成功した後、同じ TWRP 起動中に同じ install ZIP を2回、同じ restore ZIP を2回実行し、再適用と `/tmp` 作業領域の再利用を確認してください。CJK・欧文それぞれを対象にし、開始状態と終了状態を記録してください。正常終了時の繰り返しと、異常終了後の再試行は別です。異常終了後はログを採取してリカバリーを再起動してください。

検証完了時の基本状態は S とします。ユーザーが別の最終状態を希望した場合はその状態を明記してください。

## 各段階で採取する証跡

- TWRP バージョン、使用した ZIP 名・ハッシュ、開始状態、終了コード・画面表示、`/tmp/recovery.log`。ログは次の操作や再起動で失う前に保存。
- 操作後の fonts.xml 本体・SHA-256。
- 対象フォントの有無・サイズ・SHA-256。元 Roboto 20ファイルは全状態で維持。C/B では可変 CJK TTC があり旧 TTC がなく、S/L では元 TTC が復元されること。L/B では GoogleSansFlex-Regular.ttf が存在すること。
- 書き込んだ XML・TTF/TTC の所有者 `0:0`、モード `0644`、SELinux ラベル `u:object_r:system_file:s0`。読み取り可能な環境で `ls -lZ` 等を使用。
- Android の起動完了、ホーム・設定画面の動作、クラッシュや文字化けの有無、起動後の logcat。font / Minikin / XML parse / SELinux denial 関連の行を抽出しても、元ログは残す。
- 同じ文字列・サイズ・言語・画面での比較スクリーンショット。バイナリ採取に PowerShell のテキスト用リダイレクトを使わず、スクリーンショットは端末に保存して `adb pull` 等で回収。

ファイル採取例（Android 起動中。serial・保存先は実際の値に置換）:

```powershell
adb -s <serial> shell getprop sys.boot_completed
adb -s <serial> pull /system/etc/fonts.xml <証跡ディレクトリ>/fonts.xml
Get-FileHash <証跡ディレクトリ>/fonts.xml -Algorithm SHA256
adb -s <serial> shell ls -lZ /system/etc/fonts.xml
adb -s <serial> logcat -d -v threadtime > <証跡ディレクトリ>/logcat.txt
```

## 描画の重点確認

**ネイティブ側の確認を優先し、HTML だけでは完了としないでください。** ブラウザには独自のフォント選択があり、condensed を無視したりウェイト・傾斜を合成したりする可能性があります。

- 標準幅 / condensed の両方で100〜900、通常体 / italic の36設定を比較。重さ・幅・傾斜が反映され、豆腐・欠落・描画崩れ・過度な行高・切れがないこと。
- wdth=75 は軸値であり、文字列全体の実測幅が厳密に通常の75%になるという判定はしないこと。
- ウェイト別エイリアス: sans-serif-thin / light / medium / black、sans-serif-condensed-light / medium。
- 基本文字: `Hamburgefontsiv ABC xyz 0123456789 éñÅß`。
- 補助フォールバック: `Ελληνικά Кириллица ĈĜ`。Google Sans Flex にない文字も読め、通常・太字・italic が不自然に欠けないこと。Roboto を残しただけでは実際の選択まで証明できません。
- CJK: `font-test.html` の日本語・韓国語・簡体字・繁体字（注音）・香港繁体字。Sans 100〜900、Serif 200〜900、Serif 100が200に対応すること。日本語 `骨直令辻`、混植・句読点も比較。
- 名前付き serif / monospace の既存ラテン文字は置換されていないこと。ただし標準 sans の変更は他ファミリーのフォールバックに影響し得るため、あらゆる文字の完全不変とは言わないこと。
- 設定・通知・ダイアログなど普段使う UI の行送り・省略・折り返し・ボタンのはみ出し。

既存のネイティブ確認手段で36設定を指定できない場合は、最小の TextView 検証アプリ等を検討してください。フォント名・ウェイトをシステム API で指定し、例えば Android 11 の `Typeface.create(Typeface.create(family, Typeface.NORMAL), weight, italic)` を使います。TTF の直接読み込みや APK 同梱フォントではシステム XML の検証を迂回するため代用しないでください。アプリの追加・環境準備が必要ならユーザーと範囲を調整してください。

スクリーンショットだけで全可変軸の正確な適用やフォントファイルの選択を断定しないでください。「XML・ファイル確認」「目視」「ネイティブ API の描画」を分けて記録します。

## 異常時と検証対象外

- 初回の失敗で次の ZIP を続けて適用せず、recovery.log、エラー、現在 XML、フォントの有無を先に保存。
- 起動できない場合は TWRP に戻り、状態を調査して対応する restore ZIP を使用。ガードで拒否された場合は System バックアップによる復元を使い、強制書き込みで回避しない。
- 通常の端末で空き容量を意図的に枯渇させる、書き込み途中で電源を切る、system XML・フォントを故意に壊す、といった試験は今回の通常検証に含めない。
- 他 ROM・他機種、ROM 更新後の維持、あらゆるアプリ・全文字、将来の実フォントを使った serif/mono パッチは今回の合格範囲外。
- 修正が必要になったら現象と原因を分けて記録し、修正→必要なホストテスト→再ビルド→新 ZIP のハッシュ記録→該当する実機検証の再実施へ進む。

## 最後に残してほしい報告

証跡ディレクトリに以下の形式で結果を残してください。確認できなかった項目は「未実施」「未確認」とし、推測で合格にしないでください。

```text
実施日時 / 端末 / ROM fingerprint / TWRP バージョン:
使用コードの HEAD・作業ツリー差分 / ZIP の SHA-256:
初期状態 / System バックアップ保存先:
各遷移（1〜8）: 合否、XML ハッシュ、起動、証跡パス
再適用（CJK・欧文、install・restore）:
ネイティブ36設定 / エイリアス:
Roboto 補助フォールバック:
CJK 言語・ウェイト:
serif / monospace の確認:
SELinux・属性 / ログ所見:
不具合・修正・再検証:
未確認項目と理由:
最終状態:
```

README の検証済み記述を更新する場合は、実際に確認した ZIP・環境・項目に限定してください。
