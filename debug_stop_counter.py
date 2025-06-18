"""
停止回数カウントデバッグスクリプト
問題の原因を特定するための詳細ログ出力

問題：車両数を変更しても停止回数が毎回837になる
"""

import traci
import sys
import os
from collections import defaultdict
import time

# 監視対象のエッジID（元のstop_counter.pyと同じ）
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

class DebugStopCounter:
    def __init__(self):
        self.stop_counts = defaultdict(int)
        self.vehicle_stop_states = {}
        self.valid_edges = []
        
        # デバッグ用カウンター
        self.debug_log = []
        self.vehicle_count_history = []
        self.edge_vehicle_count = defaultdict(int)
        self.total_vehicles_seen = set()
        
    def debug_network_info(self):
        """ネットワーク情報をデバッグ出力"""
        print("=" * 60)
        print("🔍 ネットワーク情報デバッグ")
        print("=" * 60)
        
        # 全エッジの取得
        all_edges = traci.edge.getIDList()
        print(f"📊 ネットワーク内の全エッジ数: {len(all_edges)}")
        
        # ターゲットエッジの存在確認
        valid_count = 0
        invalid_edges = []
        
        for edge_id in TARGET_EDGES:
            if edge_id in all_edges:
                self.valid_edges.append(edge_id)
                valid_count += 1
                print(f"✅ エッジ '{edge_id}' 存在")
            else:
                invalid_edges.append(edge_id)
                print(f"❌ エッジ '{edge_id}' 見つからない")
        
        print(f"\n📈 有効エッジ: {valid_count}/{len(TARGET_EDGES)}")
        
        if invalid_edges:
            print(f"⚠️ 見つからないエッジ数: {len(invalid_edges)}")
            print("見つからないエッジの例（最初の5個）:")
            for edge in invalid_edges[:5]:
                print(f"   - {edge}")
        
        return len(self.valid_edges) > 0
    
    def debug_vehicle_info(self, step):
        """車両情報をデバッグ出力"""
        current_vehicles = traci.vehicle.getIDList()
        vehicle_count = len(current_vehicles)
        
        # 車両数の履歴を記録
        self.vehicle_count_history.append((step, vehicle_count))
        
        # 新しい車両を記録
        for vid in current_vehicles:
            self.total_vehicles_seen.add(vid)
        
        # 車両タイプの分析
        vehicle_types = defaultdict(int)
        edge_distribution = defaultdict(int)
        
        for vid in current_vehicles:
            try:
                vtype = traci.vehicle.getTypeID(vid)
                vehicle_types[vtype] += 1
                
                edge_id = traci.vehicle.getRoadID(vid)
                edge_distribution[edge_id] += 1
                
                # ターゲットエッジにいる車両をカウント
                if edge_id in self.valid_edges:
                    self.edge_vehicle_count[edge_id] += 1
                    
            except:
                continue
        
        # 100ステップごとに詳細情報を出力
        if step % 100 == 0:
            print(f"\n🚗 ステップ {step} - 車両情報:")
            print(f"   現在の車両数: {vehicle_count}")
            print(f"   累積登場車両数: {len(self.total_vehicles_seen)}")
            
            print(f"   車両タイプ別:")
            for vtype, count in vehicle_types.items():
                print(f"     {vtype}: {count} 台")
            
            # ターゲットエッジの車両数
            target_edge_vehicles = sum(1 for vid in current_vehicles 
                                     if traci.vehicle.getRoadID(vid) in self.valid_edges)
            print(f"   ターゲットエッジ内車両: {target_edge_vehicles} 台")
    
    def debug_stop_detection(self, current_time):
        """停止検出のデバッグ"""
        current_vehicles = traci.vehicle.getIDList()
        stop_vehicles = []
        moving_vehicles = []
        
        for vid in current_vehicles:
            try:
                speed = traci.vehicle.getSpeed(vid)
                edge_id = traci.vehicle.getRoadID(vid)
                
                if edge_id in self.valid_edges:
                    if speed <= STOP_THRESHOLD:
                        stop_vehicles.append((vid, edge_id, speed))
                    else:
                        moving_vehicles.append((vid, edge_id, speed))
                        
            except:
                continue
        
        # 停止車両の詳細ログ
        if stop_vehicles:
            self.debug_log.append({
                'time': current_time,
                'stopped_vehicles': len(stop_vehicles),
                'moving_vehicles': len(moving_vehicles),
                'stop_details': stop_vehicles[:5]  # 最初の5台のみ
            })
    
    def check_vehicle_stops_debug(self, current_time):
        """停止チェック（デバッグ版）"""
        current_vehicles = set(traci.vehicle.getIDList())
        
        # 削除された車両の状態をクリア
        vehicles_to_remove = []
        for vehicle_id in self.vehicle_stop_states:
            if vehicle_id not in current_vehicles:
                vehicles_to_remove.append(vehicle_id)
        
        for vehicle_id in vehicles_to_remove:
            del self.vehicle_stop_states[vehicle_id]
        
        new_stops_this_step = 0
        
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
                                new_stops_this_step += 1
                                print(f"🛑 NEW STOP: 車両{vehicle_id} エッジ{edge_id} {stop_duration:.1f}秒停止 (総停止数: {sum(self.stop_counts.values())})")
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
        
        return new_stops_this_step
    
    def print_debug_summary(self):
        """デバッグサマリーを出力"""
        print("\n" + "=" * 70)
        print("🔍 デバッグサマリー")
        print("=" * 70)
        
        # 車両数の推移
        if self.vehicle_count_history:
            max_vehicles = max(count for step, count in self.vehicle_count_history)
            min_vehicles = min(count for step, count in self.vehicle_count_history)
            final_count = self.vehicle_count_history[-1][1]
            
            print(f"🚗 車両数の推移:")
            print(f"   最大同時車両数: {max_vehicles}")
            print(f"   最小同時車両数: {min_vehicles}")
            print(f"   最終車両数: {final_count}")
            print(f"   累積登場車両数: {len(self.total_vehicles_seen)}")
        
        # エッジ別車両通過数
        print(f"\n🛣️ エッジ別車両通過状況（上位10エッジ）:")
        sorted_edges = sorted(self.edge_vehicle_count.items(), 
                            key=lambda x: x[1], reverse=True)
        for i, (edge_id, count) in enumerate(sorted_edges[:10]):
            is_target = "✅" if edge_id in self.valid_edges else "❌"
            print(f"   {i+1:2d}. {edge_id}: {count} 台 {is_target}")
        
        # 停止カウント結果
        total_stops = sum(self.stop_counts.values())
        print(f"\n🛑 停止カウント結果:")
        print(f"   総停止回数: {total_stops}")
        print(f"   停止が発生したエッジ数: {len([e for e, c in self.stop_counts.items() if c > 0])}")
        
        if total_stops > 0:
            print(f"   エッジ別停止回数（上位5エッジ）:")
            sorted_stops = sorted(self.stop_counts.items(), 
                                key=lambda x: x[1], reverse=True)
            for i, (edge_id, count) in enumerate(sorted_stops[:5]):
                if count > 0:
                    print(f"     {i+1}. {edge_id}: {count} 回")
        
        # 停止検出ログの分析
        if self.debug_log:
            print(f"\n📊 停止検出ログ分析:")
            total_stop_events = sum(log['stopped_vehicles'] for log in self.debug_log)
            print(f"   総停止検出回数: {total_stop_events}")
            print(f"   ログエントリ数: {len(self.debug_log)}")

def main():
    """デバッグメイン関数"""
    debug_counter = DebugStopCounter()
    
    # SUMO設定の確認
    print("🔍 SUMO設定ファイルの確認")
    required_files = ["mixed_traffic.sumocfg", "routes.rou.xml"]
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} 存在")
            # ファイルサイズも確認
            size = os.path.getsize(file_path)
            print(f"   ファイルサイズ: {size} bytes")
        else:
            print(f"❌ {file_path} 見つからない")
    
    # routes.rou.xmlの車両数を確認
    if os.path.exists("routes.rou.xml"):
        try:
            with open("routes.rou.xml", "r", encoding="utf-8") as f:
                content = f.read()
                vehicle_count = content.count("<vehicle")
                flow_count = content.count("<flow")
                print(f"📊 routes.rou.xml 分析:")
                print(f"   <vehicle>タグ数: {vehicle_count}")
                print(f"   <flow>タグ数: {flow_count}")
        except Exception as e:
            print(f"⚠️ routes.rou.xml読み取りエラー: {e}")
    
    print("\n" + "="*60)
    
    # SUMOコマンド設定
    sumo_cmd = ["sumo", "-c", "mixed_traffic.sumocfg", "--no-warnings", "--time-to-teleport", "-1"]
    
    try:
        print("🚀 デバッグモードでSUMOを開始...")
        traci.start(sumo_cmd)
        
        # ネットワーク情報のデバッグ
        if not debug_counter.debug_network_info():
            print("❌ 有効なエッジが見つからないため終了")
            return
        
        print(f"\n🏁 シミュレーション開始（監視エッジ数: {len(debug_counter.valid_edges)}）")
        
        step = 0
        last_check_time = 0
        last_summary_time = 0
        
        # デバッグ用短縮シミュレーション（最大1000ステップ）
        max_steps = 1000
        
        while (traci.simulation.getMinExpectedNumber() > 0 and step < max_steps):
            traci.simulationStep()
            step += 1
            current_time = traci.simulation.getTime()
            
            # 車両情報のデバッグ
            debug_counter.debug_vehicle_info(step)
            
            # 停止検出のデバッグ
            if current_time - last_check_time >= CHECK_INTERVAL:
                debug_counter.debug_stop_detection(current_time)
                new_stops = debug_counter.check_vehicle_stops_debug(current_time)
                last_check_time = current_time
            
            # 200ステップごとに中間サマリー
            if step % 200 == 0:
                total_stops = sum(debug_counter.stop_counts.values())
                vehicle_count = traci.vehicle.getIDCount()
                print(f"\n📊 中間報告 (ステップ {step}):")
                print(f"   現在の車両数: {vehicle_count}")
                print(f"   累積停止回数: {total_stops}")
                print(f"   現在停止中の車両: {len(debug_counter.vehicle_stop_states)}")
    
    except Exception as e:
        print(f"❌ エラー発生: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # デバッグサマリーの出力
        debug_counter.print_debug_summary()
        
        # SUMO終了
        try:
            traci.close()
        except:
            pass
        
        print("\n🔍 デバッグ完了")
        print("="*60)

if __name__ == "__main__":
    main()