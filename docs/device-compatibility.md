# 3機種共通 ZIP の互換性検証

Echo Show 5 (2019 / checkers)、Echo Show 5 (2021 / cronos)、Echo Show 8 (2019 / crown) の、2026-09-04付の配布 ROM を対象にします。対応するリリースと利用手順は [README](../README.md) に記載しています。任意の LineageOS 18.1 ROM に適用できる ZIP ではありません。

## 共通化の根拠

3機種のデバイスツリーは、同じ [mt8163-common の BoardConfig](https://github.com/amazon-oss/android_device_amazon_mt8163-common/blob/lineage-18.1/BoardConfigCommon.mk) を継承しています。そこでは ARM32 userspace（`armeabi-v7a`）と ext4 System を指定しています。配布済み ROM も取得し、次の条件を確認しました。

| 項目 | 3機種の照合結果 |
| --- | --- |
| Android / LineageOS | SDK 30 / 18.1 |
| System イメージ内の配置 | `/system/etc/fonts.xml` と `/system/fonts/` |
| `fonts.xml` SHA-256 | `6a44c329b05d78eac0fc9f8a49edfbaaa6c8ebd13b80af09e26e1dab1163f6da`（完全一致） |
| 通常フォントファイル | 255ファイルの名前・SHA-256 が一致 |
| 元 CJK TTC への参照 | System イメージ内の通常 XML では `/system/etc/fonts.xml` のみ |
| XML・元 CJK TTC の SELinux label | `u:object_r:system_file:s0` |
| ROM updater の System 書き込み先 | `/dev/block/platform/soc/11230000.mmc/by-name/system` |

この一致により、同じ XML 断片とフォントを使って導入・復元できます。復元 ZIP に同梱する CJK の元 TTC も3機種共通です。ROM が異なる場合に端末の元設定を保存して対応する機能は追加していません。

## ビルドと適用時の検証

[scripts/targets.py](../scripts/targets.py) に、3機種の ROM ファイル名・配布リリース・固定 SHA-256・fingerprint を定義しています。[scripts/verify_targets.py](../scripts/verify_targets.py) は、ビルドの前に全 ROM を検証・展開して上記の共通条件を照合します。1機種でも不一致なら共通 ZIP の生成を中止します。結果は `build/compatibility.json` と、各 ZIP の `verification.json` 内の `compatibility` に記録します。

同梱する実行用 updater は、従来と同じ cronos ROM 由来の ARM32 バイナリです。3機種の ROM 付属 updater 自体はバイト列が異なり、同一であるとは扱いません。共通 ZIP は汎用の Edify 操作でマウント・属性設定・ファイル配置を行い、フォントの検証と XML の合成には同梱 ARMv7 Python を使います。検証 JSON の従来の `rom` は、この基準 ROM を指します。対応 ROM の全一覧は `compatibility.roms` を参照してください。

適用時には、リカバリーが報告する機種、System の `ro.product.system.device`、その機種用の `ro.system.build.fingerprint` の組み合わせを検証します。対象機種でも別の ROM ビルドなら拒否します。その後、従来と同じ [v1 の XML・フォント検証](patch-format.md) を行います。機種名の許可だけを根拠にファイルを書き換えることはありません。

## 旧版からの移行と確認範囲

XML の担当範囲、置換するフォント、復元用断片は従来の cronos 版と同じです。対象 cronos ROM 上で同じフォント版の旧 ZIP を適用済みの場合、共通 ZIP で再適用・個別復元できます。別機種へ旧 cronos ZIP を適用することはできません。

ホストでは、対応する機種と fingerprint の組み合わせ、不一致・未知の ROM の拒否、3つの元 XML に対する生成 ZIP の適用・復元を確認します。既存の4パッチの全24通りの導入順序と独立復元のテストも継続します。

2026-09-18 に、cronos 上で **共通 Mono install ZIP の再適用1回と Android 起動**を確認しました。初期の4パッチ併用状態を維持し、XML とフォントのハッシュが適用前後で一致しました。[最小実機検証記録](common-zip-device-validation.md)を参照してください。

checkers / crown と、共通版の他の install ZIP・restore ZIP は実機未検証です。共通版での描画の再検証も実施していません。従来の詳細な実機検証記録は cronos 専用版についてのものです。
