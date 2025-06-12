# 🚗 AV車・ガソリン車混合交通シミュレーション

このシステムは、自動運転車（AV車）とガソリン車の混合交通シミュレーションを実行し、ガソリン車のCO2排出量を測定するためのツールです。

## 🎯 特徴

- **🔄 AV普及率制御**: 0-100%の範囲でAV車の普及率を設定可能
- **🎨 車両色分け**: 赤色（ガソリン車）、緑色（AV車）で視覚的に識別
- **📊 CO2排出量測定**: ガソリン車のリアルタイムCO2排出量測定
- **📈 詳細レポート**: CSV形式での詳細ログとサマリーレポート

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