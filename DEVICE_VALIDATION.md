# 実機検証 2026-09-17

対象: Echo Show 5 第2世代 / cronos、TWRP `3.7.0_9-0`。
ROM fingerprint:
`google/lineage_cronos/cronos:11/RQ3A.211001.001/r0rt1z209050214:userdebug/test-keys`

## PC への直接バックアップ

フラッシュ前に次の ADB コマンドで System・Boot・Recovery・Data を直接 PC に保存しました。

```powershell
adb -s SERIAL backup -f backups/20260917-pre-jp-fonts/twrp.ab --twrp --compress system boot recovery data
uv run --locked --cache-dir .uv-cache python scripts/verify_adb_backup.py backups/20260917-pre-jp-fonts/twrp.ab
```

保存先: `backups/20260917-pre-jp-fonts/twrp.ab`

- サイズ: 711,988,224 bytes
- SHA-256: `8813503657f11271c515937c9836f8f5f052ef3db845999b8ced2cd1de0d575c`
- TWRP は `BACKUP COMPLETED IN 205 SECONDS` / `Backup Complete` を報告。
- TWRP v3 の4エントリーと終端、制御ブロック CRC、全ペイロード MD5、圧縮データの gzip CRC と終端を PC で検証。
- 詳細は同フォルダーの `twrp.verification.json`、`recovery-backup.log`、`adb-backup.log`。
- TWRP の通常の Data バックアップであり、内部共有ストレージ `/data/media` のファイルを含む全ストレージ複製ではありません。
- バックアップとログ・画面画像は `.gitignore` の `backups/` 以下に保存しています。

復元する場合は対象端末を TWRP に起動し、同じ PC で
`adb -s SERIAL restore backups/20260917-pre-jp-fonts/twrp.ab` を実行する形式です。
これは選択した4パーティションをバックアップ時点に戻します。今回、復元の実行テストはしていません。
フォント変更だけを戻す場合は README の復元用 ZIP を使います。

## フラッシュ結果

実機に `/sbin/busybox` はなく `/sbin/toybox` と SHA-256 アプレットがあることを確認し、
検証スクリプトを Toybox 優先・BusyBox フォールバックに変更しました。
ホストテスト4件を再実行し、ZIP を再生成した後、端末への転送ハッシュを照合しました。

使用したインストール ZIP:
`a8af0667baeaef3afa6bf8b35d4aa2ed40733719e49f271ca2587a8b9427f34e`

同時に生成した復元 ZIP:
`52285792e8a79fa8deb55361e5831acf53de7afe53ff49ef39d17b03e02e8047`

`adb -s SERIAL shell twrp install /tmp/cronos-jp-fonts-install.zip` を実行し、
`script succeeded` を確認しました。フラッシュ後、読み取り専用マウントで確認した内容:

| ファイル | SHA-256 |
| --- | --- |
| fonts.xml | `fd042d90c9fa924bbd86843ef6963aa0bbbda7ef811d7642bd94f7e12ce2675a` |
| NotoSansCJKjp-VF.ttf | `240c9b83bf7b386edbae39995ae7e068ed4583f484d92e4a74c34158b5f27b1a` |
| NotoSerifCJKjp-VF.ttf | `c2ff7cffb6ef75193d4406b030eab5aa6503c48004acec6b040327e2fe1e9e51` |

3ファイルとも所有者 root:root、モード0644、SELinux ラベル `u:object_r:system_file:s0`。
再起動後も同じハッシュで、`sys.boot_completed=1`、system_server と System UI の稼働を確認。
クラッシュログは空で、日本語の日時・天気画面が表示されることをスクリーンショットで確認しました。
証跡は `recovery-flash.log`、`after-boot-crash.log`、`after-boot.png` に保存しています。

全ウェイトの描画、ブラウザの serif 選択、全字形、長時間動作、復元実行の確認は含みません。
