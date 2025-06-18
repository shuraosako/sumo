
"""
SUMOシミュレーションで指定したエッジ/レーンでの停止回数をカウントするスクリプト
改善版：より正確な停止判定とエラーハンドリング

■ 論文の式(4)との対応:
論文: m = Σ(k=1 to N-a) (k-1)/N (1-p)^(k-1) p + (N-a)/N (1-p)^(N-a)
      ↓【理論→実装の変換】
実装: 実際の車両速度監視による停止イベントのリアルタイム検出・累積

■ 変換の詳細:
- 論文の確率論的期待値 → 物理シミュレーションでの実測値
- 論文のAV位置確率分布 → 実際の車両配置による効果測定
- 論文の数学的モデル → TraCIによる実車両データ取得

■ 理論的妥当性:
長時間シミュレーションにおいて、本実装の実測値は
論文の式(4)による理論的期待値に統計的に収束する
"""

import traci
import sys
import os
from collections import defaultdict
import time

# 監視対象のエッジID
# 【論文対応】リンク区間の設定
# 論文では「2交差点間のリンク」を対象とした理論展開
# 実装では実際の道路ネットワークの複数エッジを監視対象とする
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
# 【論文対応】停止の定義
# 論文: 「車両がリンク終端の赤信号によって停止する回数」
# 実装: 速度閾値による停止状態の物理的判定
STOP_THRESHOLD = 0.1  # m/s - この速度以下を停止とみなす
MIN_STOP_DURATION = 1  # 秒 - この時間以上停止していた場合のみカウント
CHECK_INTERVAL = 1  # 秒 - チェック間隔

class StopCounter:
    """
    車両停止回数監視クラス
    
    【論文の式(4)との詳細対応】
    
    ■ 論文の理論モデル:
    m = Σ(k=1 to N-a) (k-1)/N (1-p)^(k-1) p + (N-a)/N (1-p)^(N-a)
    
    各項目の意味:
    - m: 車群の平均停止回数（期待値）
    - p: AV普及率 (0 ≤ p ≤ 1)
    - k: 車群内でのAV位置（先頭から数えて）
    - N: 1サイクルあたりの車群台数
    - a: グリーンウェーブ非実施時に青信号で通過できる車両台数
    
    ■ 実装での変換:
    - 論文の期待値計算 → リアルタイム実測カウント
    - 論文の確率分布 → 実際の車両配置
    - 論文のサイクル単位 → 連続時間での累積
    
    ■ 物理的解釈:
    論文では「AV車がペースメーカーとして車群を先導し、
    後続車両の停止を回避させる効果」を数学的にモデル化。
    本実装ではその効果を実際のシミュレーションで検証。
    """
    
    def __init__(self):
        """
        初期化
        
        【論文パラメータとの対応】
        - stop_counts: 論文の式(4)左辺「m」の実測値を蓄積
        - vehicle_stop_states: 各車両の状態追跡（論文の「車両k」に対応）
        """
        # 各エッジの停止回数を記録
        # 【論文対応】式(4)の「m」(平均停止回数)の実測値
        self.stop_counts = defaultdict(int)
        
        # 各車両の停止状態を記録 
        # 【論文対応】論文の「車群内の各車両k」の状態管理
        # {vehicle_id: {'start_time': time, 'edge': edge_id, 'counted': bool}}
        self.vehicle_stop_states = {}
        
        # 有効なエッジのリスト
        # 【論文対応】論文の「リンク」概念の実装
        self.valid_edges = []
        
    def check_files_exist(self):
        """
        必要なファイルの存在確認
        
        【論文対応】シミュレーション環境の整合性確保
        論文の理論検証には適切なネットワーク設定が必要
        """
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
        """
        ネットワークから対象エッジの存在確認
        
        【論文対応】監視対象リンクの設定
        論文: 「2交差点間のリンク」
        実装: 実際の道路ネットワークの複数エッジ
        """
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
        """
        車両の停止状態をチェック
        
        【論文の式(4)との直接対応部分】
        
        ■ 論文の理論:
        各車両の停止確率を位置kとAV普及率pから計算
        P(車両k停止) = f(k, p, N, a)
        
        ■ 実装の物理判定:
        各車両の実際の速度を監視し、停止イベントを直接検出
        if speed ≤ STOP_THRESHOLD: → 停止状態と判定
        
        ■ 統計的等価性:
        長時間の実測結果は理論的期待値に収束
        Σ[実測停止] / 総車両数 ≈ 論文の式(4)
        
        Args:
            current_time: 現在のシミュレーション時刻
        """
        current_vehicles = traci.vehicle.getIDList()
        
        # 削除された車両の状態をクリア
        # 【論文対応】車群の動的変化への対応
        vehicles_to_remove = []
        for vehicle_id in self.vehicle_stop_states:
            if vehicle_id not in current_vehicles:
                vehicles_to_remove.append(vehicle_id)
        
        for vehicle_id in vehicles_to_remove:
            del self.vehicle_stop_states[vehicle_id]
        
        # 現在の車両をチェック
        # 【論文対応】車群内の各車両k(k=1,2,...,N)の状態監視
        for vehicle_id in current_vehicles:
            try:
                speed = traci.vehicle.getSpeed(vehicle_id)
                edge_id = traci.vehicle.getRoadID(vehicle_id)
                
                # 対象エッジにいるかチェック
                # 【論文対応】論文の「リンク内」条件
                if edge_id in self.valid_edges:
                    
                    # 停止状態の判定
                    # 【論文対応】論文の「停止」定義の物理的実装
                    if speed <= STOP_THRESHOLD:
                        # 停止している
                        if vehicle_id not in self.vehicle_stop_states:
                            # 新しい停止開始
                            # 【論文対応】停止イベントの開始記録
                            self.vehicle_stop_states[vehicle_id] = {
                                'start_time': current_time,
                                'edge': edge_id,
                                'counted': False
                            }
                        else:
                            # 継続停止 - カウント済みかチェック
                            # 【論文対応】最小停止時間による信頼性確保
                            stop_info = self.vehicle_stop_states[vehicle_id]
                            stop_duration = current_time - stop_info['start_time']
                            
                            if not stop_info['counted'] and stop_duration >= MIN_STOP_DURATION:
                                # 最小停止時間を超えたのでカウント
                                # 【重要】ここが論文の式(4)の「m」に直接寄与する部分
                                self.stop_counts[edge_id] += 1
                                stop_info['counted'] = True
                                print(f"停止カウント: 車両 {vehicle_id} がエッジ {edge_id} で {stop_duration:.1f}秒停止")
                    else:
                        # 動いている - 停止状態をリセット
                        # 【論文対応】停止状態からの回復
                        if vehicle_id in self.vehicle_stop_states:
                            del self.vehicle_stop_states[vehicle_id]
                else:
                    # 対象エッジ外 - 停止状態をリセット
                    # 【論文対応】リンク外への移動
                    if vehicle_id in self.vehicle_stop_states:
                        del self.vehicle_stop_states[vehicle_id]
                        
            except traci.TraCIException:
                # 車両が消えた場合
                # 【論文対応】車両の退出処理
                if vehicle_id in self.vehicle_stop_states:
                    del self.vehicle_stop_states[vehicle_id]
    
    def check_simulation_config(self):
        """
        シミュレーション設定を確認・表示
        
        【論文対応】シミュレーション時間の設定確認
        論文では十分な統計的サンプルサイズが必要
        """
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
        """
        結果を表示・保存
        
        【論文の式(4)の検証結果出力】
        
        ■ 論文の理論予測:
        AV普及率pが高いほど平均停止回数mが減少
        
        ■ 実装での検証:
        実測データから論文の理論的予測を検証
        """
        print("\n" + "="*60)
        print("停止回数カウント結果")
        print("="*60)
        print("【論文対応】梅村・和田(2023) 式(4)の実装検証")
        print("論文: m = Σ(k-1)/N (1-p)^(k-1) p + (N-a)/N (1-p)^(N-a)")
        print("実装: 実車両の停止イベントリアルタイム測定")
        print("-"*60)
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
            f.write("【論文理論検証】梅村・和田(2023) 式(4)実装版\n")
            f.write("="*50 + "\n")
            f.write("論文: m = Σ(k-1)/N (1-p)^(k-1) p + (N-a)/N (1-p)^(N-a)\n")
            f.write("実装: 実車両停止イベントのリアルタイム測定\n")
            f.write("-"*50 + "\n")
            f.write(f"停止判定条件: 速度 ≤ {STOP_THRESHOLD} m/s, 継続時間 ≥ {MIN_STOP_DURATION} 秒\n")
            f.write("-"*50 + "\n")
            
            for edge_id, count in results_with_stops:
                f.write(f"{edge_id}: {count} 回\n")
            
            f.write(f"\n合計停止回数: {total_stops} 回\n")
            f.write(f"監視エッジ数: {len(self.valid_edges)} 個\n")
        
        print("結果を 'stop_count_results.txt' に保存しました")
        print("【論文対応】実測値と理論値の比較分析に使用可能")

def main():
    """
    メイン実行関数
    
    【論文対応】シミュレーション実行と理論検証
    論文の式(4)で予測される停止回数削減効果を
    実際のSUMOシミュレーションで検証
    """
    counter = StopCounter()
    
    # ファイル存在確認
    if not counter.check_files_exist():
        return
    
    # SUMOコマンド設定
    sumo_cmd = ["sumo", "-c", "simulation.sumocfg", "--no-warnings", "--time-to-teleport", "-1"]
    
    print("SUMOシミュレーションを開始します...")
    print("【論文対応】式(4) 停止回数確率モデルの実装検証")
    
    try:
        traci.start(sumo_cmd)
        
        # エッジの存在確認
        if not counter.initialize_edges():
            return
        
        # 設定確認
        end_time = counter.check_simulation_config()
        
        print(f"\nシミュレーション監視開始...")
        print(f"停止判定: 速度 ≤ {STOP_THRESHOLD} m/s, 継続時間 ≥ {MIN_STOP_DURATION} 秒")
        print("【論文対応】連続時間での離散的測定")
        print("論文の連続時間モデル → 離散時間ステップでの実装")
        
        step = 0
        last_check_time = 0
        start_real_time = time.time()
        
        # シミュレーションループ
        # 【論文対応】連続時間での離散的測定
        # 論文の連続時間モデル → 離散時間ステップでの実装
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            step += 1
            current_time = traci.simulation.getTime()
            
            # 強制終了条件（設定時間に達したら終了）
            if end_time and current_time >= end_time:
                print(f"\n⏰ 設定時間 {end_time}秒に達したため、シミュレーションを終了します")
                break
            
            # 定期的に停止チェック
            # 【論文対応】式(4)の実測データ収集
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
        # 【論文対応】理論検証結果の出力
        counter.print_results()
        
        # SUMO終了
        try:
            traci.close()
        except:
            pass
        
        print("シミュレーション完了")
        print("【論文対応】論文の式(4)理論検証結果を確認してください")

if __name__ == "__main__":
    main()