# 共通 ZIP の最小実機検証（2026-09-18）

Echo Show 5 (2021 / cronos)、TWRP `3.7.0_9-0` で、共通 Mono install ZIP を1回再適用し、Android の正常起動を確認しました。今回変更した機種・ROM 判定と共通 ZIP の実行経路を対象にした検証です。

対象 ROM の System fingerprint は `google/lineage_cronos/cronos:11/RQ3A.211001.001/r0rt1z209050214:userdebug/test-keys` です。ADB serial は `G091P308301603TS` です。

## 対象 ZIP と手順

```text
d55705bef5162f7795e992ec9acd4d5187f2607c802c5a95458ea8f8cdf12d12  echo-show-mono-fonts-install.zip
```

初期状態は CJK＋欧文＋Serif＋Mono の適用済み状態でした。PC と転送後の端末で ZIP の SHA-256 を照合し、System をアンマウントしてから TWRP CLI の `twrp install` で適用しました。新しい System バックアップは、ユーザーの指示に従って省略しました。

TWRP は `Install Google Sans Code 300-800 normal/italic (Echo Show: checkers / cronos / crown)` を表示し、`script succeeded` で完了しました。共通化した機種・ROM 判定を通過し、同梱 Python の実行とファイル配置が成功しています。

## 確認結果

- TWRP 上で、適用後の `fonts.xml` が適用前とバイト単位で一致。
- Mono の通常体・イタリック体の SHA-256 が配布 ZIP の検証 JSON と一致。
- XML と Mono 2フォントの所有者 `0:0`、モード `0644`、SELinux label `u:object_r:system_file:s0` を確認。
- Android 再起動後、`sys.boot_completed=1`、system_server と SystemUI のプロセスを確認。
- 起動後も XML が適用前と完全一致し、`/system/fonts/*` の262パスのハッシュとファイル名がすべて適用前と一致。
- 起動後の crash buffer は空。保存した logcat のフォント読み込み・XML エラー候補の検索にも該当なし。

最終状態は初期状態と同じ CJK＋欧文＋Serif＋Mono です。XML の SHA-256 は `b72efb6e4b62c1e1c316119951aceb593933abb68e8228bd4fab0d3df2fa94e3` です。

## 証跡と確認範囲

証跡は `build/device-validation/20260918-common-smoke/`（Git 管理対象外）に保存しました。Flash 出力、recovery.log、適用前後の XML・プロパティ・フォントハッシュ・属性、起動後の logcat、結果の `summary.json` を含みます。検証時のソースと SHA-256、HEAD、未コミットの差分も保存しています。ZIP 内の `device_tested: false` はビルド時の値を維持し、上記ハッシュの実機結果を本記録で管理します。

実機で Flash したのは **cronos 上の共通 Mono install ZIP 1個のみ**です。checkers / crown、共通版の他の install ZIP・restore ZIP、未対応 ROM の実機での拒否、描画の再検証は実施していません。機種と fingerprint の組み合わせによる拒否はホストテストの確認範囲です。
