import traci
import sys
import os
from collections import defaultdict
import time
from datetime import datetime

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

STOP_THRESHOLD = 0.1  # m/s
MIN_STOP_DURATION = 1  # 秒
CHECK_INTERVAL = 1  # 秒

class FixedStopCounter:
    def __init__(self):
        # 結果保存フォルダの設定
        self.log_dir = os.path.join("data", "log")
        self.ensure_log_directory()
        
        # 開始時に古い結果ファイルをクリア
        self.clear_old_results()
        
        self.stop_counts = defaultdict(int)
        self.vehicle_stop_states = {}
        self.valid_edges = []
        
        # 実行情報の記録
        self.start_time = time.time()
        self.start_datetime = datetime.now()
        self.total_vehicles_seen = set()
        self.max_simultaneous_vehicles = 0
        self.simulation_steps = 0
        
        # 詳細ログ
        self.stop_events = []  # 各停止イベントの記録
        
    def ensure_log_directory(self):
        """ログディレクトリが存在することを確認（なければ作成）"""
        try:
            os.makedirs(self.log_dir, exist_ok=True)
            print(f"📁 ログディレクトリ確認: {self.log_dir}")
        except Exception as e:
            print(f"⚠️ ログディレクトリ作成エラー: {e}")
            self.log_dir = "."  # フォールバック：カレントディレクトリ
    
    def clear_old_results(self):
        """古い結果ファイルをクリア"""
        result_files = [
            "stop_count_results.txt",
            "stop_count_detailed.csv",
            "stop_count_backup.txt"
        ]
        
        for filename in result_files:
            filepath = os.path.join(self.log_dir, filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    print(f"🗑️ 古いファイル削除: {filepath}")
                except Exception as e:
                    print(f"⚠️ ファイル削除失敗: {filepath} - {e}")
        
    def check_files_exist(self):
        """必要なファイルの存在確認"""
        required_files = ["mixed_traffic.sumocfg"]
        missing_files = []
        
        for file_path in required_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
        
        if missing_files:
            print(f"エラー: 以下のファイルが見つかりません: {missing_files}")
            return False
        return True
        
    def initialize_edges(self):
        """エッジの存在確認と初期化"""
        print("対象エッジの存在確認中...")
        
        all_edges = traci.edge.getIDList()
        
        for edge_id in TARGET_EDGES:
            if edge_id in all_edges:
                self.valid_edges.append(edge_id)
        
        print(f"監視対象: {len(self.valid_edges)}/{len(TARGET_EDGES)} エッジ")
        
        if len(self.valid_edges) == 0:
            print("エラー: 有効なエッジが見つかりません")
            return False
        return True
    
    def check_vehicle_stops(self, current_time):
        """車両の停止状態をチェック（修正版）"""
        current_vehicles = set(traci.vehicle.getIDList())
        
        # 統計更新
        self.total_vehicles_seen.update(current_vehicles)
        self.max_simultaneous_vehicles = max(self.max_simultaneous_vehicles, len(current_vehicles))
        
        # 削除された車両の状態をクリア
        vehicles_to_remove = []
        for vehicle_id in self.vehicle_stop_states:
            if vehicle_id not in current_vehicles:
                vehicles_to_remove.append(vehicle_id)
        
        for vehicle_id in vehicles_to_remove:
            del self.vehicle_stop_states[vehicle_id]
        
        # 現在の車両をチェック
        new_stops_this_check = 0
        
        for vehicle_id in current_vehicles:
            try:
                speed = traci.vehicle.getSpeed(vehicle_id)
                edge_id = traci.vehicle.getRoadID(vehicle_id)
                
                # 対象エッジにいるかチェック
                if edge_id in self.valid_edges:
                    
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
                                # 停止をカウント
                                self.stop_counts[edge_id] += 1
                                stop_info['counted'] = True
                                new_stops_this_check += 1
                                
                                # 詳細ログに記録
                                self.stop_events.append({
                                    'time': current_time,
                                    'vehicle_id': vehicle_id,
                                    'edge_id': edge_id,
                                    'duration': stop_duration,
                                    'total_count': sum(self.stop_counts.values())
                                })
                                
                                if new_stops_this_check <= 3:  # 最初の3件のみ表示
                                    print(f"🛑 停止: 車両{vehicle_id} エッジ{edge_id} ({stop_duration:.1f}s) 総計:{sum(self.stop_counts.values())}")
                    else:
                        # 動いている
                        if vehicle_id in self.vehicle_stop_states:
                            del self.vehicle_stop_states[vehicle_id]
                else:
                    # 対象エッジ外
                    if vehicle_id in self.vehicle_stop_states:
                        del self.vehicle_stop_states[vehicle_id]
                        
            except traci.TraCIException:
                if vehicle_id in self.vehicle_stop_states:
                    del self.vehicle_stop_states[vehicle_id]
        
        return new_stops_this_check

    def save_detailed_results(self):
        """詳細結果をCSVファイルに保存"""
        if self.stop_events:
            try:
                csv_path = os.path.join(self.log_dir, 'stop_count_detailed.csv')
                with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                    import csv
                    writer = csv.DictWriter(f, fieldnames=[
                        'time', 'vehicle_id', 'edge_id', 'duration', 'total_count'
                    ])
                    writer.writeheader()
                    writer.writerows(self.stop_events)
                print(f"📊 詳細データを{csv_path}に保存")
            except Exception as e:
                print(f"⚠️ CSV保存エラー: {e}")

    def print_results(self):
        """結果を表示・保存（修正版）"""
        execution_time = time.time() - self.start_time
        end_datetime = datetime.now()
        
        print("\n" + "="*70)
        print("🛑 停止回数カウント結果（修正版）")
        print("="*70)
        
        # 実行情報
        print(f"🕒 実行開始: {self.start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🕐 実行終了: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"⏱️ 実行時間: {execution_time:.1f} 秒")
        print(f"📊 シミュレーション時間: {self.simulation_steps} ステップ")
        print()
        
        # 車両統計
        print(f"🚗 車両統計:")
        print(f"   累積車両数: {len(self.total_vehicles_seen)} 台")
        print(f"   最大同時車両数: {self.max_simultaneous_vehicles} 台")
        print()
        
        # 停止回数結果
        total_stops = sum(self.stop_counts.values())
        edges_with_stops = len([e for e, c in self.stop_counts.items() if c > 0])
        
        print(f"🛑 停止分析結果:")
        print(f"   総停止回数: {total_stops} 回")
        print(f"   停止発生エッジ数: {edges_with_stops}/{len(self.valid_edges)} 個")
        print(f"   監視対象エッジ数: {len(self.valid_edges)} 個")
        
        if total_stops > 0:
            avg_stops_per_edge = total_stops / len(self.valid_edges)
            avg_stops_per_vehicle = total_stops / len(self.total_vehicles_seen) if self.total_vehicles_seen else 0
            print(f"   エッジあたり平均: {avg_stops_per_edge:.2f} 回")
            print(f"   車両あたり平均: {avg_stops_per_vehicle:.2f} 回")
        
        print()
        
        # エッジ別停止回数（上位10件）
        if total_stops > 0:
            print("🎯 停止回数上位エッジ:")
            sorted_edges = sorted(self.stop_counts.items(), key=lambda x: x[1], reverse=True)
            for i, (edge_id, count) in enumerate(sorted_edges[:10]):
                if count > 0:
                    percentage = (count / total_stops) * 100
                    print(f"   {i+1:2d}. {edge_id}: {count:3d} 回 ({percentage:.1f}%)")
        
        print("="*70)
        
        # 結果をテキストファイルに保存（強制上書き）
        result_content = f"""停止回数カウント結果（修正版）
実行時刻: {self.start_datetime.strftime('%Y-%m-%d %H:%M:%S')} - {end_datetime.strftime('%H:%M:%S')}
実行時間: {execution_time:.1f} 秒
シミュレーション時間: {self.simulation_steps} ステップ

車両統計:
- 累積車両数: {len(self.total_vehicles_seen)} 台
- 最大同時車両数: {self.max_simultaneous_vehicles} 台

停止分析結果:
- 総停止回数: {total_stops} 回
- 停止発生エッジ数: {edges_with_stops} 個
- 監視対象エッジ数: {len(self.valid_edges)} 個

エッジ別停止回数:
"""
        
        if total_stops > 0:
            sorted_edges = sorted(self.stop_counts.items(), key=lambda x: x[1], reverse=True)
            for edge_id, count in sorted_edges:
                if count > 0:
                    result_content += f"{edge_id}: {count} 回\n"
        else:
            result_content += "停止は検出されませんでした\n"
        
        # ファイル保存（複数の場所に保存して確実性を高める）
        result_files = ["stop_count_results.txt", "stop_count_backup.txt"]
        
        for filename in result_files:
            try:
                filepath = os.path.join(self.log_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(result_content)
                    f.flush()  # 強制的にディスクに書き込み
                    os.fsync(f.fileno())  # OS レベルでの同期
                print(f"💾 結果を {filepath} に保存")
            except Exception as e:
                print(f"⚠️ {filepath} 保存エラー: {e}")
        
        # 詳細データも保存
        self.save_detailed_results()

def main():
    """メイン実行関数（修正版）"""
    counter = FixedStopCounter()
    
    print("="*70)
    print("🛑 修正版停止回数カウンター")
    print("="*70)
    print(f"開始時刻: {counter.start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ファイル存在確認
    if not counter.check_files_exist():
        return
    
    # SUMOコマンド設定
    sumo_cmd = ["sumo", "-c", "mixed_traffic.sumocfg", "--no-warnings", "--time-to-teleport", "-1"]
    
    try:
        print("🚀 SUMOシミュレーション開始...")
        traci.start(sumo_cmd)
        
        # エッジの存在確認
        if not counter.initialize_edges():
            return
        
        print(f"🎯 監視開始 - {len(counter.valid_edges)}個のエッジを監視")
        print(f"停止判定: 速度 ≤ {STOP_THRESHOLD} m/s, 継続時間 ≥ {MIN_STOP_DURATION} 秒")
        
        step = 0
        last_check_time = 0
        
        # シミュレーションループ
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            step += 1
            counter.simulation_steps = step
            current_time = traci.simulation.getTime()
            
            # 定期的に停止チェック
            if current_time - last_check_time >= CHECK_INTERVAL:
                new_stops = counter.check_vehicle_stops(current_time)
                last_check_time = current_time
            
            # 進捗表示
            if step % 200 == 0:
                vehicle_count = traci.vehicle.getIDCount()
                total_stops = sum(counter.stop_counts.values())
                
                print(f"📊 ステップ {step:4d} | 車両 {vehicle_count:3d} | 停止 {total_stops:4d} | 時刻 {current_time:6.0f}s")
    
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 結果表示と保存
        counter.print_results()
        
        # SUMO終了
        try:
            traci.close()
        except:
            pass
        
        print("✅ シミュレーション完了")

if __name__ == "__main__":
    main()