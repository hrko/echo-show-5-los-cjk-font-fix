# Echo Show 可変フォントパッチ

Echo Show の LineageOS 18.1（Android 11）に、可変フォントを導入する TWRP ZIP を生成します。**各パッチの同じ ZIP を、以下の3機種の対象 ROM で使用できます。**

| 機種 | コードネーム | 対象 ROM（配布ファイルの日付はすべて2026-09-04） |
| --- | --- | --- |
| Echo Show 5 (2019・第1世代) | `checkers` | [v0.7](https://github.com/amazon-oss/releases/releases/tag/lineage-18.1-checkers-v0.7) |
| Echo Show 5 (2021・第2世代) | `cronos` | [v0.4](https://github.com/amazon-oss/releases/releases/tag/lineage-18.1-cronos-v0.4) |
| Echo Show 8 (2019・第1世代) | `crown` | [v0.5](https://github.com/amazon-oss/releases/releases/tag/lineage-18.1-crown-v0.5) |

対象ファイル名は `lineage-18.1-20260904-UNOFFICIAL-{コードネーム}.zip` です。3つの ROM の `fonts.xml` と255個の通常フォントファイルが一致することをビルド時に検証します。他の ROM・世代は拒否します。**共通版の実機検証は、cronos 上の Mono install ZIP の再適用と Android 起動のみです。** checkers / crown と他の共通 ZIP はホスト検証のみです。[3機種の互換性検証](docs/device-compatibility.md)と [最小実機検証記録](docs/common-zip-device-validation.md)を参照してください。

各パッチは個別に導入・復元でき、併用も可能です。

| パッチ | 変更内容 | ウェイト | System 空き容量の目安 |
| --- | --- | --- | --- |
| CJK | Noto Sans CJK / Serif CJK（日本語・韓国語・簡体字・繁体字・香港繁体字） | Sans: 100〜900、Serif: 200〜900 | 約160 MiB以上 |
| 欧文（latin） | `sans-serif` / `sans-serif-condensed` を Google Sans Flex に変更 | 100〜900 | 約10 MiB以上 |
| Serif | `serif` を Noto Serif VF に変更 | 100〜900 | 約10 MiB以上 |
| Mono | `monospace` を Google Sans Code VF に変更 | 300〜800 | 約10 MiB以上 |

欧文・Serif・Mono は通常体とイタリック体に対応します。表の範囲外のウェイトを指定すると、その範囲の最小値または最大値に対応します。複数のパッチを併用する場合は、表の空き容量を合計して確保してください。

## ZIP のダウンロード

1. [最新リリース](https://github.com/hrko/echo-show-5-lineageos-variable-fonts/releases/latest)を開きます。
2. **Assets** から、使用するパッチの `echo-show-{component}-fonts-install.zip`（導入用）と `echo-show-{component}-fonts-restore.zip`（復元用）をダウンロードします。`{component}` は `cjk`・`latin`・`serif`・`mono` のいずれかです。日本語フォントを変更する場合は `cjk` を選びます。
3. ダウンロードした ZIP は展開せず、以下の手順で端末へ転送して適用します。

リリースの `Source code (zip)` と `Source code (tar.gz)` はソースコードのアーカイブです。TWRP で適用するファイルは、上記の install / restore ZIP です。配布 ZIP を使う場合、ビルドは不要です。

## 導入・復元

1. 対象 ROM を確認し、**TWRP で System をバックアップ**します。[PC に直接保存する手順](docs/twrp-pc-backup.md)は cronos での記録です。他機種では TWRP の表示やバックアップ方法を確認してください。
2. 使用するパッチの `echo-show-{component}-fonts-install.zip` と `echo-show-{component}-fonts-restore.zip` を端末へ転送します。`{component}` は `cjk`・`latin`・`serif`・`mono` のいずれかです。
3. TWRP の Mount で System をアンマウントし、Install から install ZIP を適用します。複数のパッチは任意の順序で導入できます。ZIP は未署名のため、ZIP signature verification が有効なら解除してください。
4. 成功表示を確認して System へ再起動します。

パッチを取り除く場合は、対応する restore ZIP を適用します。そのパッチの担当部分だけが元に戻り、他のパッチは維持されます。導入したすべてのパッチを取り除くと、元 ROM のフォント設定に戻ります。

- **併用には現行の実装で生成した CJK ZIP を使ってください。** XML 全体のハッシュを検証する旧 CJK ZIP は、欧文との併用状態に対応しません。旧版で CJK を導入済みの場合も、現行の CJK ZIP で再適用・復元できます。
- 対象 cronos ROM に従来の `cronos-*-fonts-*.zip` を導入済みの場合も、同じフォント版の共通 ZIP で再適用・個別復元できます。XML の担当範囲とフォントの内容は維持しています。
- 想定外のデバイス・ROM・設定では処理を中止します。復元を拒否された場合は System バックアップを使用してください。
- 処理に失敗した場合はエラーを確認し、再試行前にリカバリーを再起動してください。
- ROM 更新後の自動維持には対応していません。

TWRP の `/sbin/sh` と、`env -i` が使える `/sbin/toybox` または `/sbin/busybox` が必要です。実行用 Python は ZIP に同梱します。

## ビルド

mise と Python 3.14 を使用します。初回は約1.6 GBのダウンロードと、少なくとも約12 GBの追加空き容量が必要です。3機種分の ROM を取得・展開します。

```powershell
mise install
mise exec -- uv sync --locked --cache-dir .uv-cache
mise run check
mise run fetch-assets
mise run build
mise run test
```

`dist/` に各パッチの install / restore ZIP、検証結果の `echo-show-{cjk,latin,serif,mono}-fonts-verification.json`、`SHA256SUMS.txt` を出力します。入力ファイルは固定ハッシュで検証し、一致する既存ファイルは再利用します。

展開済みの `build/system.img`、`build/checkers/system.img`、`build/crown/system.img` も再利用するため、手動で変更した場合は該当ファイルを削除して再ビルドしてください。`build/compatibility.json` と各検証 JSON の `compatibility` に、3機種の ROM ハッシュ・fingerprint・元フォントの照合結果を記録します。古い `cronos-*` の成果物が `dist/` に残っていても、新しい `SHA256SUMS.txt` とリリースには含めません。

## 実機検証と関連資料

従来の cronos 専用 ZIP は、2026-09-18 に Echo Show 5 (2021) / TWRP 3.7.0_9-0 で導入・個別復元・再適用・Android 起動を確認しました。実機検証の対象 ZIP と確認項目は、以下の記録に記載しています。全言語・全ウェイト・すべてのフォールバックの描画は確認していません。フォールバックによって字形や幅が変わる場合があります。

- 実機検証記録：[CJK・欧文](docs/python-device-validation.md) / [Serif・Mono](docs/serif-mono-device-validation.md)
- 目視確認用ページ：[CJK](font-test.html) / [欧文](latin-font-test.html)（ブラウザの影響があるため、ネイティブ UI も確認してください）
- [フォントの出典・設定・ライセンス、ビルド・リリースの詳細](docs/font-and-build-details.md)
- [独立適用の仕組み](docs/patch-format.md) / [同梱 Python の出典・ライセンス](docs/python-runtime.md)
