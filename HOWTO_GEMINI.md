LineageOS 18.1（Android 11）でW1〜W9の日本語フォントを導入するための、TWRP用フラッシャブルZIPを作成する手順を解説します。

Android 11のフォントレンダリングエンジンはすでにバリアブルフォント（可変ウェイト）に対応しているため、フォントファイルと設定ファイル（`fonts.xml`）を差し替えることでAndroid 15と同等の多ウェイト化が可能です。

1. **必要なファイルの準備:** PC上での作業.
1. **フォントファイル:** Google Fontsなどから「Noto Sans CJK JP」のバリアブルフォント版（例: `NotoSansCJK-VF.ttc` または `NotoSansCJKjp-VF.ttf`）をダウンロードします。
2. **fonts.xml:** 端末とPCを繋ぎ、現在の設定ファイルを抽出します。
`adb pull /system/etc/fonts.xml`
3. **update-binary:** 任意のTWRP用ZIP（MagiskのZIPやカスタムROMのZIPなど）から、`META-INF/com/google/android/update-binary` をコピーして用意しておきます。


2. **fonts.xml の編集:**
抽出した `fonts.xml` をテキストエディタで開き、`<family lang="ja">` のブロックを以下のようにバリアブルフォントのウェイト指定（W1〜W9）に書き換えます。

```xml
<family lang="ja">
    <font weight="100" style="normal" index="0" postScriptName="NotoSansCJKjp-Thin">NotoSansCJK-VF.ttc<axis tag="wght" stylevalue="100"/></font>
    <font weight="200" style="normal" index="0" postScriptName="NotoSansCJKjp-Thin">NotoSansCJK-VF.ttc<axis tag="wght" stylevalue="200"/></font>
    <font weight="300" style="normal" index="0" postScriptName="NotoSansCJKjp-Thin">NotoSansCJK-VF.ttc<axis tag="wght" stylevalue="300"/></font>
    <font weight="400" style="normal" index="0" postScriptName="NotoSansCJKjp-Thin">NotoSansCJK-VF.ttc<axis tag="wght" stylevalue="400"/></font>
    <font weight="500" style="normal" index="0" postScriptName="NotoSansCJKjp-Thin">NotoSansCJK-VF.ttc<axis tag="wght" stylevalue="500"/></font>
    <font weight="600" style="normal" index="0" postScriptName="NotoSansCJKjp-Thin">NotoSansCJK-VF.ttc<axis tag="wght" stylevalue="600"/></font>
    <font weight="700" style="normal" index="0" postScriptName="NotoSansCJKjp-Thin">NotoSansCJK-VF.ttc<axis tag="wght" stylevalue="700"/></font>
    <font weight="800" style="normal" index="0" postScriptName="NotoSansCJKjp-Thin">NotoSansCJK-VF.ttc<axis tag="wght" stylevalue="800"/></font>
    <font weight="900" style="normal" index="0" postScriptName="NotoSansCJKjp-Thin">NotoSansCJK-VF.ttc<axis tag="wght" stylevalue="900"/></font>
</family>

```


3. **ZIPのディレクトリ構造を作成:**
PC上で新しいフォルダを作成し、以下の構造になるようにファイル群を配置します。

```text
Patch_Folder/
├── META-INF/
│   └── com/
│       └── google/
│           ├── android/
│           │   ├── update-binary  (Step1で用意したバイナリ)
│           │   └── updater-script (Step4で作成)
├── system/
│   ├── etc/
│   │   └── fonts.xml              (Step2で編集したXML)
│   └── fonts/
│       └── NotoSansCJK-VF.ttc     (ダウンロードしたフォント)

```


4. **updater-script の作成:**
`updater-script` という名前のテキストファイルを作成し、以下のインストール命令を記述します。

```text
ui_print("Installing Variable Japanese Fonts...");
run_program("/sbin/busybox", "mount", "/system");
run_program("/sbin/busybox", "mount", "/system_root");

package_extract_dir("system", "/system");

set_perm(0, 0, 0644, "/system/etc/fonts.xml");
set_perm(0, 0, 0644, "/system/fonts/NotoSansCJK-VF.ttc");

unmount("/system");
unmount("/system_root");
ui_print("Done!");

```


5. **ZIP圧縮とインストール:**
作成したフォルダの中身（`META-INF` と `system`）を選択し、通常のZIP形式（無圧縮または標準圧縮）でアーカイブします。
作成したZIPファイルを端末に転送し、TWRPの「Install」からフラッシュして端末を再起動します。


**確認方法:**
端末再起動後、ブラウザを開いてCSSで `font-weight: 100` から `900` まで指定されているテストページ（または自作のHTMLファイル）を表示し、日本語の太さが段階的に変化しているか確認してください。