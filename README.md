# 🚗 AV車・ガソリン車混合交通シミュレーション

このシステムは、自動運転車（AV車）とガソリン車の混合交通シミュレーションを実行し、ガソリン車のCO2排出量を測定するためのツールです。

## 🎯 特徴

- **🔄 AV普及率制御**: 0-100%の範囲でAV車の普及率を設定可能
- **🎨 車両色分け**: 赤色（ガソリン車）、緑色（AV車）で視覚的に識別
- **📊 CO2排出量測定**: ガソリン車のリアルタイムCO2排出量測定
- **📈 詳細レポート**: CSV形式での詳細ログとサマリーレポート
- **🚦 停止回数カウント**: 指定エリアでの車両停止回数測定

---

## 🚀 基本的な使い方

### 1️⃣ 混合交通の生成と可視化

```bash
# AV普及率50%、車両数100台で生成
python generate_mixed_traffic.py --vehicles 100 --av-penetration 50

# SUMO-GUIで可視化確認
sumo-gui -c mixed_traffic.sumocfg
```

### 2️⃣ CO2排出量の測定

```bash
# CO2排出量をリアルタイム測定
python co2_emission_monitor.py
```

### 3️⃣ 停止回数の測定

```bash
# 停止回数をリアルタイム測定
python stop_counter.py
```

---

## 🎛️ パラメータ変更方法

### 📊 車両数の変更

```bash
# 車両数を200台に変更
python generate_mixed_traffic.py --vehicles 200 --av-penetration 50

# 車両数を50台に変更
python generate_mixed_traffic.py --vehicles 50 --av-penetration 50
```

### 🔄 AV普及率の変更

```bash
# ガソリン車のみ（AV普及率0%）
python generate_mixed_traffic.py --vehicles 100 --av-penetration 0

# AV車25%
python generate_mixed_traffic.py --vehicles 100 --av-penetration 25

# AV車半分（AV普及率50%）
python generate_mixed_traffic.py --vehicles 100 --av-penetration 50

# AV車75%
python generate_mixed_traffic.py --vehicles 100 --av-penetration 75

# AV車のみ（AV普及率100%）
python generate_mixed_traffic.py --vehicles 100 --av-penetration 100
```

### ⏰ シミュレーション時間の変更

```bash
# 10分間（600秒）のシミュレーション
python generate_mixed_traffic.py --vehicles 100 --av-penetration 50 --end-time 600

# 20分間（1200秒）のシミュレーション
python generate_mixed_traffic.py --vehicles 100 --av-penetration 50 --end-time 1200
```

---

## 🎨 車両の色分け

| 車両タイプ | 色 | 特徴 | CO2排出 |
|-----------|---|------|---------|
| **AV車（自動運転車）** | 🟢 **緑色** | 完璧な運転、スムーズな動き | **ゼロ排出** |
| **ガソリン車（一般車両）** | 🔴 **赤色** | 人間らしい運転、若干不規則 | **CO2排出あり** |

### 🔍 SUMO-GUIでの確認方法
- シミュレーション画面で車両の色を確認
- 緑の車 = AV車、赤の車 = ガソリン車
- 車両を右クリック → 「Show Parameter」で詳細確認

---

## 📊 CO2排出量の確認方法

### 💻 リアルタイム表示

```bash
python co2_emission_monitor.py
```

**表示例:**
```
⏰ 時刻:   300s | 🔴 ガソリン車:  45 | 🟢 AV車:  55 | 💨 CO2排出:   142.50g
```

### 📁 結果ファイル

| ファイル名 | 内容 | 場所 |
|-----------|------|------|
| `co2_emission_log.csv` | 時系列詳細データ | 作業ディレクトリ |
| `co2_emission_report.txt` | サマリーレポート | 作業ディレクトリ |

#### 📈 co2_emission_log.csv の内容
```csv
time,gasoline_co2,av_co2,total_gasoline,total_av,gasoline_vehicles,av_vehicles
100.0,2.5,0.0,125.3,0.0,45,55
200.0,2.8,0.0,267.8,0.0,48,52
...
```

#### 📋 co2_emission_report.txt の内容
```
============================================================
CO2排出量測定結果レポート
============================================================
📊 車両タイプ別排出量:
   🔴 ガソリン車総排出量: 1250.45 g
   🟢 AV車総排出量: 0.00 g
   📈 全体総排出量: 1250.45 g

💨 ガソリン車CO2排出率: 142.3 g/km
============================================================
```

---

## 🚦 停止回数の確認方法

### 💻 リアルタイム表示

```bash
python stop_counter.py
```

**表示例:**
```
🕐 時刻   300s | 車両  82 | 停止   45
停止カウント: 車両 vehicle_123 がエッジ 174274266#1 で 1.2秒停止
```

### 📁 結果ファイル

| ファイル名 | 内容 | 場所 |
|-----------|------|------|
| `stop_count_results.txt` | 停止回数サマリー | 作業ディレクトリ |

#### 📋 stop_count_results.txt の内容
```
停止回数カウント結果
==================================================
-174274266#1        :  133 回
174274266#6         :   78 回
-174274266#6        :   65 回
174274266#7         :   53 回
...
合計停止回数: 768 回
```

---

## 🧪 実験パターン例

### 🔬 AV普及率の影響調査

```bash
# 実験1: ガソリン車のみ
python generate_mixed_traffic.py --av-penetration 0
python co2_emission_monitor.py
# → 結果をco2_0percent.csvに保存

# 実験2: AV車50%
python generate_mixed_traffic.py --av-penetration 50  
python co2_emission_monitor.py
# → 結果をco2_50percent.csvに保存

# 実験3: AV車100%
python generate_mixed_traffic.py --av-penetration 100
python co2_emission_monitor.py
# → 結果をco2_100percent.csvに保存
```

### 📈 交通量の影響調査

```bash
# 低密度: 50台
python generate_mixed_traffic.py --vehicles 50 --av-penetration 50

# 中密度: 100台  
python generate_mixed_traffic.py --vehicles 100 --av-penetration 50

# 高密度: 200台
python generate_mixed_traffic.py --vehicles 200 --av-penetration 50
```

---

## 📁 ファイル構成

```
GreenWave/
├── generate_mixed_traffic.py     # 車両生成スクリプト
├── co2_emission_monitor.py       # CO2排出量測定スクリプト  
├── stop_counter.py               # 停止回数測定スクリプト
├── vehicle_types.xml             # 車両タイプ定義
├── mixed_traffic.sumocfg         # SUMO設定ファイル（自動生成）
├── mixed_routes.rou.xml          # ルートファイル（自動生成）
│
├── 3gousen_new.net.xml           # ネットワークファイル
├── 3gousen_colored.poly.xml      # 色付きマップファイル
│
└── 結果ファイル/
    ├── co2_emission_log.csv      # CO2詳細ログ
    ├── co2_emission_report.txt   # CO2サマリーレポート
    └── stop_count_results.txt    # 停止回数結果
```

---

## 🔧 トラブルシューティング

### ❌ よくあるエラーと解決方法

#### 1. ファイルアクセスエラー
```
PermissionError: プロセスはファイルにアクセスできません
```
**解決方法:**
- SUMO-GUIが開いていたら閉じる
- 既存のファイルを削除: `del routes.rou.xml`

#### 2. SUMO_HOME未設定エラー
```
SUMO_HOME環境変数が設定されていません
```
**解決方法:**
```bash
$env:SUMO_HOME = "C:\Program Files (x86)\Eclipse\Sumo"
```

#### 3. 車両が表示されない
**解決方法:**
- ネットワークファイル `3gousen_new.net.xml` の存在確認
- シミュレーション時間を確認（車両生成に時間がかかる場合あり）

---

## 📞 サポート・参考資料

### 🔗 関連ファイル
- **ネットワーク生成**: `netconvert --osm-files 3gousen.osm -o 3gousen_new.net.xml`  
- **色付きマップ**: `polyconvert --net-file 3gousen_new.net.xml --osm-files 3gousen.osm --type-file typemap.xml -o 3gousen_colored.poly.xml`

### 💡 応用例
- **環境負荷分析**: AV普及率とCO2排出量の関係
- **交通効率分析**: AV普及率と停止回数の関係  
- **政策効果分析**: AV導入政策のシミュレーション

### 📝 データ活用
- **Excel分析**: CSVファイルをExcelで開いてグラフ作成
- **Python分析**: pandasでデータ分析・可視化
- **論文作成**: 実験データを研究論文に活用

## 📁 ファイル構成

```
├── generate_mixed_traffic.py     # 車両生成スクリプト
├── co2_emission_monitor.py       # CO2排出量測定スクリプト
├── vehicle_types.xml             # 車両タイプ定義
├── run_simulation.bat            # Windows用実行スクリプト
├── run_simulation.sh             # Linux/Mac用実行スクリプト
└── mixed_traffic.sumocfg         # SUMO設定ファイル（自動生成）
```

## 🚀 クイックスタート

### Windows の場合:
```batch
run_simulation.bat
```

### Linux/Mac の場合:
```bash
chmod +x run_simulation.sh
./run_simulation.sh
```

## 📋 手動実行

### 1. 車両ルート生成
```bash
# AV普及率50%で100台の車両を生成
python generate_mixed_traffic.py --vehicles 100 --av-penetration 50

# その他のオプション
python generate_mixed_traffic.py --help
```

### 2. シミュレーション実行

#### SUMO-GUIでの可視化:
```bash
sumo-gui -c mixed_traffic.sumocfg
```

#### CO2排出量測定付き実行:
```bash
python co2_emission_monitor.py
```

## 🎛️ パラメータ設定

### 車両生成パラメータ

| パラメータ | 説明 | デフォルト | 範囲 |
|-----------|------|-----------|------|
| `--vehicles` | 総車両数 | 100 | 1以上 |
| `--av-penetration` | AV普及率(%) | 50 | 0-100 |
| `--end-time` | シミュレーション時間(秒) | 600 | 1以上 |
| `--network` | ネットワークファイル | 3gousen_new.net.xml | - |

### 車両タイプ特性

| 車両タイプ | 色 | CO2排出 | 運転特性 |
|-----------|---|---------|----------|
| ガソリン車 | 🔴 赤色 | HBEFA3/PC_G_EU4 | 人間的（sigma=0.5） |
| AV車 | 🟢 緑色 | ゼロ排出 | 完璧（sigma=0.0） |

## 📊 出力ファイル

### 1. co2_emission_log.csv
シミュレーション中の詳細ログ（時系列データ）

| 列名 | 説明 |
|------|------|
| time | シミュレーション時刻 |
| gasoline_co2 | ガソリン車瞬間CO2排出量(g/s) |
| av_co2 | AV車瞬間CO2排出量(g/s) |
| total_gasoline | ガソリン車累積CO2排出量(g) |
| total_av | AV車累積CO2排出量(g) |
| gasoline_vehicles | ガソリン車台数 |
| av_vehicles | AV車台数 |

### 2. co2_emission_report.txt
サマリーレポート（総排出量、走行距離、排出率など）

## 🔧 設定のカスタマイズ

### 車両タイプの変更
`vehicle_types.xml`を編集して車両特性を変更:

```xml
<vType id="gasoline_car" 
       accel="2.6"           <!-- 加速度 m/s² -->
       decel="4.5"           <!-- 減速度 m/s² -->
       sigma="0.5"           <!-- 運転の不完全性 (0-1) -->
       maxSpeed="50.0"       <!-- 最高速度 m/s -->
       color="1,0,0"         <!-- 色 (R,G,B) -->
       emissionClass="HBEFA3/PC_G_EU4"/>  <!-- 排出クラス -->
```

### 新しい車両タイプの追加
1. `vehicle_types.xml`に新しい`<vType>`を追加
2. `generate_mixed_traffic.py`の車両割り当てロジックを修正
3. `co2_emission_monitor.py`の集計ロジックを修正

## 📈 実験例

### AV普及率の影響調査
```bash
# AV普及率0%（ガソリン車のみ）
python generate_mixed_traffic.py --av-penetration 0

# AV普及率25%
python generate_mixed_traffic.py --av-penetration 25

# AV普及率50%
python generate_mixed_traffic.py --av-penetration 50

# AV普及率100%（AV車のみ）
python generate_mixed_traffic.py --av-penetration 100
```

各設定でCO2排出量を測定し、比較分析が可能です。

## 🐛 トラブルシューティング

### よくある問題

1. **SUMO_HOME環境変数が設定されていない**
   ```bash
   # Windows
   set SUMO_HOME=C:\Program Files (x86)\Eclipse\Sumo
   
   # Linux/Mac
   export SUMO_HOME=/usr/share/sumo
   ```

2. **networkファイルが見つからない**
   - `3gousen_new.net.xml`が存在することを確認
   - `--network`オプションで正しいファイル名を指定

3. **Python モジュールエラー**
   ```bash
   # 必要な場合はtraci、xmlモジュールをインストール
   pip install traci
   ```

## 📞 サポート

問題が発生した場合：
1. エラーメッセージを確認
2. ファイルの存在を確認
3. SUMO環境変数の設定を確認
4. Python/SUMOのバージョンを確認

## 📝 ライセンス

このプロジェクトはMITライセンスの下で提供されています。