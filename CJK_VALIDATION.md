# 全 CJK 版の検証

2026-09-17。日本語単独版から全 CJK ロケールへ実装を拡張しました。
この版は PC 上で検証済みで、同日に実機へのフラッシュ・正常起動も確認しました。
端末には現在、全 CJK 版を適用しています。全 CJK 版の復元 ZIP の実行は未検証です。

## 一次資料と入力

`gh api` で以下の公式ファイルを取得しました。いずれも固定コミット
`f8d157532fbfaeda587e826d4cd5b21a49186f7c` の未改変 TrueType 可変コレクションです。
CFF2 版ではありません。

| ファイル | bytes | Git blob SHA-1 |
| --- | ---: | --- |
| [NotoSansCJK-VF.ttf.ttc](https://github.com/notofonts/noto-cjk/blob/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Sans/Variable/OTC/NotoSansCJK-VF.ttf.ttc) | 38,089,916 | `cfeab111cec01c491c0120aeb905a86afaecea56` |
| [NotoSerifCJK-VF.ttf.ttc](https://github.com/notofonts/noto-cjk/blob/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Serif/Variable/OTC/NotoSerifCJK-VF.ttf.ttc) | 62,008,512 | `f2e98c60cee4f44de9f671d76d900ac84a50da14` |

各コレクションの name/fvar/cmap/glyf/gvar を検査し、index 0〜4 がそれぞれ
JP/KR/SC/TC/HK であることを確認しました。Sans は100〜900、Serif は200〜900。
各 face の言語別サンプル文字を各ウェイトで描画用の輪郭に変換し、すべて異なることを確認します。
同じ漢字コードでも地域ごとに字形が異なるため、言語ごとの index を明示します。

Android 11 の `index` と `axis` の読み取り実装は、既に取得した
[FontListParser.java](https://github.com/LineageOS/android_frameworks_base/blob/6432e2cf6632de03b8ba48d1d18825f1c9b5350c/graphics/java/android/graphics/FontListParser.java)
で確認しています。`postScriptName` は使いません。

## 旧 TTC の排除と復元

元 ROM の4つの CJK family は JP/KR/SC/TC を指定していました。
今回もこの対応と `zh-Bopo`、明朝体の `fallbackFor="serif"` を維持し、香港用 family を追加します。
変換後の fonts.xml に `NotoSansCJK-Regular.ttc` / `NotoSerifCJK-Regular.ttc` の参照がないことを必須条件にしました。
元 ROM 全体の独立した XML ファイルも検査し、旧 TTC への参照が `/system/etc/fonts.xml` 以外にないことを確認しています。
APK 内や外部アプリによるファイル名のハードコードは検査対象外です。
旧 Sans TTC 内の Mono face は元の fonts.xml から参照されていません。

元 TTC の JP/KR/SC/TC の cmap と新 TTC の同地域の cmap を比較し、収録文字が欠落しないことも検証します。
香港 Serif は元 ROM に専用 face がなかったため、新しく公式 HK face を使用します。

インストールの順序:

1. 機種、ROM、XML、既存ファイルのハッシュを確認。
2. 新しい可変 TTC を一時名に展開・ハッシュ検証・権限設定して rename。
3. 新しい XML を同じ方式で配置。
4. 旧 TTC 2ファイルを削除し、不在を確認。既知の旧日本語 TTF も削除。

復元の順序:

1. ROM から抽出して ZIP に同梱した元 TTC 2ファイルを検証・配置。
2. 元 XML を配置。
3. 本パッチとハッシュが一致する可変フォントを削除。

これにより、元 XML が参照する旧 TTC を欠いたまま復元を終えることを避けます。
電源断をまたいだ全操作の原子性は保証しませんが、XML を切り替える前に参照先を配置します。
未変更 ROM、既知の日本語単独版 XML、同じ全 CJK 版 XML を受け付けます。
未知の XML や改変された旧 TTC は、削除や上書き前に拒否します。

テストでは5ロケールの対応・全ウェイト・非 CJK 設定の維持・不正参照の拒否・
導入と復元の順序・日本語単独版からの移行許可・SHA-256 ガードを確認しています。
ビルドでは両 ZIP の全内容と CRC を検証し、詳細を `dist/cjk-verification.json` に記録します。

## 実機適用結果

2026-09-17、日本語単独版を適用済みの cronos / TWRP 3.7.0_9-0 へ移行しました。
事前に元 ROM の PC バックアップ `twrp.ab` の SHA-256 が以前の検証値と一致することを確認。
System の空き容量は約1.8 GiBでした。

使用したインストール ZIP の SHA-256:
`ded123e7d9fb355ee829dbced7c4ca78d574861636b2dacda3b05c7b84dc428c`

TWRP に転送後も一致を確認し、`twrp install` は `script succeeded` を返しました。
配置直後と Android 再起動後に以下の SHA-256 を確認しました。

| ファイル | SHA-256 |
| --- | --- |
| fonts.xml | `d511966983c2fc98dfbb5633b336b74709806c4a7315efa10616e78536ce8e55` |
| NotoSansCJK-VF.ttf.ttc | `2abbfc7ff74a086cf2c1f5be6130528791cfd2c8b83466db5a1463aa63252ca7` |
| NotoSerifCJK-VF.ttf.ttc | `e0be8fdd4f01c9807ee856ee0d30147f663c5ab397c491c80134266f58d1fffe` |

3ファイルの root:root / 0644 / `u:object_r:system_file:s0` を確認しました。
旧 `NotoSansCJK-Regular.ttc`、`NotoSerifCJK-Regular.ttc`、日本語単独版 TTF 2ファイルは削除済み。
`sys.boot_completed=1`、system_server と System UI の稼働を確認し、クラッシュログは空でした。
画面上の日本語表示も確認しましたが、他ロケールの字形と全ウェイトの描画確認は未実施です。

証跡は `backups/20260917-pre-jp-fonts/` 内の `recovery-cjk-install.log`、
`after-cjk-boot.png`、`after-cjk-boot-crash.log` に保存しています。
ビルド結果 JSON の `device_tested: false` はビルド処理自体が実機テストを行わないことを示し、
今回の実機テスト結果はこの節に記録しています。
