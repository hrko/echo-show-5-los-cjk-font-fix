# Echo Show 5 可変フォントパッチ

Echo Show 5 **第2世代（cronos）/ LineageOS 18.1（Android 11）** 向けに、CJK と欧文をそれぞれ独立して導入・復元する TWRP ZIP を生成します。

- 対象 ROM: `lineage-18.1-20260904-UNOFFICIAL-cronos.zip`。他の ROM・世代には対応しません。
- CJK: 公式 Noto Sans CJK / Serif CJK。日本語・韓国語・簡体字・繁体字（注音を含む）・香港繁体字。ゴシック体は100〜900、明朝体は200〜900（100の指定は200にマッチ）。
- 欧文: `sans-serif` と `sans-serif-condensed` を公式公開版 Google Sans Flex に変更。100〜900の9段階、通常・イタリック。
- Serif: 名前付き `serif` を Noto Serif VF に変更。100〜900、通常・イタリック。
- Mono: 名前付き `monospace` を Google Sans Code VF に変更。300〜800、通常・イタリック。範囲外の指定は端のウェイトへマッチ。

従来の CJK 版では実機で導入 → 復元 → 再導入・正常起動・日本語の全ウェイトの描画を確認済みです。今回の Python 版は、2026-09-18 に TWRP 3.7.0_9-0 で独立導入・復元の8遷移、再適用、ファイル・属性・Android 起動を確認しました。[実機検証記録](docs/python-device-validation.md)を参照してください。この CJK・欧文の検証での表示確認はユーザーによる手動確認とし、全ウェイト・言語・フォールバックの描画確認済みとは扱いません。Serif / Mono の実機描画検証は下記の別記録を参照してください。

## 導入・復元

1. 対象 ROM が入っていることを確認し、**TWRP で System をバックアップ**します。[PC に直接保存する手順](docs/twrp-pc-backup.md)も利用できます。
2. 希望するパッチの install / restore ZIP を端末へ転送します。CJK は `cronos-cjk-fonts-*`、欧文は `cronos-latin-fonts-*`、Serif は `cronos-serif-fonts-*`、Mono は `cronos-mono-fonts-*` です。
3. TWRP の Mount で System をアンマウントし、Install から希望する install ZIP を選びます。併用する場合、順序は任意です。
   ZIP は未署名のため、ZIP signature verification が有効なら解除してください。
4. 成功表示を確認して System へ再起動します。

System の空き容量は CJK が**約160 MiB以上**、欧文単独が**約10 MiB以上**を推奨します。併用する場合は両方の余裕を確保してください。
TWRP の `/sbin/sh` と、`env -i` が使える `/sbin/toybox` または `/sbin/busybox` が必要です。ARMv7 CPython と musl を ZIP に同梱し、`/tmp` で実行します（展開後約15.1 MiB）。awk や System への Python インストールは不要です。[出典・固定ハッシュ・ライセンス](docs/python-runtime.md)を参照してください。
想定外のデバイス・ROM・設定では処理を中止します。

戻す場合は対応する restore ZIP をフラッシュします。他のパッチは維持されます。導入した各パッチの restore ZIP を適用すれば元 ROM のフォント設定に戻ります。
**併用には今回生成した CJK ZIP を使ってください。** 旧 CJK ZIP は XML 全体を照合するため、欧文併用状態では拒否します。旧 CJK 版の導入済み状態は今回の ZIP で扱えます。
共通構造・エイリアス・操作対象の担当部分が想定外で復元を拒否された場合は、System バックアップで復元してください。他の担当部分は変更せず保持しますが、その内容の正当性は他のパッチ側の責任です。
処理に失敗した場合はエラーを確認し、再試行前にリカバリーを再起動してください。
ROM 更新後の自動維持には対応していません。

## 欧文フォントの出典と設定

[Google Fonts の公式配布](https://github.com/google/fonts/tree/3dc14e61f108f036db84188b9b405a67df9b7c88/ofl/googlesansflex)を使用します。開発元は [googlefonts/googlesans-flex](https://github.com/googlefonts/googlesans-flex) です。

- 固定コミット: `3dc14e61f108f036db84188b9b405a67df9b7c88`
- 元ファイル: `GoogleSansFlex[GRAD,ROND,opsz,slnt,wdth,wght].ttf`。取得 URL は [fetch_assets.py](scripts/fetch_assets.py) に固定。
- 内部バージョン: `Version 4.005;[3fe7d0b9f]`
- SHA-256: `c31a482fbecbf2e07e6890134d20078723aadf732c9b9c6c9a44f86f8265b6fe`
- ライセンス: [SIL Open Font License 1.1](licenses/GoogleSansFlex-OFL.txt)、Reserved Font Names なし。[商標に関する通知](licenses/GoogleSansFlex-TRADEMARKS.md)も同梱。両文書は公式の原文・Git blob を検証します。
- 配布 TTF のバイト列は変更せず、保存名のみ `GoogleSansFlex-Regular.ttf` にします。Pixel 抽出フォントは同梱しません。

| 軸 | 公開版の最小 / 既定 / 最大 | 採用値 |
| --- | --- | --- |
| `wght` | 1 / 400 / 1000 | 100〜900、100刻み |
| `wdth` | 25 / 100 / 151 | sans-serif: 100、condensed: 75 |
| `slnt` | -10 / 0 / 0 | 通常: 0、イタリック: -10 |
| `opsz` | 6 / 18 / 144 | 18 |
| `GRAD` | 0 / 0 / 100 | 0 |
| `ROND` | 0 / 0 / 100 | 0 |

`opsz / GRAD / ROND` は公開版の既定値を明示します。ローカル調査済み Pixel 9 / CP3A.260905.009 の汎用 `google-sans-flex` もこの3軸を指定せず同じ既定値を使用しています。用途別の可変 display/body 設定は移植せず、文字サイズによる opsz の自動変更も行いません。

これは独自の設定です。調査した Pixel の標準 sans-serif は Roboto であり、Google Sans Flex ではありません。Pixel 同梱版は 4.001、採用公開版は 4.005 です。

Android 11 の `family` / `font weight/style` / `axis tag/stylevalue` を使い、両ファミリーに18エントリーずつ明示します。Android 17 の `family-list` / `supportedAxes` は使用しません。ウェイト別エイリアス、CJK の順序・言語指定は維持します。

公開版の cmap は535文字で、元の各 Roboto フォントにある2,263コードポイントを含みません。ギリシャ文字・キリル文字・一部の拡張ラテン文字などを失わないよう、**元 Roboto / RobotoCondensed を削除せず、それぞれの `fallbackFor` を指定した補助ファミリーを登録**します。既存 CJK ファミリーの相対順序は変えません。使用文字が Google Sans Flex にない場合は Google Sans Flex の字形にはなりません。

## Noto Serif / Google Sans Code の出典と設定

Google Sans Flex と同じ固定コミット `3dc14e61f108f036db84188b9b405a67df9b7c88` の公式 Google Fonts 配布を使用します。

| パッチ | 公式配布 | 軸と採用値 | 内部バージョン（通常 / イタリック） |
| --- | --- | --- | --- |
| serif | [Noto Serif](https://github.com/google/fonts/tree/3dc14e61f108f036db84188b9b405a67df9b7c88/ofl/notoserif) | `wght`: 100〜900、`wdth`: 100 固定 | 2.015 / 2.013 |
| mono | [Google Sans Code](https://github.com/google/fonts/tree/3dc14e61f108f036db84188b9b405a67df9b7c88/ofl/googlesanscode) | `wght`: 300〜800 | 6.001 / 6.001 |

通常体とイタリック体はそれぞれ独立した VF を使い、100刻みのウェイトを Android 11 の `font` / `axis` で登録します。この Google Sans Code 配布版には `MONO` 軸はありません。各ウェイト・スタイルでASCII文字の送り幅が等しいことをビルド時に検証します。フォールバック先の文字まで同じ幅になる保証はありません。

TTF は保存名のみ変更し、バイト列は変更しません。[named_fonts.py](scripts/named_fonts.py) に URL・Git blob・軸・バージョンを固定し、検証 JSON には SHA-256・字形検証結果・収録文字差分を記録します。元の Noto Serif 4ファイルと DroidSansMono は残し、専用の `fallbackFor` を設定・ファイルハッシュを照合します。CJK の明朝体は CJK パッチの担当で、`serif-monospace` は置き換えません。

SIL OFL 1.1 の原文を [NotoSerifLatin-OFL.txt](licenses/NotoSerifLatin-OFL.txt)、[GoogleSansCode-OFL.txt](licenses/GoogleSansCode-OFL.txt) に保存し、Google Sans Code の[商標通知](licenses/GoogleSansCode-TRADEMARKS.md)とともに ZIP に同梱します。ライセンスも公式の Git blob と照合します。

Serif / Mono は2026-09-18に実機で導入・個別復元・再適用・4種類併用の起動を検証しました。ネイティブ描画30設定の参照画像一致、Google Sans Code のASCII等幅性、サンプルのロケール別フォールバックも確認しています。[検証記録](docs/serif-mono-device-validation.md)を参照してください。日本語ロケールでは一部の記号・ギリシャ文字などにCJKフォントが選ばれ、元フォントとは字形・幅が異なる場合があります。System 空き容量は各パッチ単独で約10 MiB以上を推奨します。併用時は各パッチの必要量を合計してください。

## 独立適用の仕組みと検証

XML 全体の導入時バックアップを戻す方式は、後から入れた別パッチまで巻き戻すため採用していません。各 ZIP は担当部分の元 ROM / 置換後ハッシュと復元用断片を持ち、現在の XML に担当部分だけを合成します。共通構造のハッシュ、ファイルのハッシュ、機種・ROM fingerprint、ステージング後のハッシュを検証してから切り替えます。

担当部分は欧文2箇所、CJK 4箇所（香港を繁体字側に含む）、serif 1箇所、mono 1箇所です。他の担当部分はそのまま保持するため、全パッチの組み合わせや他のフォントのバージョンを列挙する必要がありません。担当外のファミリー、エイリアス、コメント、順序は共通構造として固定します。将来の拡張契約・失敗時の扱いは [docs/patch-format.md](docs/patch-format.md) を参照してください。

ホスト側では実際に同梱する recovery 用 Python を使い、serif/mono を含む実際の4パッチの全24導入順序と復元、再適用、競合・改変の拒否をテストします。TTF の軸・36通りの字形差・参照ファイル・ZIP 内容も検証します。これらは TWRP や Android の実機描画の検証ではありません。

実機の目視確認には [font-test.html](font-test.html) と [latin-font-test.html](latin-font-test.html) を利用できます。外部フォントは読み込みませんが、ブラウザ独自のフォント指定に影響されるため、設定画面などのネイティブ UI も確認してください。

## ビルド

`main` への push 時には、[ci.yml](.github/workflows/ci.yml) が静的チェック、入力ファイルの取得・検証、ビルド、テストを自動実行します。リリース時にも同じ静的チェックを実行します。

mise と Python 3.14 が使用できる環境で実行します。依存関係は uv で管理します。
初回は約590 MBのダウンロードと、少なくとも約4 GBの追加空き容量が必要です。

```powershell
mise install
mise exec -- uv sync --locked --cache-dir .uv-cache
mise run check
mise run fetch-assets
mise run build
mise run test
```

`mise run check` は `scripts/`・`recovery/`・`tests/` を対象に Ruff による lint と ty による型チェックを実行します。Ruff のルールは 0.16.6 のデフォルトを基準に、`pyproject.toml` の `select` に個別コードで明示しています。Ruff 更新時もデフォルトの変更には追従せず、ルール一覧は明示的に見直します。個別には `mise run lint` / `mise run typecheck` を使えます。型チェックに必要な依存関係は `uv sync --locked` で自動同期するため、ROM やフォントのダウンロードは不要です。
Ruff と ty は mise.toml でバージョンを固定しています。更新時は `mise use ruff@latest ty@latest --pin` を実行し、`mise run check` と `mise run test` で検証してください。

`fetch-assets` は対象 ROM、Noto Sans CJK / Serif CJK の可変 TTC、Google Sans Flex、Noto Serif VF、Google Sans Code VF、ARMv7 Python / musl を取得し、固定ハッシュを検証します。
一致する既存ファイルは再利用し、異なるファイルがある場合は上書きせず中止します。

出力先は `dist/` です。

| ファイル | 用途 |
| --- | --- |
| `cronos-cjk-fonts-install.zip` | 可変フォントの導入と旧フォントの削除 |
| `cronos-cjk-fonts-restore.zip` | CJK だけを元 ROM へ復元 |
| `cronos-latin-fonts-install.zip` | 欧文2ファミリーだけを導入 |
| `cronos-latin-fonts-restore.zip` | 欧文2ファミリーだけを元 ROM へ復元 |
| `cronos-serif-fonts-install.zip` / `cronos-serif-fonts-restore.zip` | serif だけを導入 / 元 ROM へ復元 |
| `cronos-mono-fonts-install.zip` / `cronos-mono-fonts-restore.zip` | monospace だけを導入 / 元 ROM へ復元 |
| `serif-verification.json` / `mono-verification.json` | 出典・軸・字形・元フォントとの収録文字差分 |
| `SHA256SUMS.txt` | ZIP の SHA-256 |
| `cjk-verification.json` | 入力ハッシュ・ウェイト範囲・字形の検証結果 |
| `latin-verification.json` | 公開フォントの出典・軸・字形・Roboto との差分 |

入力・`build/`・`dist/`・仮想環境は Git 管理対象外です。
展開済みの `build/system.img` は再利用されます。手動で変更した場合は削除して再ビルドしてください。

## リリース（メンテナー向け）

[release.yml](.github/workflows/release.yml) を main ブランチでバージョン番号を入力して手動実行すると、実行時点のコミットにタグを作成し、ビルド・テスト・ビルド証明の作成を経て、上記13ファイルをリリースに公開します。
初回はワークフローをデフォルトブランチへマージし、Settings → General → Releases の **Enable release immutability** を有効にしてください。

`0.1.0` を公開するバージョンに置き換えて実行します。入力は `0.1.0` または `v0.1.0` の形式で、作成されるタグは `v0.1.0` です。タグの事前作成・push は不要です。

公開済みリリース（prerelease を含み、ドラフトを除く）のうち、この形式に一致する最大バージョンから major・minor・patch のいずれかを1だけ上げたバージョンを指定してください。major 更新時は minor・patch を、minor 更新時は patch を0に戻します。たとえば最新が `v1.2.3` なら `2.0.0`・`1.3.0`・`1.2.4` のみ指定できます。
該当する公開済みリリースがない初回は `0.0.0` を基準とし、`0.0.1`・`0.1.0`・`1.0.0` を許可します。タグ作成前と公開直前に検証し、飛び越し・同一バージョン・ダウングレードは拒否します。

```sh
gh workflow run release.yml --ref main -f version=0.1.0
```

本文や prerelease 設定を指定する場合は、同じタグのドラフトを先に作成してください。
GitHub の Actions 画面から実行する場合は、**Run workflow** でブランチに `main` を選び、`version` を入力してください。main 以外では実行できません。
ドラフト作成後に失敗した場合はドラフトのまま残り、同名アセットは再実行時に置換されます。既存タグが実行対象と異なるコミットを指す場合は停止するため、main が進んだ後の再試行は元の実行の **Re-run all jobs** を使用してください。公開済みリリースへの再実行はできません。
実行中はタグやドラフトを編集・公開せず、アセットを手動追加しないでください。

ダウンロードした ZIP のビルド証明は次のコマンドで検証できます（`OWNER/REPO` はリポジトリ名に置換）。
この証明は TWRP の ZIP 署名とは別です。

```sh
gh attestation verify cronos-cjk-fonts-install.zip --repo OWNER/REPO
gh attestation verify cronos-cjk-fonts-restore.zip --repo OWNER/REPO
```
