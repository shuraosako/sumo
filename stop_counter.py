#!/usr/bin/env python3
"""
SUMOシミュレーションで指定したエッジ/レーンでの停止回数をカウントするスクリプト
改善版：より正確な停止判定とエラーハンドリング
"""

import traci
import sys
import os
from collections import defaultdict
import time

# 監視対象のエッジID
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

# 設定パラメータ
STOP_THRESHOLD = 0.1  # m/s - この速度以下を停止とみなす
MIN_STOP_DURATION = 1  # 秒 - この時間以上停止していた場合のみカウント
CHECK_INTERVAL = 1  # 秒 - チェック間隔

class StopCounter:
    def __init__(self):
        # 各エッジの停止回数を記録
        self.stop_counts = defaultdict(int)
        # 各車両の停止状態を記録 {vehicle_id: {'start_time': time, 'edge': edge_id, 'counted': bool}}
        self.vehicle_stop_states = {}
        # 有効なエッジのリスト
        self.valid_edges = []
        
    def check_files_exist(self):
        """必要なファイルの存在確認"""
        required_files = ["simulation.sumocfg", "3gousen_new.net.xml", "routes.rou.xml"]
        missing_files = []
        
        for file_path in required_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
        
        if missing_files:
            print(f"エラー: 以下のファイルが見つかりません: {missing_files}")
            return False
        return True
        
    def initialize_edges(self):
        """ネットワークから対象エッジの存在確認"""
        print("対象エッジの存在確認中...")
        
        all_edges = traci.edge.getIDList()
        
        for edge_id in TARGET_EDGES:
            if edge_id in all_edges:
                self.valid_edges.append(edge_id)
                print(f"✓ エッジ {edge_id} が見つかりました")
            else:
                print(f"✗ エッジ '{edge_id}' が見つかりません")
                
        print(f"\n監視対象: {len(self.valid_edges)}/{len(TARGET_EDGES)} エッジ")
        
        if len(self.valid_edges) == 0:
            print("エラー: 有効なエッジが見つかりません")
            return False
        return True
    
    def check_vehicle_stops(self, current_time):
        """車両の停止状態をチェック"""
        current_vehicles = traci.vehicle.getIDList()
        
        # 既存の停止状態を更新
        vehicles_to_remove = []
        for vehicle_id in self.vehicle_stop_states:
            if vehicle_id not in current_vehicles:
                vehicles_to_remove.append(vehicle_id)
        
        for vehicle_id in vehicles_to_remove:
            del self.vehicle_stop_states[vehicle_id]
        
        # 現在の車両をチェック
        for vehicle_id in current_vehicles:
            try:
                speed = traci.vehicle.getSpeed(vehicle_id)
                edge_id = traci.vehicle.getRoadID(vehicle_id)
                
                # 対象エッジにいるかチェック
                if edge_id in self.valid_edges:
                    # 停止状態の判定
                    if speed <= STOP_THRESHOLD:
                        # 停止している
                        if vehicle_id not in self.vehicle_stop_states:
                            # 新しい停止開始
                            self.vehicle_stop_states[vehicle_id] = {
                                'start_time': current_time,
                                'edge': edge_id,
                                'counted': False
                            }
                        else:
                            # 継続停止 - カウント済みかチェック
                            stop_info = self.vehicle_stop_states[vehicle_id]
                            stop_duration = current_time - stop_info['start_time']
                            
                            if not stop_info['counted'] and stop_duration >= MIN_STOP_DURATION:
                                # 最小停止時間を超えたのでカウント
                                self.stop_counts[edge_id] += 1
                                stop_info['counted'] = True
                                print(f"停止カウント: 車両 {vehicle_id} がエッジ {edge_id} で {stop_duration:.1f}秒停止")
                    else:
                        # 動いている - 停止状態をリセット
                        if vehicle_id in self.vehicle_stop_states:
                            del self.vehicle_stop_states[vehicle_id]
                else:
                    # 対象エッジ外 - 停止状態をリセット
                    if vehicle_id in self.vehicle_stop_states:
                        del self.vehicle_stop_states[vehicle_id]
                        
            except traci.TraCIException:
                # 車両が消えた場合
                if vehicle_id in self.vehicle_stop_states:
                    del self.vehicle_stop_states[vehicle_id]
    
    def check_simulation_config(self):
        """シミュレーション設定を確認・表示"""
        try:
            # 設定ファイルから終了時間を読み取り
            import xml.etree.ElementTree as ET
            tree = ET.parse("simulation.sumocfg")
            root = tree.getroot()
            
            end_time = None
            for time_elem in root.findall(".//time"):
                end_elem = time_elem.find("end")
                if end_elem is not None:
                    end_time = float(end_elem.get("value"))
                    break
            
            if end_time:
                print(f"📋 設定終了時間: {end_time} 秒 ({end_time/60:.1f} 分)")
                return end_time
            else:
                print("⚠️  設定ファイルから終了時間を読み取れませんでした")
                return None
        except Exception as e:
            print(f"⚠️  設定ファイル読み取りエラー: {e}")
            return None

    def print_results(self):
        """結果を表示・保存"""
        print("\n" + "="*60)
        print("停止回数カウント結果")
        print("="*60)
        print(f"停止判定条件: 速度 ≤ {STOP_THRESHOLD} m/s, 継続時間 ≥ {MIN_STOP_DURATION} 秒")
        print("-"*60)
        
        total_stops = 0
        results_with_stops = []
        
        for edge_id in self.valid_edges:
            count = self.stop_counts[edge_id]
            total_stops += count
            if count > 0:
                results_with_stops.append((edge_id, count))
                print(f"{edge_id:20s}: {count:4d} 回")
        
        if not results_with_stops:
            print("停止は検出されませんでした")
        
        print("-"*60)
        print(f"合計停止回数: {total_stops} 回")
        print(f"監視エッジ数: {len(self.valid_edges)} 個")
        print("="*60)
        
        # 結果をファイルに保存
        with open("stop_count_results.txt", "w", encoding="utf-8") as f:
            f.write("SUMOシミュレーション 停止回数カウント結果\n")
            f.write("="*50 + "\n")
            f.write(f"停止判定条件: 速度 ≤ {STOP_THRESHOLD} m/s, 継続時間 ≥ {MIN_STOP_DURATION} 秒\n")
            f.write("-"*50 + "\n")
            
            for edge_id, count in results_with_stops:
                f.write(f"{edge_id}: {count} 回\n")
            
            f.write(f"\n合計停止回数: {total_stops} 回\n")
            f.write(f"監視エッジ数: {len(self.valid_edges)} 個\n")
        
        print("結果を 'stop_count_results.txt' に保存しました")

def main():
    counter = StopCounter()
    
    # ファイル存在確認
    if not counter.check_files_exist():
        return
    
    # SUMOコマンド設定
    sumo_cmd = ["sumo", "-c", "simulation.sumocfg", "--no-warnings", "--time-to-teleport", "-1"]
    
    print("SUMOシミュレーションを開始します...")
    
    try:
        traci.start(sumo_cmd)
        
        # エッジの存在確認
        if not counter.initialize_edges():
            return
        
        # 設定確認
        end_time = counter.check_simulation_config()
        
        print(f"\nシミュレーション監視開始...")
        print(f"停止判定: 速度 ≤ {STOP_THRESHOLD} m/s, 継続時間 ≥ {MIN_STOP_DURATION} 秒")
        
        step = 0
        last_check_time = 0
        start_real_time = time.time()
        
        # シミュレーションループ
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            step += 1
            current_time = traci.simulation.getTime()
            
            # 強制終了条件（設定時間に達したら終了）
            if end_time and current_time >= end_time:
                print(f"\n⏰ 設定時間 {end_time}秒に達したため、シミュレーションを終了します")
                break
            
            # 定期的に停止チェック
            if current_time - last_check_time >= CHECK_INTERVAL:
                counter.check_vehicle_stops(current_time)
                last_check_time = current_time
            
            # 進捗表示（100ステップごと）
            if step % 100 == 0:
                vehicle_count = traci.vehicle.getIDCount()
                total_stops = sum(counter.stop_counts.values())
                
                # 進捗計算
                if end_time:
                    progress = (current_time / end_time) * 100
                    remaining_sim_time = end_time - current_time
                    
                    # 実行時間から推定残り時間計算
                    elapsed_real_time = time.time() - start_real_time
                    if current_time > 0:
                        estimated_total_real_time = elapsed_real_time * (end_time / current_time)
                        remaining_real_time = estimated_total_real_time - elapsed_real_time
                        remaining_minutes = remaining_real_time / 60
                        
                        print(f"🕐 時刻 {current_time:6.0f}s ({progress:5.1f}%) | 車両 {vehicle_count:3d} | 停止 {total_stops:4d} | 残り約 {remaining_minutes:.1f}分")
                    else:
                        print(f"🕐 時刻 {current_time:6.0f}s ({progress:5.1f}%) | 車両 {vehicle_count:3d} | 停止 {total_stops:4d}")
                else:
                    print(f"🕐 時刻 {current_time:6.1f}s | 車両 {vehicle_count:3d} | 停止 {total_stops:4d}")
    
    except Exception as e:
        print(f"エラーが発生しました: {e}")
    
    finally:
        # 結果表示と保存
        counter.print_results()
        
        # SUMO終了
        try:
            traci.close()
        except:
            pass
        
        print("シミュレーション完了")

if __name__ == "__main__":
    main()