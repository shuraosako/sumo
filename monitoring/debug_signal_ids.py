#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信号機ID調査用デバッグスクリプト
SUMOネットワークの実際の信号機IDとエッジIDの対応関係を調べる
"""

import sys
import traci
import os

# 設定ファイルをインポート
try:
    from monitoring_config import PathConfig, SimulationConfig
    print("✅ 設定ファイル読み込み成功")
except ImportError as e:
    print(f"⚠️ 設定ファイルが見つかりません: {e}")
    # デフォルト設定
    class PathConfig:
        DEFAULT_SUMO_CONFIG = "../config/mixed_traffic.sumocfg"
    class SimulationConfig:
        SUMO_BINARY = "sumo"
        SUMO_CMD_OPTIONS = ["--start", "--no-warnings", "--time-to-teleport", "-1"]

def investigate_network_structure():
    """ネットワーク構造を調査"""
    try:
        # SUMO設定ファイルが存在するか確認
        config_file = PathConfig.DEFAULT_SUMO_CONFIG
        if not os.path.exists(config_file):
            print(f"❌ SUMO設定ファイルが見つかりません: {config_file}")
            return False
        
        print(f"🔍 SUMO設定ファイル: {config_file}")
        
        # SUMOを起動
        sumo_cmd = [SimulationConfig.SUMO_BINARY, "-c", config_file] + SimulationConfig.SUMO_CMD_OPTIONS
        print(f"🚀 SUMOコマンド: {' '.join(sumo_cmd)}")
        
        traci.start(sumo_cmd)
        print("✅ SUMO接続成功")
        
        print("\n" + "="*70)
        print("            🚦 信号機ID調査結果")
        print("="*70)
        
        # 1. 全ての信号機IDを取得
        traffic_light_ids = traci.trafficlight.getIDList()
        print(f"📊 検出された信号機数: {len(traffic_light_ids)}")
        print("📋 信号機IDリスト:")
        for i, tl_id in enumerate(sorted(traffic_light_ids)):
            print(f"   {i+1:2d}. {tl_id}")
        
        print("\n" + "-"*70)
        
        # 2. 全てのエッジIDを取得
        edge_ids = traci.edge.getIDList()
        print(f"📊 検出されたエッジ数: {len(edge_ids)}")
        
        # 数値エッジIDのみを抽出
        numeric_edges = []
        for edge_id in edge_ids:
            try:
                # 数値に変換できるエッジIDを探す
                int(edge_id)
                numeric_edges.append(edge_id)
            except ValueError:
                continue
        
        numeric_edges = sorted(numeric_edges, key=lambda x: int(x))
        print(f"📋 数値エッジIDリスト: {numeric_edges}")
        
        print("\n" + "-"*70)
        
        # 3. エッジと信号機の対応関係を調べる
        print("🔍 エッジと信号機の対応関係調査:")
        
        edge_to_signals = {}
        signal_to_edges = {}
        
        for tl_id in traffic_light_ids:
            try:
                # 各信号機が制御するレーンを取得
                controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
                controlled_edges = set()
                
                for lane in controlled_lanes:
                    # レーン名からエッジIDを抽出 (例: "1_0" -> "1")
                    edge_id = lane.split('_')[0]
                    controlled_edges.add(edge_id)
                
                signal_to_edges[tl_id] = list(controlled_edges)
                
                for edge_id in controlled_edges:
                    if edge_id not in edge_to_signals:
                        edge_to_signals[edge_id] = []
                    edge_to_signals[edge_id].append(tl_id)
                
            except Exception as e:
                print(f"   ⚠️ 信号機 {tl_id} の調査中にエラー: {e}")
        
        print("\n📋 信号機 → 制御エッジ の対応:")
        for tl_id, edges in sorted(signal_to_edges.items()):
            edges_str = ", ".join(sorted(edges))
            print(f"   信号機 '{tl_id}' → エッジ [{edges_str}]")
        
        print("\n📋 エッジ → 信号機 の対応:")
        for edge_id, signals in sorted(edge_to_signals.items()):
            if edge_id in [str(i) for i in range(1, 13)] + [str(-i) for i in range(1, 13)]:
                signals_str = ", ".join(signals)
                print(f"   エッジ '{edge_id}' → 信号機 [{signals_str}]")
        
        print("\n" + "-"*70)
        
        # 4. 道路1-12, -1--12 の対応する交差点/信号機を特定
        print("🎯 道路1-12, -1--12 に対応する信号機予測:")
        
        target_roads = [str(i) for i in range(1, 13)] + [str(-i) for i in range(1, 13)]
        road_to_next_signal = {}
        
        for road_id in target_roads:
            if road_id in edge_to_signals:
                signals = edge_to_signals[road_id]
                if signals:
                    # 最初の信号機を使用（複数ある場合）
                    next_signal = signals[0]
                    road_to_next_signal[road_id] = next_signal
                    
                    direction = "正方向" if int(road_id) > 0 else "逆方向"
                    print(f"   道路{road_id}({direction}) → 信号機 '{next_signal}'")
        
        print("\n" + "-"*70)
        
        # 5. 信号機の詳細情報を確認（最初の5つ）
        print("🔍 信号機詳細情報サンプル:")
        
        sample_signals = list(traffic_light_ids)[:5]
        for tl_id in sample_signals:
            try:
                current_state = traci.trafficlight.getRedYellowGreenState(tl_id)
                current_phase = traci.trafficlight.getPhase(tl_id)
                controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
                
                print(f"\n   信号機 '{tl_id}':")
                print(f"     現在の状態: {current_state}")
                print(f"     現在のフェーズ: {phase}")
                print(f"     制御レーン数: {len(controlled_lanes)}")
                print(f"     制御レーン: {controlled_lanes[:3]}{'...' if len(controlled_lanes) > 3 else ''}")
                
            except Exception as e:
                print(f"   ⚠️ 信号機 {tl_id} の詳細取得エラー: {e}")
        
        print("\n" + "="*70)
        print("🎯 推奨修正内容:")
        print("="*70)
        
        if road_to_next_signal:
            print("✅ 道路→信号機の対応関係が特定できました！")
            print("\n修正すべき内容:")
            print("1. AVSignalPredictor.predict_next_junction() メソッドを以下のように修正:")
            print("   ```python")
            print("   def get_signal_id_for_road(self, road_id):")
            print("       # 実際の対応関係に基づく信号機ID取得")
            print("       road_to_signal_map = {")
            for road_id, signal_id in sorted(road_to_next_signal.items()):
                print(f"           '{road_id}': '{signal_id}',")
            print("       }")
            print("       return road_to_signal_map.get(str(road_id))")
            print("   ```")
            
            print("\n2. または、以下のパターンが見つかった場合の自動変換:")
            # 信号機IDのパターンを分析
            signal_patterns = set()
            for signal_id in traffic_light_ids:
                if any(char.isdigit() for char in signal_id):
                    signal_patterns.add(signal_id)
            
            print(f"   検出された信号機IDパターン: {sorted(signal_patterns)[:10]}")
        else:
            print("❌ 道路→信号機の対応関係を特定できませんでした")
            print("SUMOネットワークファイルの構造を再確認してください")
        
        return True
        
    except Exception as e:
        print(f"❌ 調査中にエラーが発生: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            traci.close()
            print("\n✅ SUMO接続を終了しました")
        except:
            pass

def main():
    """メイン実行関数"""
    print("🔍 SUMO信号機ID調査ツール")
    print("="*50)
    
    success = investigate_network_structure()
    
    if success:
        print("\n🎉 調査完了!")
        print("上記の結果を基にAV信号予測機能を修正してください。")
    else:
        print("\n❌ 調査失敗")
        print("SUMO設定ファイルとネットワークファイルを確認してください。")

if __name__ == "__main__":
    main()