# 独立フォントパッチ形式 v1

この形式は、[README に記載した対象 ROM](../README.md) の `fonts.xml` を、パッチごとの担当範囲に分けて変更・復元するためのものです。担当範囲を「スロット」と呼びます。

XML の分解・合成には、ホストとリカバリーで共通の `scripts/font_slots.py` を使います。端末側では `recovery/font_patch.py` が検証・合成と、書き込み前のファイル準備（ステージング）を行います。実行用の ARMv7 Python は ZIP に同梱し、TWRP の `/tmp` で起動します。[ランタイムの詳細](python-runtime.md)を参照してください。

## 各パッチの担当スロット

| コンポーネント | スロット | 対象 |
| --- | --- | --- |
| latin | latin-sans / latin-condensed | sans-serif / sans-serif-condensed |
| cjk | cjk-sc / cjk-tc / cjk-ja / cjk-ko | 既存の4言語ファミリーと追加の香港ファミリー |
| serif | serif | 名前付き serif |
| mono | mono | 名前付き monospace |

CJK の `fallbackFor="serif"` は CJK パッチの担当です。Serif パッチが置換する名前付き `serif` ファミリーとは区別します。

スロットの開始・終了タグと位置は固定します。各スロットの直後には、`    <!-- font-slot: SLOT fallback -->` と無名の `<family>` を1つ追加できます。`SLOT` はスロット名に置き換えます。この補助ファミリーも同じスロットに含め、復元時に取り除きます。欧文パッチでは元 Roboto の `fallbackFor` 登録に使います。香港ファミリーは繁体字ファミリーの直前に置き、`cjk-tc` に含めます。

スロット以外のバイト列は、共通構造（skeleton）として保持します。全8スロットをマーカーに置換した XML の SHA-256 が、元 ROM から求めた固定値と一致しなければ処理を中止します。分解した XML を再合成し、入力とバイト単位で一致することも確認するため、行末などの意図しない変更を検出できます。

## 検証境界

操作対象のスロットは、元 ROM または適用する ZIP の置換後データとハッシュが一致する場合だけ受け付けます。担当外スロットの内容は変更せず、その検証は担当するパッチに任せます。このため、担当外の不正なフォント指定は検出・修正しません。担当外スロット内の独自変更は受け付けますが、スロットの境界や共通構造の変更は拒否します。

`patch/format` の値は `1` です。`patch/slots.txt` には、担当スロットだけを `slot stock_sha256 patched_sha256 desired_sha256` の4列で列挙します。各列はスロット名、元 ROM のハッシュ、置換後のハッシュ、今回書き込む断片のハッシュです。同梱する断片も `desired_sha256` と照合します。他パッチのバージョンや有無による条件分岐はなく、端末に永続的な導入履歴や共有バックアップも作りません。

## 書き込みと復元

1. 機種・ROM fingerprint・必要な recovery コマンドを確認。
2. `/tmp` で XML を分解し、共通構造と操作対象スロットを検証・合成。
3. 上書き・削除対象の既存フォントをハッシュ照合。欧文版は残す元 Roboto 全20ファイルも照合。
4. 導入時は新フォント、CJK 復元時は元 TTC を先に展開し、ハッシュ・属性を設定して rename。
5. XML が準備時から変化していないことを照合。合成 XML を同一ファイルシステムの `.jpfont-new` にコピー・検証し、属性設定後 rename。
6. 不要なフォントを削除。CJK 導入時は合成 XML に元 TTC の参照が残ると手順2で中止。復元時は追加フォントのハッシュが一致し、合成後 XML から参照されない場合だけ削除。

フォントの配置後に XML を切り替え、不要なフォントは最後に削除します。この順序により、配置前の新フォントを XML が参照することを避けます。ただし、複数ファイルへの変更を電源断時にも一括して確定・取り消しする機能や、自動ロールバックはありません。作業前に System をバックアップし、空き容量不足やエラーが発生した場合はリカバリーを再起動してから再試行してください。

全コンポーネントを復元すれば、通常の導入状態から元 XML と元フォント集合に戻ります。ユーザーが変更した追加フォントや他スロットが参照する追加フォントは削除しません。

## パッチの実装・更新時の互換性

- v1 の境界・skeleton・改行を変更せず、既存スロット内だけを置換すること。必要なら契約済みの補助 family を使用。
- `payload(..., component="serif" / "mono")` を使って独立 ZIP を生成すること。共有 fonts.xml のスナップショット全体を復元しないこと。
- 追加ファイル名はコンポーネント専用にすること。他コンポーネント所有の追加フォントを共有・削除しないこと。
- 元ファイルを残す場合は復元前に検証、削除する場合は全設定の参照調査と復元 ZIP への同梱を行うこと。
- 新しい同一コンポーネントのフォント版へ更新する場合は、原則として旧版の restore ZIP を適用してから新版を入れること。未知の同一スロットを自動上書きしない。
- 境界・共通構造を変える拡張は v1 と非互換。既存 ZIP を黙って互換扱いにせず、新形式と移行手順を用意すること。

ホストテストでは実際の Serif・Mono パッチを使い、CJK・欧文と合わせた全24通りの導入順序で、各パッチを個別に復元できることを確認します。

XML 全体のハッシュを検証する旧 CJK ZIP は、他パッチとの併用状態に対応しません。旧版で CJK を導入した状態は、現行の CJK ZIP が同一の CJK 断片として認識するため、再適用・復元できます。

## Android 11 のフォント設定を扱うソース

- [FontListParser.java](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-11.0.0_r1/graphics/java/android/graphics/FontListParser.java): weight / style / axis / fallbackFor の読み取り。
- [SystemFonts.java](https://github.com/aosp-mirror/platform_frameworks_base/blob/android-11.0.0_r1/graphics/java/android/graphics/fonts/SystemFonts.java): 無名ファミリーの fallbackFor 別の登録。default font のない専用 fallback は指定されたファミリーだけに追加。

上記は XML の解釈を確認するためのソースです。ソースとホストテストだけでは、対象端末での描画や TWRP 上の動作、Android の起動までは確認できません。実機で確認した範囲は、[CJK・欧文の検証記録](python-device-validation.md)と [Serif・Mono の検証記録](serif-mono-device-validation.md)を参照してください。
