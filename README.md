# Echo Show 5 可変フォントパッチ

Echo Show 5 **第2世代（cronos）/ LineageOS 18.1（Android 11）** のフォントを変更する TWRP ZIP を生成します。
対象 ROM は `lineage-18.1-20260904-UNOFFICIAL-cronos.zip` のみです。他の ROM・世代には対応しません。

各パッチは個別に導入・復元でき、併用も可能です。

| パッチ | 変更内容 | ウェイト | System 空き容量の目安 |
| --- | --- | --- | --- |
| CJK | Noto Sans CJK / Serif CJK（日本語・韓国語・簡体字・繁体字・香港繁体字） | Sans: 100〜900、Serif: 200〜900 | 約160 MiB以上 |
| 欧文（latin） | `sans-serif` / `sans-serif-condensed` を Google Sans Flex に変更 | 100〜900 | 約10 MiB以上 |
| Serif | `serif` を Noto Serif VF に変更 | 100〜900 | 約10 MiB以上 |
| Mono | `monospace` を Google Sans Code VF に変更 | 300〜800 | 約10 MiB以上 |

欧文・Serif・Mono は通常体とイタリック体に対応します。範囲外のウェイト指定は端のウェイトにマッチします。併用時は必要な空き容量を合計してください。

## 導入・復元

1. 対象 ROM を確認し、**TWRP で System をバックアップ**します。[PC に直接保存する手順](docs/twrp-pc-backup.md)も利用できます。
2. 使用するパッチの `cronos-{cjk,latin,serif,mono}-fonts-install.zip` と対応する `restore.zip` を端末へ転送します。
3. TWRP の Mount で System をアンマウントし、Install から install ZIP を適用します。併用時の順序は任意です。ZIP は未署名のため、ZIP signature verification が有効なら解除してください。
4. 成功表示を確認して System へ再起動します。

戻す場合は対応する restore ZIP を適用します。他のパッチは維持され、導入したすべてのパッチを復元すると元 ROM のフォント設定に戻ります。

- **併用には本バージョンで生成した CJK ZIP を使ってください。** 旧 CJK ZIP は欧文との併用状態を扱えません。旧 CJK 版の導入済み状態は本バージョンの ZIP で扱えます。
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

## 検証・詳細

2026-09-18 に TWRP 3.7.0_9-0 で導入・個別復元・再適用・Android 起動を確認しています。全言語・全ウェイト・すべてのフォールバックの描画を保証するものではありません。フォールバックによって字形や幅が変わる場合があります。

- 実機検証記録：[CJK・欧文](docs/python-device-validation.md) / [Serif・Mono](docs/serif-mono-device-validation.md)
- 目視確認用ページ：[CJK](font-test.html) / [欧文](latin-font-test.html)（ブラウザの影響があるため、ネイティブ UI も確認してください）
- [フォントの出典・設定・ライセンス、ビルド・リリースの詳細](docs/font-and-build-details.md)
- [独立適用の仕組み](docs/patch-format.md) / [同梱 Python の出典・ライセンス](docs/python-runtime.md)
