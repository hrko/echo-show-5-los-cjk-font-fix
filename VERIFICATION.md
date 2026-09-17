# HOWTO_GEMINI.md の検証記録

2026-09-17 に、配置済み ROM、フォントの実データ、一次資料を照合しました。
元の `HOWTO_GEMINI.md` は比較用にそのまま残しています。

## 修正した点

| 元の手順 | 検証と採用した処理 |
| --- | --- |
| `.ttc` を参照 | 配置済みデータは単体の TrueType 可変フォント。実際の `.ttf` 名を参照。 |
| 日本語 family を丸ごと9行で置換 | 元の family はゴシック体と `fallbackFor="serif"` の明朝体を含む。両方の役割を維持して拡張。 |
| `postScriptName` を指定 | Android 11 の FontListParser はこの属性を読まないので省略。配置済みゴシック体の実名が `NotoSansCJKjp-Thin` なのは正しい。 |
| Android 15 と同等になる | Android 11 の `axis` 対応は確認できるが、OS 全体の挙動が Android 15 と同一とは保証できない。 |
| `/system` と `/system_root` をマウントして `/system` に展開 | 配置済み ext4 は `/system/etc/fonts.xml` を持つ system-as-root 構成。専用マウント以下の実パスに書き込む。 |
| 任意の ZIP の update-binary | 元の ROM に含まれる ARM32 ELF をそのまま使用。Magisk のインストーラーとの互換性を仮定しない。 |
| `set_perm` | Android 11 recovery の登録関数にない。`set_metadata` で root:root、0644、元と同じ SELinux ラベルを指定。 |
| マウント・展開結果の確認なし | マウント、ROM fingerprint、既存 XML、配置済み同名フォント、展開結果を検証。失敗時は中止。 |
| ブラウザだけで確認 | PC では XML・フォント輪郭・ZIPを検証。端末上ではブラウザとネイティブ UI の確認が必要。 |

追加要望の明朝体は `wght=200..900` なので8段階です。100の架空のインスタンスは作りません。
元の CJK TTC を削除しないため、中国語・韓国語の参照も維持します。

## 一次資料

GitHub 上のファイルは `gh api` で取得・確認しました。

- [Android 11 公式 fonts.xml](https://android.googlesource.com/platform/frameworks/base/+/android-11.0.0_r26/data/fonts/fonts.xml): `axis tag="wght" stylevalue="..."` の実例。
- [LineageOS 18.1 FontListParser](https://github.com/LineageOS/android_frameworks_base/blob/6432e2cf6632de03b8ba48d1d18825f1c9b5350c/graphics/java/android/graphics/FontListParser.java): weight、index、fallbackFor、axis の読み取り。
- [recovery install.cpp](https://github.com/LineageOS/android_bootable_recovery/blob/ac8c9e96627671e53a1aebdacaf9748b7241a3df/updater/install.cpp): 登録関数、mount、rename、set_metadata の返り値と失敗処理。
- [recovery updater_runtime.cpp](https://github.com/LineageOS/android_bootable_recovery/blob/ac8c9e96627671e53a1aebdacaf9748b7241a3df/updater/updater_runtime.cpp): マウントポイントの作成と mount 呼び出し。
- [blockimgdiff.py](https://github.com/LineageOS/android_build/blob/4fdba55d8946e7ede6d54422770b9bce45590924/tools/releasetools/blockimgdiff.py): OTA 転送リスト。今回の総書込みブロック数は `new` と `zero` の合計。
- [cronos BoardConfig](https://github.com/amazon-oss/android_device_amazon_cronos/blob/lineage-18.1/BoardConfig.mk)、[共通 fstab](https://github.com/amazon-oss/android_device_amazon_mt8163-common/blob/lineage-18.1/init/fstab.mt8163_legacy): パーティションとデバイス設定。最終的なパス・レイアウトの判断は配置済み ROM の updater-script と ext4 を優先。
- [Noto Sans CJK JP VF](https://github.com/notofonts/noto-cjk/blob/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Sans/Variable/TTF/NotoSansCJKjp-VF.ttf)、[Noto Serif CJK JP VF](https://github.com/notofonts/noto-cjk/blob/f8d157532fbfaeda587e826d4cd5b21a49186f7c/Serif/Variable/TTF/NotoSerifCJKjp-VF.ttf): 公式バイナリ。明朝体はこの固定版から取得。

手元のファイルに Git の blob ハッシュ計算を適用し、GitHub API の SHA と一致することを確認しました。
ビルドスクリプトも毎回この一致を検証します。

| ファイル | バイト数 | Git blob SHA-1 |
| --- | ---: | --- |
| NotoSansCJKjp-VF.ttf | 36,174,296 | `1196f022592989cd6a66cac06cddf81043bd53ba` |
| NotoSerifCJKjp-VF.ttf | 59,929,612 | `d2a12d4fb23c2cfe18942cbf1fea7dceb04dc2c1` |

両フォントのライセンス本文と内部 name テーブルの著作権表示を `licenses/` と ZIP に同梱しています。

## 実施した検証と限界

- Brotli の終端、new データ長、ブロック数と範囲、ext4 メタデータを検証して読み取り専用で抽出。
- ROM の元 XML を基準に、日本語以外の構造の一致と全フォント参照先の存在を確認。
- fvar / glyf / gvar、範囲、サンプル文字の存在、各ウェイトで異なる輪郭になることを fontTools で確認。
- 元ファイルの SELinux ラベルが `u:object_r:system_file:s0` であることを ext4 から確認。
- ZIP 全エントリーの CRC、入力とのバイト一致、update-binary の実行権限を確認。
- ホストの bash で SHA-256 ガードを実行し、一致・不一致・欠落・任意の既存ファイルの拒否をテスト。
  ホストテストでは BusyBox の呼出形式を模した shim を使い、実機 BusyBox の動作そのものは検証していません。

その後、2026-09-17 に対象実機で ARM update-binary / Edify の実行、書込み、起動を確認しました。
実機の TWRP は BusyBox ではなく Toybox を搭載していたため、両方に対応するよう修正しました。
詳細は [実機検証記録](DEVICE_VALIDATION.md) を参照してください。全ウェイト・全字形・復元の実行は未検証です。
ビルド時の検証結果と SHA-256 は `dist/verification.json` に記録します。
同ファイルの `device_tested: false` はビルド処理自体が実機テストを行わないことを示します。
