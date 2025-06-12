#!/usr/bin/env python3
"""
CO2排出量測定スクリプト
ガソリン車のCO2排出量をリアルタイムで測定・記録
"""

import os
import sys
import traci
import time
import csv
from collections import defaultdict
import signal

class CO2EmissionMonitor:
    def __init__(self):
        self.vehicle_types = {}  # 車両ID -> タイプ
        self.co2_emissions = defaultdict(float)  # 車両タイプ別CO2排出量
        self.vehicle_distances = defaultdict(float)  # 車両タイプ別走行距離
        self.total_co2 = 0.0
        self.gasoline_co2 = 0.0
        self.av_co2 = 0.0
        self.step_count = 0
        self.start_time = time.time()
        
        # 結果保存用
        self.emission_log = []
        
    def initialize_vehicles(self):
        """現在の車両の型を記録"""
        vehicle_ids = traci.vehicle.getIDList()
        for vid in vehicle_ids:
            try:
                vtype = traci.vehicle.getTypeID(vid)
                self.vehicle_types[vid] = vtype
            except:
                pass
    
    def update_emissions(self):
        """排出量を更新"""
        current_vehicles = set(traci.vehicle.getIDList())
        
        # 新しい車両を登録
        for vid in current_vehicles:
            if vid not in self.vehicle_types:
                try:
                    vtype = traci.vehicle.getTypeID(vid)
                    self.vehicle_types[vid] = vtype
                except:
                    continue
        
        # 各車両の排出量を取得
        step_gasoline_co2 = 0.0
        step_av_co2 = 0.0
        
        for vid in current_vehicles:
            if vid in self.vehicle_types:
                try:
                    # CO2排出量を取得 (mg/s)
                    co2_emission = traci.vehicle.getCO2Emission(vid)  # mg/s
                    distance = traci.vehicle.getSpeed(vid)  # m/s
                    vtype = self.vehicle_types[vid]
                    
                    # タイプ別に集計
                    self.co2_emissions[vtype] += co2_emission / 1000.0  # mg -> g
                    self.vehicle_distances[vtype] += distance  # m/s -> m (1秒あたり)
                    
                    if vtype == 'gasoline_car':
                        step_gasoline_co2 += co2_emission / 1000.0
                    elif vtype == 'autonomous_car':
                        step_av_co2 += co2_emission / 1000.0
                        
                except:
                    continue
        
        self.gasoline_co2 += step_gasoline_co2
        self.av_co2 += step_av_co2
        self.total_co2 = self.gasoline_co2 + self.av_co2
        
        # ログに記録
        current_time = traci.simulation.getTime()
        self.emission_log.append({
            'time': current_time,
            'gasoline_co2': step_gasoline_co2,
            'av_co2': step_av_co2,
            'total_gasoline': self.gasoline_co2,
            'total_av': self.av_co2,
            'gasoline_vehicles': len([v for v, t in self.vehicle_types.items() 
                                    if t == 'gasoline_car' and v in current_vehicles]),
            'av_vehicles': len([v for v, t in self.vehicle_types.items() 
                              if t == 'autonomous_car' and v in current_vehicles])
        })
    
    def print_status(self):
        """現在の状況を表示"""
        current_time = traci.simulation.getTime()
        current_vehicles = traci.vehicle.getIDList()
        
        gasoline_count = len([v for v, t in self.vehicle_types.items() 
                            if t == 'gasoline_car' and v in current_vehicles])
        av_count = len([v for v, t in self.vehicle_types.items() 
                       if t == 'autonomous_car' and v in current_vehicles])
        
        print(f"\r⏰ 時刻: {current_time:6.0f}s | "
              f"🔴 ガソリン車: {gasoline_count:3d} | "
              f"🟢 AV車: {av_count:3d} | "
              f"💨 CO2排出: {self.gasoline_co2:8.2f}g", end="")
    
    def save_results(self):
        """結果をファイルに保存"""
        # 詳細ログをCSVで保存
        with open('co2_emission_log.csv', 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'time', 'gasoline_co2', 'av_co2', 'total_gasoline', 
                'total_av', 'gasoline_vehicles', 'av_vehicles'
            ])
            writer.writeheader()
            writer.writerows(self.emission_log)
        
        # サマリーレポート
        report = f"""
============================================================
CO2排出量測定結果レポート
============================================================
📊 車両タイプ別排出量:
   🔴 ガソリン車総排出量: {self.gasoline_co2:.2f} g
   🟢 AV車総排出量: {self.av_co2:.2f} g
   📈 全体総排出量: {self.total_co2:.2f} g

📏 車両タイプ別走行距離:
"""
        
        for vtype, distance in self.vehicle_distances.items():
            distance_km = distance / 1000.0
            report += f"   {vtype}: {distance_km:.2f} km\n"
        
        # CO2/km計算
        if self.vehicle_distances.get('gasoline_car', 0) > 0:
            gasoline_km = self.vehicle_distances['gasoline_car'] / 1000.0
            gasoline_co2_per_km = self.gasoline_co2 / gasoline_km if gasoline_km > 0 else 0
            report += f"\n💨 ガソリン車CO2排出率: {gasoline_co2_per_km:.2f} g/km\n"
        
        report += f"""
⏱️  シミュレーション時間: {self.step_count} ステップ
🕐 実行時間: {time.time() - self.start_time:.1f} 秒
============================================================
詳細ログ: co2_emission_log.csv に保存済み
============================================================
"""
        
        print(report)
        
        # レポートをファイルに保存
        with open('co2_emission_report.txt', 'w', encoding='utf-8') as f:
            f.write(report)

def signal_handler(sig, frame):
    """Ctrl+Cでの終了処理"""
    print("\n\n⚠️  シミュレーション中断中...")
    try:
        traci.close()
    except:
        pass
    print("✅ シミュレーション終了")
    sys.exit(0)

def main():
    # SUMO接続
    sumo_cmd = ["sumo", "-c", "mixed_traffic.sumocfg", "--start"]
    
    if len(sys.argv) > 1 and sys.argv[1] == "gui":
        sumo_cmd[0] = "sumo-gui"
    
    print("🚗 CO2排出量測定開始...")
    print("⏹️  Ctrl+C で途中終了可能")
    print("=" * 60)
    
    # シグナルハンドラー設定
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        traci.start(sumo_cmd)
        monitor = CO2EmissionMonitor()
        
        # 初期車両を登録
        monitor.initialize_vehicles()
        
        # シミュレーションループ
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            monitor.step_count += 1
            
            # 排出量更新
            monitor.update_emissions()
            
            # 10ステップごとに表示更新
            if monitor.step_count % 10 == 0:
                monitor.print_status()
        
        print("\n\n🎉 シミュレーション完了!")
        monitor.save_results()
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
    finally:
        try:
            traci.close()
        except:
            pass

if __name__ == "__main__":
    main()