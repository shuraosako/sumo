import traci
import sys
import os
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
import math

# グリーンウェーブ制御対象エッジ
TARGET_EDGES = [
    "174032654#1", "-174032654#1", "174032654#0", "-174032654#0",
    "174032652#4", "-174032652#4", "174032652#2", "-174032652#2",
    "174032652#1", "-174032652#1", "174032652#0", "-174032652#0",
    "174274266#7", "-174274266#7", "174274266#6", "-174274266#6",
    "174274266#5", "-174274266#5", "174274266#4", "-174274266#4",
    "174274266#3", "-174274266#3", "174274266#2", "-174274266#2",
    "174274266#1", "-174274266#1", "67792293#4", "-67792293#4",
    "67792293#3", "-67792293#3", "67792293#1", "-67792293#1",
    "67792292", "-67792293#0", "170841497#10", "-170841497#10",
    "170841497#9", "-170841497#9", "170841497#8", "-170841497#8",
    "170841497#7", "-170841497#7", "170841497#6", "-170841497#6",
    "170841497#5", "-170841497#5", "170841497#4", "-170841497#4",
    "170841497#3", "-170841497#3", "170841497#2", "-170841497#2",
    "170841497#1", "-170841497#1", "170841497#0", "-170841497#0"
]

class GreenWaveController:
    """
    AV車専用グリーンウェーブ速度制御システム
    
    速度決定式：
    v = L/g           if d = 0 and L/g ≤ vj
    v = vj            if 0 < d ≤ T  
    v = L/(g-C)       otherwise
    
    where: d = (L/vj) × 3.6 - g, T = (C/2)^P
    """
    
    def __init__(self, av_penetration_rate=0.5):
        self.av_penetration = av_penetration_rate
        self.target_edges = set(TARGET_EDGES)
        
        # キャッシュ用データ構造
        self.edge_data = {}           # エッジ長、制限速度キャッシュ
        self.traffic_light_data = {}  # 信号データキャッシュ
        self.junction_edges = {}      # エッジ→終端交差点マッピング
        self.controlled_vehicles = set()  # 制御済み車両ID
        
        # 統計データ
        self.speed_controls = []      # 速度制御履歴
        self.control_count = 0
        
        print("🌊 グリーンウェーブ制御システム初期化完了")
        print(f"   AV普及率: {av_penetration_rate:.1%}")
        print(f"   制御対象エッジ数: {len(TARGET_EDGES)}")
    
    def initialize_network_data(self):
        """
        ネットワークデータを初期化（TRACI接続後に実行）
        """
        print("🗺️ ネットワークデータ初期化中...")
        
        # エッジデータの取得
        all_edges = traci.edge.getIDList()
        for edge_id in self.target_edges:
            if edge_id in all_edges:
                try:
                    length = traci.lane.getLength(f"{edge_id}_0")  # 最初のレーン長を取得
                    max_speed = traci.lane.getMaxSpeed(f"{edge_id}_0")  # km/h -> m/s
                    
                    self.edge_data[edge_id] = {
                        'length': length,  # メートル
                        'max_speed': max_speed * 3.6,  # m/s -> km/h に変換
                        'junction_id': None  # 後で設定
                    }
                    
                    # 終端交差点を特定
                    junction_id = self.get_edge_endpoint_junction(edge_id)
                    if junction_id:
                        self.edge_data[edge_id]['junction_id'] = junction_id
                        self.junction_edges[edge_id] = junction_id
                        
                except Exception as e:
                    print(f"⚠️ エッジ {edge_id} データ取得エラー: {e}")
        
        # 信号データの取得
        self.initialize_traffic_light_data()
        
        print(f"✅ エッジデータ初期化完了: {len(self.edge_data)} エッジ")
        print(f"✅ 信号データ初期化完了: {len(self.traffic_light_data)} 信号")
    
    def get_edge_endpoint_junction(self, edge_id):
        """
        エッジの終端交差点IDを取得
        """
        try:
            # エッジの終端ノード（To Node）を取得
            # SUMOでは通常、正方向エッジの場合はToノード、逆方向の場合はFromノード
            if edge_id.startswith('-'):
                # 逆方向エッジの場合
                original_edge = edge_id[1:]  # '-'を除去
                return traci.edge.getFromJunction(original_edge)
            else:
                # 正方向エッジの場合
                return traci.edge.getToJunction(edge_id)
        except:
            return None
    
    def initialize_traffic_light_data(self):
        """
        信号データを初期化
        """
        traffic_lights = traci.trafficlight.getIDList()
        
        for tl_id in traffic_lights:
            try:
                # 信号の制御定義を取得
                logic = traci.trafficlight.getCompleteRedYellowGreenDefinition(tl_id)
                
                if logic:
                    # 最初のロジック（通常はデフォルト）を使用
                    current_logic = logic[0]
                    phases = current_logic.phases
                    
                    # サイクル長を計算（全フェーズの合計時間）
                    cycle_length = sum(phase.duration for phase in phases)
                    
                    # 青フェーズの開始時刻を計算
                    green_start_time = 0
                    for phase in phases:
                        if 'G' in phase.state or 'g' in phase.state:  # 青信号フェーズ
                            break
                        green_start_time += phase.duration
                    
                    self.traffic_light_data[tl_id] = {
                        'cycle_length': cycle_length,
                        'green_start': green_start_time,
                        'phases': phases
                    }
                    
            except Exception as e:
                print(f"⚠️ 信号 {tl_id} データ取得エラー: {e}")
    
    def get_signal_offset(self, current_edge_id, next_junction_id):
        """
        隣接する2つの信号の青開始時刻の差（オフセット）を計算
        """
        # 現在のエッジの終端交差点の信号
        current_junction = self.junction_edges.get(current_edge_id)
        
        if not current_junction or not next_junction_id:
            return 30.0  # デフォルト値（30秒）
        
        # 現在の交差点と次の交差点の信号データを取得
        current_tl_data = None
        next_tl_data = None
        
        # 交差点IDに対応する信号を探す
        for tl_id, data in self.traffic_light_data.items():
            # 簡易的に交差点IDと信号IDの対応を推定
            if current_junction in tl_id or tl_id in current_junction:
                current_tl_data = data
            if next_junction_id in tl_id or tl_id in next_junction_id:
                next_tl_data = data
        
        if current_tl_data and next_tl_data:
            # 青開始時刻の差を計算
            offset = abs(next_tl_data['green_start'] - current_tl_data['green_start'])
            return offset
        
        # データが取得できない場合のデフォルト値
        return 30.0
    
    def calculate_green_wave_speed(self, vehicle_id, edge_id):
        """
        グリーンウェーブ最適速度を計算
        
        Args:
            vehicle_id (str): 車両ID
            edge_id (str): エッジID
            
        Returns:
            float: 最適速度 (km/h)
        """
        if edge_id not in self.edge_data:
            return None
        
        # パラメータ取得
        edge_info = self.edge_data[edge_id]
        L = edge_info['length']  # リンク長（メートル）
        vj = edge_info['max_speed']  # 法定速度（km/h）
        
        # 次の交差点の信号情報を取得
        next_junction = edge_info['junction_id']
        if not next_junction:
            return vj  # 次の交差点が不明な場合は法定速度
        
        # 信号オフセットとサイクル長を取得
        g = self.get_signal_offset(edge_id, next_junction)
        
        # サイクル長は該当する信号から取得
        C = 120.0  # デフォルト値
        for tl_id, data in self.traffic_light_data.items():
            if next_junction in tl_id or tl_id in next_junction:
                C = data['cycle_length']
                break
        
        # 速度決定式のパラメータ計算
        d = (L / vj) * 3.6 - g  # 時間単位調整
        T = (C / 2) ** self.av_penetration
        
        # 速度決定式の適用
        if abs(d) < 0.1 and (L / g) <= vj:  # d ≈ 0 の場合
            optimal_speed = L / g if g > 0 else vj
        elif 0 < d <= T:
            optimal_speed = vj
        else:
            if (g - C) != 0:
                optimal_speed = L / (g - C)
            else:
                optimal_speed = vj
        
        # 速度制限の適用
        optimal_speed = max(10.0, min(optimal_speed, vj))  # 10-vj km/h の範囲
        
        # 制御履歴に記録
        self.speed_controls.append({
            'vehicle_id': vehicle_id,
            'edge_id': edge_id,
            'L': L,
            'g': g,
            'C': C,
            'd': d,
            'T': T,
            'original_speed': vj,
            'optimal_speed': optimal_speed,
            'time': traci.simulation.getTime()
        })
        
        return optimal_speed
    
    def control_av_vehicles(self):
        """
        AV車両の速度制御を実行
        """
        current_vehicles = traci.vehicle.getIDList()
        new_controls = 0
        
        for vehicle_id in current_vehicles:
            try:
                # AV車かどうか確認
                vehicle_type = traci.vehicle.getTypeID(vehicle_id)
                if vehicle_type != 'autonomous_car':
                    continue
                
                # 現在のエッジを取得
                current_edge = traci.vehicle.getRoadID(vehicle_id)
                
                # 制御対象エッジにいるかチェック
                if current_edge in self.target_edges:
                    # 既に制御済みでないかチェック
                    control_key = f"{vehicle_id}_{current_edge}"
                    if control_key not in self.controlled_vehicles:
                        
                        # グリーンウェーブ最適速度を計算
                        optimal_speed = self.calculate_green_wave_speed(vehicle_id, current_edge)
                        
                        if optimal_speed:
                            # 速度を設定（km/h -> m/s変換）
                            traci.vehicle.setMaxSpeed(vehicle_id, optimal_speed / 3.6)
                            
                            # 制御済みマーク
                            self.controlled_vehicles.add(control_key)
                            new_controls += 1
                            self.control_count += 1
                            
                            if new_controls <= 3:  # 最初の3件のみ表示
                                print(f"🌊 AV速度制御: {vehicle_id} @ {current_edge} -> {optimal_speed:.1f} km/h")
                
            except Exception as e:
                continue
        
        return new_controls
    
    def print_status(self):
        """
        制御状況を表示
        """
        current_time = traci.simulation.getTime()
        av_vehicles = len([v for v in traci.vehicle.getIDList() 
                          if traci.vehicle.getTypeID(v) == 'autonomous_car'])
        
        print(f"\r🌊 [{current_time:6.0f}s] AV車: {av_vehicles:3d} | "
              f"制御済: {self.control_count:4d} | "
              f"対象エッジ: {len(self.target_edges)}", end="")
    
    def save_control_log(self):
        """
        制御ログを保存
        """
        log_dir = os.path.join("data", "log")
        os.makedirs(log_dir, exist_ok=True)
        
        # CSV形式で制御履歴を保存
        csv_path = os.path.join(log_dir, 'green_wave_control_log.csv')
        try:
            import csv
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                if self.speed_controls:
                    writer = csv.DictWriter(f, fieldnames=self.speed_controls[0].keys())
                    writer.writeheader()
                    writer.writerows(self.speed_controls)
            print(f"\n📊 グリーンウェーブ制御ログを{csv_path}に保存")
        except Exception as e:
            print(f"\n⚠️ ログ保存エラー: {e}")
        
        # サマリーレポート
        report = f"""
グリーンウェーブ制御結果サマリー
============================================================
🌊 制御統計:
   総制御回数: {self.control_count}
   AV普及率: {self.av_penetration:.1%}
   制御対象エッジ数: {len(self.target_edges)}

📊 速度制御パラメータ統計:
"""
        
        if self.speed_controls:
            speeds = [c['optimal_speed'] for c in self.speed_controls]
            avg_speed = sum(speeds) / len(speeds)
            report += f"   平均最適速度: {avg_speed:.1f} km/h\n"
            report += f"   速度範囲: {min(speeds):.1f} - {max(speeds):.1f} km/h\n"
        
        report += f"""
============================================================
詳細ログ: {csv_path}
============================================================
"""
        
        print(report)
        
        # レポートファイル保存
        report_path = os.path.join(log_dir, 'green_wave_control_report.txt')
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"📄 制御レポートを{report_path}に保存")
        except Exception as e:
            print(f"⚠️ レポート保存エラー: {e}")

def main():
    """
    メイン実行関数
    """
    # 引数チェック
    if len(sys.argv) < 2:
        print("使い方: python green_wave_controller.py <AV普及率(0-100)> [GUI]")
        print("例: python green_wave_controller.py 50 gui")
        sys.exit(1)
    
    try:
        av_penetration = float(sys.argv[1]) / 100.0
        if not 0.0 <= av_penetration <= 1.0:
            raise ValueError("AV普及率は0-100の範囲で入力してください")
    except ValueError as e:
        print(f"❌ AV普及率エラー: {e}")
        sys.exit(1)
    
    # SUMOコマンド設定
    sumo_cmd = ["sumo", "-c", "mixed_traffic.sumocfg", "--start"]
    if len(sys.argv) > 2 and sys.argv[2].lower() == "gui":
        sumo_cmd[0] = "sumo-gui"
    
    print("=" * 60)
    print("🌊 グリーンウェーブ制御システム")
    print("=" * 60)
    print(f"AV普及率: {av_penetration:.1%}")
    print("対象: autonomous_car タイプのAV車両のみ")
    print("制御方式: エッジ進入時の最適速度計算")
    print("⏹️  Ctrl+C で終了")
    print("-" * 60)
    
    try:
        # SUMO開始
        traci.start(sumo_cmd)
        
        # 制御システム初期化
        controller = GreenWaveController(av_penetration)
        controller.initialize_network_data()
        
        print("🚀 グリーンウェーブ制御開始...")
        
        step_count = 0
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            step_count += 1
            
            # AV車両の速度制御
            new_controls = controller.control_av_vehicles()
            
            # 状況表示（10ステップごと）
            if step_count % 10 == 0:
                controller.print_status()
        
        print("\n\n🎉 シミュレーション完了!")
        controller.save_control_log()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ シミュレーション中断")
        if 'controller' in locals():
            controller.save_control_log()
    except Exception as e:
        print(f"\n❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            traci.close()
        except:
            pass

if __name__ == "__main__":
    main()