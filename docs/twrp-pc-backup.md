# TWRP の System バックアップを PC に直接保存する

Echo Show 5 第2世代（cronos）、TWRP `3.7.0_9-0`、Windows / PowerShell で確認した手順です。端末の内部ストレージにバックアップを一旦保存せず、TWRP の ADB バックアップストリームを PC に書き込みます。通常の Android のアプリバックアップとは別の形式です。

## 端末と保存先を確認する

```powershell
adb devices -l
$serial = 'G091P308301603TS'  # 実際の対象端末に合わせる
$destination = 'build/device-validation/' + (Get-Date -Format 'yyyyMMdd-HHmmss')
New-Item -ItemType Directory -Path $destination -Force | Out-Null
adb -s $serial reboot recovery
```

再接続後、`adb devices -l` が対象を `recovery` と表示し、次のコマンドで TWRP のバージョンが取得できることを確認します。

```powershell
adb -s $serial shell getprop ro.twrp.version
```

初回の System 読み取り専用確認画面で止まっている場合は、次を実行します。今回の端末では初回画面が閉じ、バックアップ受付用 FIFO が作成されました。

```powershell
adb -s $serial shell twrp remountrw
adb -s $serial shell ls -l /tmp/twadbfifo
```

`remountrw` は System を書き込み可能にする設定です。フォントパッチを適用する前のバックアップ準備として実行します。このコマンド自体はフォントを書き換えません。

## System を保存・検証する

```powershell
adb -s $serial backup -f "$destination/system-before.ab" --twrp --compress system
```

処理が終了するまで待ちます。ADB の `Now unlock your device and confirm the backup operation...` というメッセージだけでは進行・完了を判定できません。別の PowerShell で保存ファイルの増加とログを確認できます。

```powershell
Get-Item "$destination/system-before.ab" | Select-Object Length,LastWriteTime
adb -s $serial shell tail -n 25 /tmp/recovery.log
adb -s $serial shell tail -n 15 /tmp/adb.log
```

終了後、ログとバックアップの検証結果を保存します。

```powershell
adb -s $serial pull /tmp/recovery.log "$destination/recovery-backup.log"
adb -s $serial pull /tmp/adb.log "$destination/adb-backup.log"
mise exec -- uv run --locked --cache-dir .uv-cache python scripts/verify_adb_backup.py "$destination/system-before.ab"
Get-FileHash "$destination/system-before.ab" -Algorithm SHA256
```

[`verify_adb_backup.py`](../scripts/verify_adb_backup.py) は TWRP v3 ストリームの終端・エントリー数・制御ブロック CRC・ペイロード MD5・gzip CRC と終端を検証し、成功時に `system-before.verification.json` を作ります。System だけを指定した場合は `partition_count: 1` と `system.ext4.win` を確認してください。検証はバックアップからの実際の復元テストとは別です。

`build/` は Git 管理対象外です。バックアップは、検証完了まで削除しない保存先に保管してください。バイナリ本体には PowerShell のテキスト用リダイレクトを使わず、必ず ADB の `-f` で保存します。

## 0バイトで終了した場合

今回、初回画面が開いたままでは ADB が終了コード0で戻ってもバックアップは0バイトでした。`/tmp/adb.log` には次のエラーがありました。

```text
Unable to open TW_ADB_FIFO No such file or directory
Adb backup/restore failed
```

`twrp remountrw` 実行後、`/tmp/twadbfifo` の存在を確認してから再実行すると成功しました。失敗時のログは再試行前に別名で保存します。0バイトのファイルや、検証に失敗したファイルを復元用バックアップとして扱わないでください。

## 復元方法

対象端末を TWRP に起動し、上記と同じ初回画面の処理を行います。PC 側でバックアップを再検証し、対象端末のシリアルを確認してから実行します。

```powershell
adb -s $serial restore "$destination/system-before.ab"
```

これはバックアップに含まれるパーティションを取得時点へ戻す操作です。この手順の `system` のみのバックアップなら System が対象です。現在のフォントだけを戻す通常の操作には、対応する restore ZIP を使います。

復元時も `/tmp/recovery.log` と `/tmp/adb.log` を保存し、完了表示だけでなく、fonts.xml・フォントのハッシュ、属性、Android の起動を確認してください。今回取得したバックアップからの復元実行は未実施です。

## 今回の取得記録

- 実施日: 2026-09-18（JST）
- 端末: `G091P308301603TS` / cronos、TWRP `3.7.0_9-0`
- 保存先: `build/device-validation/20260918-020133/system-before.ab`
- サイズ: 548,407,296 bytes
- SHA-256: `e653498603c3c17f1535008974a76053953d2f4edae93c1b646d61cbe24f110a`
- 取得状態: CJK のみ適用した状態（C）。元 ROM 状態（S）のバックアップではありません。
- System 1エントリーの整合性検証に成功。

前回のセッションでは `--twrp --compress system boot recovery data` で4パーティションを PC に直接保存しています。複数を指定したバックアップの復元は、それらすべてを取得時点に戻します。TWRP の Data バックアップは通常 `/data/media` の内部共有ストレージを含まないため、全ストレージの複製ではありません。
