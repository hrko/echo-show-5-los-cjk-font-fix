# Python 版パッチの実機検証（2026-09-18）

対象: Echo Show 5 第2世代 cronos（ADB `G091P308301603TS`）、TWRP `3.7.0_9-0`、Linux `4.9.77` ARMv7。
System fingerprint: `google/lineage_cronos/cronos:11/RQ3A.211001.001/r0rt1z209050214:userdebug/test-keys`。

証跡は `build/device-validation/20260918-python/`（Git 管理対象外）に保存しました。`tested-source.zip` に検証時のコード、`tested-source-sha256.json` にそのハッシュ、`worktree.patch` / `git-status.txt` / `head.txt` に未コミットの変更を含む作業ツリーの記録を保存しています。各段階の TWRP ログ、XML 本体、フォントのハッシュと属性、Android の起動状態を示すプロパティ、logcat も含みます。

## 対象 ZIP

```text
bc1664aa93768f35dfc7e361bec5832ee439eaff713ef1b248a8d78ba4320b0b  cronos-cjk-fonts-install.zip
ce2071ce8a5a110d963febf63e977d1874a53d0f0cab12e2ac13f68b1913b518  cronos-cjk-fonts-restore.zip
c336504e763e8b036b4d7631b6111ccf0e5456abc128c9d7c7d540673b7c7f97  cronos-latin-fonts-install.zip
c08b2ec527a543b59ab5c9dd77936ce7beec19636451770de1f753d867f21e46  cronos-latin-fonts-restore.zip
```

本記録の対象は、上記のハッシュに一致する4つの ZIP です。`verification.json` の `device_tested: false` はビルド時の値を保持し、実機で確認した結果はこの文書と証跡に記録しています。

## 確認結果

状態を表す記号は、S＝元 ROM、C＝CJK のみ、L＝欧文のみ、B＝CJK＋欧文です。

- ARMv7 CPython 3.12.14 が TWRP の `/tmp` で起動し、SHA-256 の既知値テストに成功。
- ホスト32テスト成功。生成 ZIP 内の Python とホストの共通ソースが一致し、同梱 runtime manifest の全ファイルハッシュが一致。
- 初期状態 C（CJK のみ）から Python 版 CJK restore で S（元 ROM）へ復元し、Android 起動を確認。
- 以下の8遷移で ZIP 適用、XML・対象フォントのハッシュ、不要ファイルの不在、所有者 `0:0`、モード `0644`、SELinux `u:object_r:system_file:s0`、Android 起動を確認。元 Roboto / RobotoCondensed 20ファイルは全状態で一致。

| 証跡ディレクトリ | 操作 | 遷移 | ファイル・属性・起動 |
| --- | --- | --- | --- |
| 01-S-to-L | latin install | S → L | 成功 |
| 02-L-to-B | cjk install | L → B | 成功 |
| 03-B-to-C | latin restore | B → C | 成功 |
| 04-C-to-S | cjk restore | C → S | 成功 |
| 05-S-to-C | cjk install | S → C | 成功 |
| 06-C-to-B | latin install | C → B | 成功 |
| 07-B-to-L | cjk restore | B → L | 成功 |
| 08-L-to-S | latin restore | L → S | 成功 |

同じ TWRP 起動中に、CJK・欧文それぞれの install を2回、restore を2回実行しました。計8回すべてが成功し、`/tmp` のランタイム・作業領域を再利用できました。証跡は `repeat-cjk-1`〜`4`、`repeat-latin-1`〜`4` です。

通常の成功後の再適用と、ホストでの prepare 失敗後のステージング拒否を確認しています。実機の電源断・容量枯渇・実ファイル破壊による試験は実施していません。

## 起動待ちとログ

初回の Android から TWRP への再起動後、`ro.twrp.version` を取得できた段階でも、`twrp remountrw` は終了コード255で失敗しました。その後の実行は成功したため、ZIP 適用前の制御受付の準備に伴う問題と判断し、補助スクリプトを完了応答まで待つよう修正しました。今回の Python 版 ZIP の適用はすべて成功しました。

Android の `sys.boot_completed=1`、system_server / SystemUI の存在を確認し、各起動時の crash buffer は空でした。フォント・XML・SELinux 関連候補行は `font-log-review.json` に記録しています。途中の screenshot 採取では MediaProvider が `/data/local/tmp/font-validation-screen.png` の登録警告を出しています。これはフォントファイルの読み込みエラーとは別です。

## 表示確認と未確認範囲

表示はユーザーが手動で確認する方針とし、この記録では初期に採取した画像を描画の合格判定に使っていません。設定画面の起動要求が error code 101 で拒否された記録もあるため、画像ファイル名に settings とあっても、設定画面を表示できた証拠にはしていません。検証 APK は追加していません。

ネイティブ36設定、condensed / italic / 各ウェイト、Roboto 補助フォールバックの実際の選択、全 CJK 言語・ウェイト、serif / monospace の表示は自動検証の合格範囲外です。

既存 System バックアップ `build/device-validation/20260918-020133/system-before.ab` を保持し、SHA-256 `e653498603c3c17f1535008974a76053953d2f4edae93c1b646d61cbe24f110a` の一致を再確認しました。C 状態のバックアップであり、バックアップからの復元実行は今回も未実施です。前セッションの失敗証跡も保持しています。

## 検証終了時の状態

ユーザーの指定に従い、検証で S に戻した後に CJK と欧文を導入し、B（CJK＋欧文）で Android の起動を確認して終了しました。終了時の証跡は `final-cjk-install` と `final-both-install` です。

最終 XML SHA-256: `118a64a407779fac7f991a383d3d087f84d05d866e4fcd0c8f5e5025cf8bab14`。
