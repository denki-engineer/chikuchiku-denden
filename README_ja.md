# chikuchiku-denden

電力料金比較、30分電力量分析、蓄電池スケジュール評価を行う Python / Streamlit アプリケーションです。

![UI](assets/ui_step5.png)

## 概要

`chikuchiku-denden` は、工場や事業所の電力利用を対象に、
料金プラン比較と蓄電池導入効果の概算評価を行うための実務志向アプリです。

このアプリでは、次のような業務を一連の流れで扱えます。

- 電気料金プランの比較
- 30分電力量データの読込と検証
- 目標受電電力に基づく蓄電池容量の検討
- 月別・日種別ごとの充放電スケジュール設定
- 導入前後の需要電力・電気料金の比較
- プロジェクト単位での保存と再利用

## 背景 / なぜこのプロジェクトを作ったか

電力コスト削減の検討は、単なる数式処理だけでは完結しません。
実務では、扱いにくいCSV、料金表、運用条件、説明用の集計結果をまとめて扱う必要があります。

特に現場では、次のような課題が起こりがちです。

- 電力会社や現場由来のCSVが、そのままでは分析に使いにくい
- 料金表や休日区分の扱いが複雑で、試算作業が属人化しやすい
- 蓄電池導入効果を月次・年次で説明できる形に整理する必要がある
- Python が使えない利用者にも渡せる形が求められる

このプロジェクトは、そうした「電力 × IT × 業務課題解決」の間をつなぐために作成しました。

## 主な機能

- 2つの料金プランの比較
- 年間30分電力量データの読込と検証
- 年間電力量、最大需要電力、導入前料金の算出
- STEP3 による目標受電電力ベースの蓄電池容量検討
- STEP5 による月別スケジュール編集と年間シミュレーション
- 導入前後の需要電力グラフ表示
- 月次・年次の料金比較
- プロジェクトZIPの入出力
- Windows exe 配布対応
- 実務レイアウトのCSV読込対応
  - 横持ちの電気料金CSV
  - 電力会社帳票風の月報CSV

## 構成

```text
app.py                 Streamlit エントリーポイント
ui_components.py       UI描画と画面操作
models.py              データモデルとバリデーション
io_utils.py            CSV / ZIP 入出力と形式変換
calculators.py         UIから使う計算ファサード
engine/                ドメインロジック本体
defaults/              初期表示用の公開サンプルデータ
assets/                README用画像
sample_data/           GitHub公開用サンプルCSV
docs/                  設計説明や補助資料
build_exe.ps1          Windows exe ビルドスクリプト
chikuchiku_denden.spec PyInstaller 設定
```

## 画面イメージ

### STEP5 UI
![UI](assets/ui_step5.png)

### 導入前後比較
![Graph](assets/graph_before_after.png)

### 月次結果
![Monthly](assets/monthly_result.png)

## 実行方法

### ソースコードから起動

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

### exe をビルド

```powershell
pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

配布用フォルダは次に出力されます。

```text
release/chikuchiku_denden
```

実行ファイル:

```text
release/chikuchiku_denden/chikuchiku_denden.exe
```

## 公開データについて

このリポジトリには、公開可能なサンプルデータのみを含めています。

- `defaults/` はアプリ初期表示用のサンプル
- `sample_data/` はGitHub閲覧者向けの説明用サンプル

顧客情報、契約番号、請求情報、実運用データは含めていません。

## 免責事項

このプロジェクトは、ポートフォリオおよび技術デモ用途のアプリケーションです。

- 財務・契約・法務判断を保証するものではありません
- 計算結果は一定の前提条件に基づく概算です
- 実務利用時は、前提条件と入力データの妥当性確認が必要です

## ライセンス

本プロジェクトは MIT License で公開しています。
詳細は [LICENSE](LICENSE) を参照してください。

## 関連資料

- [English README](README.md)
- [設計メモ](docs/architecture.md)
- [サンプルデータ説明](sample_data/README.md)

## 作者

昭 井上
