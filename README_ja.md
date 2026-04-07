# chikuchiku-denden

工場や事業所向けの電力料金分析と蓄電池スケジュール評価を題材に、`電力 × ソフトウェア設計 × 業務課題解決` を形にしたポートフォリオプロジェクトです。

![Battery scheduling UI](assets/ui_step5.png)

## なぜこのプロジェクトを作ったか

産業向けの電力分析では、難しいのは数式だけではありません。

実務で本当に難しいのは、電力会社帳票風のCSV、料金表、休日区分、運用条件といった扱いにくい情報を、試算と説明に使えるワークフローへ落とし込むことです。

`chikuchiku-denden` は、そのギャップを埋めるために作成しました。

このプロジェクトが扱う業務課題は次のようなものです。

- 電気料金プランを比較したい
- 30分電力量データから年間コストを試算したい
- 蓄電池の充放電スケジュールが最大需要電力と年間料金に与える影響を見たい
- 人が読みやすいCSVを、シミュレーション入力へ変換したい
- Python 環境のない利用者にも exe で渡したい

単なる最適化サンプルではなく、現場で起こる「電力 × IT × 業務改善」の問題を、入力整形、計算ロジック、UI、配布まで含めて扱うことを意図しています。

## 概要

`chikuchiku-denden` は、工場や事業所の電力利用を対象に、料金プラン比較と蓄電池導入効果の概算評価を行う Python / Streamlit アプリケーションです。

次のような実務フローを一連で扱えます。

- 2つの料金プランを比較する
- 実務レイアウトのCSVから電力使用量を取り込む
- 目標受電電力から蓄電池容量の目安を検討する
- 月別・日種別ごとの充放電スケジュールを編集する
- 年間シミュレーションを行い、導入前後の料金差を確認する
- プロジェクトを ZIP で保存、再読込する

## どんな課題を解くアプリか

このアプリは、たとえば次のような場面を想定しています。

- 料金プラン見直しの効果を比較したい
- 蓄電池運用による電気料金削減余地を概算したい
- 導入前後で年額、月額、最大需要電力がどう変わるかを見たい
- 現場由来の扱いにくいデータを、再利用できる入力形式へ揃えたい
- Python を使わない関係者にも配布できる形にしたい

エネルギー分野の実務課題を、ソフトウェアとしてどう整理し、どう見せるかを重視したプロジェクトです。

## 主な機能

- 30分電力量データを使った2つの料金プラン比較
- 年間電力量、最大需要電力、導入前年間料金の算出
- 目標受電電力に基づく蓄電池容量の目安計算
- 月別、稼働日／休日別の充放電スケジュール編集
- 年間の充放電シミュレーション
- 導入前後の需要電力と料金差の可視化
- 電力会社帳票風を含む実務レイアウトCSVの読込
- プロジェクトZIPの出力と再読込
- Windows exe 配布対応

## アーキテクチャ

コードベースは、UI、入出力、ドメインロジックを分ける形で整理しています。

- `app.py`
  Streamlit のエントリーポイント
- `ui_components.py`
  UI描画と画面遷移、入力処理
- `io_utils.py`
  CSV / ZIP 入出力と形式変換
- `models.py`
  データ構造とバリデーション
- `calculators.py`
  UI から呼び出す計算ファサード
- `engine/`
  計算とシミュレーションの中核ロジック

詳細は [docs/architecture.md](docs/architecture.md) を参照してください。

## リポジトリ構成

```text
app.py
ui_components.py
io_utils.py
models.py
calculators.py
engine/
defaults/
sample_data/
docs/
assets/
build_exe.ps1
chikuchiku_denden.spec
```

## サンプル入力と出力

公開用サンプルは `sample_data/` に含めています。

- `sample_energy_usage.csv`
- `sample_tariff.csv`
- `sample_battery_schedule.csv`

このアプリでは、たとえば次のような出力を確認できます。

- 年額料金比較
- 月次削減額
- 導入前後の需要電力グラフ
- 充放電スケジュール表

## スクリーンショット

### STEP5 UI
![Battery scheduling UI](assets/ui_step5.png)

### 導入前後比較
![Before-and-after demand graph](assets/graph_before_after.png)

### 月次結果
![Monthly result summary](assets/monthly_result.png)

## 実行方法

### ソースコードから起動

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

### Windows exe をビルド

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

## 公開データ方針

このリポジトリには、公開可能なサンプルデータとデモ用初期データのみを含めています。

- `defaults/` はアプリ初期表示用のサンプル
- `sample_data/` はGitHub閲覧者向けの説明用サンプル

顧客情報、契約番号、請求情報、実運用データは含めていません。

## 制約事項

- 本プロジェクトはポートフォリオ兼デモアプリであり、商用製品認証を受けたものではありません
- 計算結果は入力データ品質と一定の簡略化前提に依存します
- 料金制度や蓄電池挙動は評価用モデルとして表現しています
- 実務利用時は、契約条件や運用条件に合わせた妥当性確認が必要です

## 今後の改善案

- CSV変換と年間シミュレーションの自動テスト強化
- 蓄電池容量や運転パターンの複数シナリオ比較
- レポート出力の強化
- 入力不正時のバリデーションメッセージ改善
- `docs/` 内の設計資料と業務フロー説明の拡充

## 免責事項

このプロジェクトは、ポートフォリオおよび技術デモ用途のアプリケーションです。

- 財務、契約、法務判断を保証するものではありません
- シミュレーション結果は簡略化した前提に基づく概算です
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


