# 独立フォントパッチ形式 v1

対象は固定した cronos ROM の fonts.xml。`scripts/font_slots.py` をホストと recovery で共有し、`recovery/font_patch.py` が端末側の検証・合成・ステージングを行います。ZIP に ARMv7 Python を同梱し、TWRP の `/tmp` のみで起動します。[ランタイムの詳細](python-runtime.md)を参照してください。

## 所有権

| コンポーネント | スロット | 対象 |
| --- | --- | --- |
| latin | latin-sans / latin-condensed | sans-serif / sans-serif-condensed |
| cjk | cjk-sc / cjk-tc / cjk-ja / cjk-ko | 既存の4言語ファミリーと追加の香港ファミリー |
| serif | serif | 名前付き serif |
| mono | mono | 名前付き monospace |

CJK の `fallbackFor="serif"` は引き続き CJK 所有です。名前付き serif 置換がこの部分を編集してはいけません。

スロットの開始・終了タグと位置を固定します。各スロットには直後に `    <!-- font-slot: SLOT fallback -->` と無名 `<family>` 1つを付加できます。これは同じスロットの所有物で、復元時に一緒に取り除きます。欧文版では元 Roboto の `fallbackFor` 登録に使います。香港ファミリーは繁体字ファミリーの直前に置き、cjk-tc に含めます。

それ以外のバイト列は共通構造（skeleton）です。全8スロットをマーカーへ置換した SHA-256 が ROM 由来の固定値と一致しなければ中止します。全体を分割・再合成して元入力ハッシュと一致することも確認し、行末などの暗黙の書き換えを防ぎます。

## 検証境界

操作対象のスロットは元 ROM または今回の ZIP が生成する内容とハッシュが一致する場合だけ受け付けます。**担当外スロットの内容は、そのパッチの責任で検証し、ここでは保持します。** 担当外の不正なフォント指定を検出・修正する仕組みではありません。別の担当領域に独自変更があることだけでは拒否しませんが、境界や共通構造の変更は拒否します。

`patch/format` は `1`、`slots.txt` は `slot stock_sha256 patched_sha256 desired_sha256` の4列です。自分のスロットだけを列挙します。断片も desired SHA-256 と照合します。他パッチのバージョンや有無を条件分岐しません。端末に永続的な導入履歴や共有バックアップは作りません。

## 書き込みと復元

1. 機種・ROM fingerprint・必要な recovery コマンドを確認。
2. `/tmp` で XML を分解し、共通構造と操作対象スロットを検証・合成。
3. 上書き・削除対象の既存フォントをハッシュ照合。欧文版は残す元 Roboto 全20ファイルも照合。
4. 導入時は新フォント、CJK 復元時は元 TTC を先に展開し、ハッシュ・属性を設定して rename。
5. XML が準備時から変化していないことを照合。合成 XML を同一ファイルシステムの `.jpfont-new` にコピー・検証し、属性設定後 rename。
6. 不要なフォントを削除。CJK 導入時は合成 XML に元 TTC の参照が残ると手順2で中止。復元時は追加フォントのハッシュが一致し、合成後 XML から参照されない場合だけ削除。

中断時に元 XML が新フォントの欠落を参照しない順序を維持します。ただし複数ファイル全体の電源断に対するトランザクションや自動ロールバックではありません。空き容量不足やエラー後はリカバリーを再起動して再試行してください。System バックアップも必要です。

全コンポーネントを復元すれば、通常の導入状態から元 XML と元フォント集合に戻ります。ユーザーが変更した追加フォントや他スロットが参照する追加フォントは削除しません。

## serif / mono の実装と今後の拡張

- v1 の境界・skeleton・改行を変更せず、既存スロット内だけを置換すること。必要なら契約済みの補助 family を使用。
- `payload(..., component="serif" / "mono")` を使って独立 ZIP を生成すること。共有 fonts.xml のスナップショット全体を復元しないこと。
- 追加ファイル名はコンポーネント専用にすること。他コンポーネント所有の追加フォントを共有・削除しないこと。
- 元ファイルを残す場合は復元前に検証、削除する場合は全設定の参照調査と復元 ZIP への同梱を行うこと。
- 新しい同一コンポーネントのフォント版へ更新する場合は、原則として旧版の restore ZIP を適用してから新版を入れること。未知の同一スロットを自動上書きしない。
- 境界・共通構造を変える拡張は v1 と非互換。既存 ZIP を黙って互換扱いにせず、新形式と移行手順を用意すること。

ホストテストでは 実際の serif/mono の置換を使い、CJK/欧文と合わせて全24導入順序で独立復元を確認します。旧来の全体ハッシュ方式で生成した CJK ZIP 自体には前方互換性はありません。旧版の導入結果は、新しい CJK ZIP が同一の CJK 断片として認識します。

## Android 11 の根拠

- [FontListParser.java](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-11.0.0_r1/graphics/java/android/graphics/FontListParser.java): weight / style / axis / fallbackFor の読み取り。
- [SystemFonts.java](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-11.0.0_r1/graphics/java/android/graphics/fonts/SystemFonts.java): 無名ファミリーの fallbackFor 別の登録。default font のない専用 fallback は指定されたファミリーだけに追加。

これはソース仕様とホスト処理の検証です。対象端末上での Minikin / FreeType の描画、TWRP の applet 実装、起動は別途実機検証が必要です。
