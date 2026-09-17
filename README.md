# Echo Show 5 可変フォントパッチ

Echo Show 5 第2世代（cronos）の LineageOS 18.1（Android 11）に、可変フォントを導入する TWRP ZIP を生成します。対象 ROM は **`lineage-18.1-20260904-UNOFFICIAL-cronos.zip` のみ**です。他の ROM・世代には対応しません。

各パッチは個別に導入・復元でき、併用も可能です。

| パッチ | 変更内容 | ウェイト | System 空き容量の目安 |
| --- | --- | --- | --- |
| CJK | Noto Sans CJK / Serif CJK（日本語・韓国語・簡体字・繁体字・香港繁体字） | Sans: 100〜900、Serif: 200〜900 | 約160 MiB以上 |
| 欧文（latin） | `sans-serif` / `sans-serif-condensed` を Google Sans Flex に変更 | 100〜900 | 約10 MiB以上 |
| Serif | `serif` を Noto Serif VF に変更 | 100〜900 | 約10 MiB以上 |
| Mono | `monospace` を Google Sans Code VF に変更 | 300〜800 | 約10 MiB以上 |

欧文・Serif・Mono は通常体とイタリック体に対応します。表の範囲外のウェイトを指定すると、その範囲の最小値または最大値に対応します。複数のパッチを併用する場合は、表の空き容量を合計して確保してください。

## 導入・復元

1. 対象 ROM を確認し、**TWRP で System をバックアップ**します。[PC に直接保存する手順](docs/twrp-pc-backup.md)も利用できます。
2. 使用するパッチの `cronos-{component}-fonts-install.zip` と `cronos-{component}-fonts-restore.zip` を端末へ転送します。`{component}` は `cjk`・`latin`・`serif`・`mono` のいずれかです。
3. TWRP の Mount で System をアンマウントし、Install から install ZIP を適用します。複数のパッチは任意の順序で導入できます。ZIP は未署名のため、ZIP signature verification が有効なら解除してください。
4. 成功表示を確認して System へ再起動します。

パッチを取り除く場合は、対応する restore ZIP を適用します。そのパッチの担当部分だけが元に戻り、他のパッチは維持されます。導入したすべてのパッチを取り除くと、元 ROM のフォント設定に戻ります。

- **併用には現行の実装で生成した CJK ZIP を使ってください。** XML 全体のハッシュを検証する旧 CJK ZIP は、欧文との併用状態に対応しません。旧版で CJK を導入済みの場合も、現行の CJK ZIP で再適用・復元できます。
- 想定外のデバイス・ROM・設定では処理を中止します。復元を拒否された場合は System バックアップを使用してください。
- 処理に失敗した場合はエラーを確認し、再試行前にリカバリーを再起動してください。
- ROM 更新後の自動維持には対応していません。

TWRP の `/sbin/sh` と、`env -i` が使える `/sbin/toybox` または `/sbin/busybox` が必要です。実行用 Python は ZIP に同梱します。

## ビルド

mise と Python 3.14 を使用します。初回は約590 MBのダウンロードと、少なくとも約4 GBの追加空き容量が必要です。

```powershell
mise install
mise exec -- uv sync --locked --cache-dir .uv-cache
mise run check
mise run fetch-assets
mise run build
mise run test
```

`dist/` に各パッチの install / restore ZIP、検証結果の `cronos-{cjk,latin,serif,mono}-fonts-verification.json`、`SHA256SUMS.txt` を出力します。入力ファイルは固定ハッシュで検証し、一致する既存ファイルは再利用します。

展開済みの `build/system.img` も再利用するため、手動で変更した場合は削除して再ビルドしてください。

## 実機検証と関連資料

2026-09-18 に TWRP 3.7.0_9-0 で導入・個別復元・再適用・Android 起動を確認しました。実機検証の対象 ZIP と確認項目は、以下の記録に記載しています。全言語・全ウェイト・すべてのフォールバックの描画は確認していません。フォールバックによって字形や幅が変わる場合があります。

- 実機検証記録：[CJK・欧文](docs/python-device-validation.md) / [Serif・Mono](docs/serif-mono-device-validation.md)
- 目視確認用ページ：[CJK](font-test.html) / [欧文](latin-font-test.html)（ブラウザの影響があるため、ネイティブ UI も確認してください）
- [フォントの出典・設定・ライセンス、ビルド・リリースの詳細](docs/font-and-build-details.md)
- [独立適用の仕組み](docs/patch-format.md) / [同梱 Python の出典・ライセンス](docs/python-runtime.md)
