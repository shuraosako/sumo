#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合監視システム メインファイル（動的車両制御対応版）
CO2排出量と停止回数を同時に監視し、車両数を動的に制御するシステム

使用方法:
    python integrated_monitor.py --config ../config/mixed_traffic.sumocfg --vehicles 100 --av-penetration 50
    python integrated_monitor.py --gui --vehicles 100 --av-penetration 50
"""

import os
import sys
import traci
import time
import csv
import signal
import argparse
import random
from collections import defaultdict
from datetime import datetime

# 設定ファイルをインポート
try:
    from monitoring_config import (
        PathConfig, VehicleConfig, CO2MonitoringConfig, 
        StopMonitoringConfig, SimulationConfig, ReportConfig,
        DebugConfig, OutputConfig, validate_config
    )
except ImportError as e:
    print(f"❌ 設定ファイル読み込みエラー: {e}")
    print("monitoring_config.py が同じディレクトリにあることを確認してください")
    sys.exit(1)

class IntegratedMonitor:
    """
    CO2排出量と停止回数を同時に監視し、車両数を動的制御するクラス
    """
    
    def __init__(self):
        """初期化"""
        # 設定値検証
        config_errors = validate_config()
        if config_errors:
            print("❌ 設定エラーが検出されました:")
            for error in config_errors:
                print(f"   - {error}")
            sys.exit(1)
        
        # ===== 基本設定 =====
        self.log_dir = PathConfig.LOG_DIR
        self.ensure_log_directory()
        
        # ===== CO2監視関連 =====
        self.vehicle_types = {}
        self.co2_emissions = defaultdict(float)
        self.vehicle_distances = defaultdict(float)
        self.total_co2 = 0.0
        self.gasoline_co2 = 0.0
        self.av_co2 = 0.0
        self.emission_log = []
        
        # ===== 停止回数監視関連 =====
        self.target_edges = StopMonitoringConfig.TARGET_EDGES
        self.stop_threshold = StopMonitoringConfig.STOP_SPEED_THRESHOLD
        self.min_stop_duration = StopMonitoringConfig.MIN_STOP_DURATION
        self.check_interval = StopMonitoringConfig.CHECK_INTERVAL
        
        self.stop_counts = defaultdict(int)
        self.vehicle_stop_states = {}
        self.valid_stop_edges = []
        self.stop_events = []
        
        # ===== 動的車両制御関連 =====
        self.target_vehicle_count = 0  # 目標車両数（0で制御無効）
        self.target_av_penetration = 0.5  # 目標AV普及率
        self.valid_vehicle_edges = []  # 車両生成用有効エッジ
        self.vehicle_id_counter = 2000  # 新規車両ID用カウンター
        self.last_vehicle_control_time = 0  # 最後の制御時刻
        
        # ===== シミュレーション管理 =====
        self.step_count = 0
        self.start_time = time.time()
        self.start_datetime = datetime.now()
        self.total_vehicles_seen = set()
        self.max_simultaneous_vehicles = 0
        
        if DebugConfig.VERBOSE_MODE:
            print("✅ 統合監視システム初期化完了")
    
    def ensure_log_directory(self):
        """ログディレクトリ確保"""
        try:
            os.makedirs(self.log_dir, exist_ok=True)
            if DebugConfig.VERBOSE_MODE:
                print(f"📁 ログディレクトリ確認: {self.log_dir}")
        except Exception as e:
            print(f"⚠️ ログディレクトリ作成エラー: {e}")
            self.log_dir = "."  # フォールバック
    
    def set_vehicle_control_params(self, total_vehicles, av_penetration):
        """動的車両制御パラメータを設定"""
        self.target_vehicle_count = total_vehicles
        self.target_av_penetration = av_penetration / 100.0 if av_penetration > 1.0 else av_penetration
        
        if DebugConfig.VERBOSE_MODE:
            print(f"🚗 動的車両制御設定:")
            print(f"   目標車両数: {self.target_vehicle_count}")
            print(f"   目標AV普及率: {self.target_av_penetration:.1%}")
    
    def get_valid_vehicle_edges(self):
        """車両生成用の有効エッジを取得"""
        try:
            all_edges = traci.edge.getIDList()
            valid_edges = []
            
            for edge_id in all_edges:
                # 内部エッジや特殊エッジを除外
                if not edge_id.startswith(':') and len(edge_id) > 1:
                    # 逆方向エッジ（-で始まる）も含める
                    valid_edges.append(edge_id)
            
            if DebugConfig.VERBOSE_MODE:
                print(f"🛣️ 車両生成用エッジ数: {len(valid_edges)}")
            
            return valid_edges
        except Exception as e:
            print(f"⚠️ 車両用エッジ取得エラー: {e}")
            return []
    
    def add_vehicle(self, veh_id, is_av):
        """新しい車両を追加"""
        if not self.valid_vehicle_edges:
            return False
            
        max_attempts = 10
        veh_type = VehicleConfig.AUTONOMOUS_CAR_TYPE if is_av else VehicleConfig.GASOLINE_CAR_TYPE
        
        for attempt in range(max_attempts):
            try:
                from_edge = random.choice(self.valid_vehicle_edges)
                to_edge = random.choice([e for e in self.valid_vehicle_edges if e != from_edge])
                
                route = traci.simulation.findRoute(from_edge, to_edge)
                if route.edges:
                    route_id = f"route_{veh_id}"
                    traci.route.add(route_id, route.edges)
                    traci.vehicle.add(
                        vehID=veh_id,
                        routeID=route_id,
                        typeID=veh_type,
                        departPos="random"
                    )
                    
                    # 車両タイプを記録
                    self.vehicle_types[veh_id] = veh_type
                    
                    if DebugConfig.VERBOSE_MODE and attempt <= 2:  # 最初の3回のみ表示
                        print(f"🚗 車両追加: {veh_id} ({veh_type})")
                    
                    return True
            except Exception as e:
                if DebugConfig.VERBOSE_MODE:
                    print(f"⚠️ 車両追加試行{attempt+1}失敗: {e}")
                continue
        
        return False
    
    def update_vehicle_control(self, current_time, end_time):
        """動的車両制御を更新"""
        if self.target_vehicle_count == 0:
            return  # 制御無効
            
        # 終了60秒前まで車両追加
        if current_time >= end_time - VehicleConfig.STOP_GENERATION_BEFORE_END:
            return
            
        # 3秒ごとに制御チェック（頻繁すぎるチェックを防止）
        if current_time - self.last_vehicle_control_time < 3.0:
            return
        
        self.last_vehicle_control_time = current_time
        
        current_vehicles = list(traci.vehicle.getIDList())
        current_count = len(current_vehicles)
        
        # 車両不足時に補充
        if current_count < self.target_vehicle_count:
            shortage = min(self.target_vehicle_count - current_count, VehicleConfig.MAX_VEHICLES_PER_STEP)
            success_count = 0
            
            for _ in range(shortage):
                is_av = random.random() < self.target_av_penetration
                veh_id = f"dyn_{self.vehicle_id_counter}"
                
                if self.add_vehicle(veh_id, is_av):
                    success_count += 1
                    self.vehicle_id_counter += 1
            
            if success_count > 0 and DebugConfig.VERBOSE_MODE:
                print(f"🔄 車両補充: {success_count}台追加 (時刻: {current_time:.0f}s, 現在: {current_count + success_count}台)")
    
    def initialize_monitoring(self):
        """監視初期化"""
        if DebugConfig.VERBOSE_MODE:
            print("🔍 監視システム初期化中...")
        
        # 停止監視エッジの存在確認
        all_edges = traci.edge.getIDList()
        for edge_id in self.target_edges:
            if edge_id in all_edges:
                self.valid_stop_edges.append(edge_id)
        
        print(f"✅ 停止監視対象エッジ: {len(self.valid_stop_edges)}/{len(self.target_edges)} 個")
        
        if len(self.valid_stop_edges) == 0:
            print("❌ 有効な停止監視エッジが見つかりません")
            return False
        
        # 車両生成用エッジを取得
        self.valid_vehicle_edges = self.get_valid_vehicle_edges()
        if not self.valid_vehicle_edges:
            print("❌ 有効な車両生成エッジが見つかりません")
            return False
        
        # 初期車両登録（CO2監視用）
        vehicle_ids = traci.vehicle.getIDList()
        for vid in vehicle_ids:
            try:
                vtype = traci.vehicle.getTypeID(vid)
                self.vehicle_types[vid] = vtype
            except:
                if DebugConfig.CONTINUE_ON_MINOR_ERRORS:
                    continue
                else:
                    raise
        
        if DebugConfig.VERBOSE_MODE:
            print(f"🚗 初期車両登録完了: {len(self.vehicle_types)} 台")
        
        return True
    
    def update_co2_monitoring(self, current_time):
        """CO2排出量監視更新"""
        current_vehicles = set(traci.vehicle.getIDList())
        
        # 新しい車両を登録
        for vid in current_vehicles:
            if vid not in self.vehicle_types:
                try:
                    vtype = traci.vehicle.getTypeID(vid)
                    self.vehicle_types[vid] = vtype
                except:
                    if DebugConfig.CONTINUE_ON_MINOR_ERRORS:
                        continue
                    else:
                        raise
        
        # 各車両の排出量を取得
        step_gasoline_co2 = 0.0
        step_av_co2 = 0.0
        
        for vid in current_vehicles:
            if vid in self.vehicle_types:
                try:
                    # CO2排出量取得 (mg/s)
                    co2_emission = traci.vehicle.getCO2Emission(vid)
                    distance = traci.vehicle.getSpeed(vid)
                    vtype = self.vehicle_types[vid]
                    
                    # タイプ別に集計（mg → g 変換）
                    co2_g = co2_emission / CO2MonitoringConfig.MG_TO_G_CONVERSION
                    self.co2_emissions[vtype] += co2_g
                    self.vehicle_distances[vtype] += distance
                    
                    # 車両分類別集計
                    if vtype == VehicleConfig.GASOLINE_CAR_TYPE:
                        step_gasoline_co2 += co2_g
                    elif vtype == VehicleConfig.AUTONOMOUS_CAR_TYPE:
                        step_av_co2 += co2_g
                        
                except:
                    if DebugConfig.CONTINUE_ON_MINOR_ERRORS:
                        continue
                    else:
                        raise
        
        # 累積排出量更新
        self.gasoline_co2 += step_gasoline_co2
        self.av_co2 += step_av_co2
        self.total_co2 = self.gasoline_co2 + self.av_co2
        
        # ログに記録
        gasoline_count = len([v for v, t in self.vehicle_types.items() 
                            if t == VehicleConfig.GASOLINE_CAR_TYPE and v in current_vehicles])
        av_count = len([v for v, t in self.vehicle_types.items() 
                       if t == VehicleConfig.AUTONOMOUS_CAR_TYPE and v in current_vehicles])
        
        self.emission_log.append({
            'time': current_time,
            'gasoline_co2': step_gasoline_co2,
            'av_co2': step_av_co2,
            'total_gasoline': self.gasoline_co2,
            'total_av': self.av_co2,
            'gasoline_vehicles': gasoline_count,
            'av_vehicles': av_count
        })
    
    def update_stop_monitoring(self, current_time):
        """停止回数監視更新"""
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
                if edge_id in self.valid_stop_edges:
                    
                    if speed <= self.stop_threshold:
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
                            
                            if not stop_info['counted'] and stop_duration >= self.min_stop_duration:
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
                                
                                # リアルタイム表示（設定に基づく）
                                if new_stops_this_check <= StopMonitoringConfig.MAX_STOP_EVENTS_TO_PRINT:
                                    total_stops = sum(self.stop_counts.values())
                                    print(f"🛑 停止: 車両{vehicle_id} エッジ{edge_id} ({stop_duration:.1f}s) 総計:{total_stops}")
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
                if not DebugConfig.CONTINUE_ON_MINOR_ERRORS:
                    raise
        
        return new_stops_this_check
    
    def print_status(self, current_time):
        """現在の状況を表示"""
        current_vehicles = traci.vehicle.getIDList()
        
        # 車両数カウント
        gasoline_count = len([v for v, t in self.vehicle_types.items() 
                            if t == VehicleConfig.GASOLINE_CAR_TYPE and v in current_vehicles])
        av_count = len([v for v, t in self.vehicle_types.items() 
                       if t == VehicleConfig.AUTONOMOUS_CAR_TYPE and v in current_vehicles])
        
        total_stops = sum(self.stop_counts.values())
        total_vehicles = len(current_vehicles)
        
        # 制御状況表示
        control_status = ""
        if self.target_vehicle_count > 0:
            control_status = f" | 🎯 目標: {self.target_vehicle_count}"
        
        print(f"\r⏰ 時刻: {current_time:6.0f}s | "
              f"🚗 車両: {total_vehicles:3d}{control_status} | "
              f"🔴 ガソリン車: {gasoline_count:3d} | "
              f"🟢 AV車: {av_count:3d} | "
              f"💨 CO2: {self.gasoline_co2:8.{OutputConfig.CO2_DECIMAL_PLACES}f}g | "
              f"🛑 停止: {total_stops:4d}回", end="")
    
    def save_results(self):
        """結果保存"""
        if DebugConfig.VERBOSE_MODE:
            print("\n\n🔄 結果保存中...")
        
        print("\n\n" + OutputConfig.REPORT_SEPARATOR)
        print("           🎯 統合監視結果（動的制御対応版）")
        print(OutputConfig.REPORT_SEPARATOR)
        
        # 各種結果を保存
        self.save_co2_csv()
        self.save_co2_report()
        self.save_stop_results()
        self.save_stop_csv()
        
        # 統合サマリー表示
        self.print_integrated_summary()
        
        print(OutputConfig.REPORT_SEPARATOR)
        if DebugConfig.VERBOSE_MODE:
            print("✅ 結果保存完了")
    
    def save_co2_csv(self):
        """CO2データをCSVで保存"""
        csv_path = os.path.join(self.log_dir, PathConfig.CO2_EMISSION_LOG_CSV)
        try:
            with open(csv_path, 'w', newline=OutputConfig.CSV_NEWLINE, 
                     encoding=OutputConfig.CSV_ENCODING) as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'time', 'gasoline_co2', 'av_co2', 'total_gasoline', 
                    'total_av', 'gasoline_vehicles', 'av_vehicles'
                ])
                writer.writeheader()
                writer.writerows(self.emission_log)
            print(f"📊 CO2時系列データを{csv_path}に保存")
        except Exception as e:
            print(f"⚠️ CO2 CSV保存エラー: {e}")
    
    def save_co2_report(self):
        """CO2レポート保存"""
        # AV普及率計算
        if self.emission_log:
            latest_log = self.emission_log[-1]
            total_vehicles = latest_log['gasoline_vehicles'] + latest_log['av_vehicles']
            av_penetration_rate = latest_log['av_vehicles'] / total_vehicles if total_vehicles > 0 else 0.0
        else:
            av_penetration_rate = 0.0
            total_vehicles = 0
        
        # 制御統計
        control_info = ""
        if self.target_vehicle_count > 0:
            control_info = f"""
📊 動的車両制御統計:
   目標車両数: {self.target_vehicle_count}
   目標AV普及率: {self.target_av_penetration:.1%}
   生成車両ID範囲: dyn_2000 - dyn_{self.vehicle_id_counter-1}
"""
        
        report = f"""
{OutputConfig.REPORT_SEPARATOR}
CO2排出量測定結果レポート（統合監視・動的制御対応版）
{OutputConfig.REPORT_SEPARATOR}

📊 車両タイプ別排出量:
   🔴 ガソリン車総排出量: {self.gasoline_co2:.{OutputConfig.CO2_DECIMAL_PLACES}f} g
   🟢 AV車総排出量: {self.av_co2:.{OutputConfig.CO2_DECIMAL_PLACES}f} g
   📈 全体総排出量: {self.total_co2:.{OutputConfig.CO2_DECIMAL_PLACES}f} g

📊 シミュレーション統計:
   AV普及率: {av_penetration_rate:.3f}
   総車両数: {total_vehicles}
   累積監視車両数: {len(self.total_vehicles_seen)}
   最大同時車両数: {self.max_simultaneous_vehicles}
{control_info}
⏱️  シミュレーション時間: {self.step_count} ステップ
🕐 実行時間: {time.time() - self.start_time:.{OutputConfig.TIME_DECIMAL_PLACES}f} 秒
{OutputConfig.REPORT_SEPARATOR}
"""
        
        report_path = os.path.join(self.log_dir, PathConfig.CO2_EMISSION_REPORT_TXT)
        try:
            with open(report_path, 'w', encoding=OutputConfig.REPORT_ENCODING) as f:
                f.write(report)
            print(f"💾 CO2レポートを{report_path}に保存")
        except Exception as e:
            print(f"⚠️ CO2レポート保存エラー: {e}")
    
    def save_stop_results(self):
        """停止回数結果保存"""
        execution_time = time.time() - self.start_time
        total_stops = sum(self.stop_counts.values())
        edges_with_stops = len([e for e, c in self.stop_counts.items() if c > 0])
        
        # 制御統計
        control_info = ""
        if self.target_vehicle_count > 0:
            control_info = f"""
動的車両制御統計:
- 目標車両数: {self.target_vehicle_count}
- 目標AV普及率: {self.target_av_penetration:.1%}
- 生成車両数: {self.vehicle_id_counter - 2000}

"""
        
        result_content = f"""停止回数カウント結果（統合監視・動的制御対応版）

実行時刻: {self.start_datetime.strftime('%Y-%m-%d %H:%M:%S')} - {datetime.now().strftime('%H:%M:%S')}
実行時間: {execution_time:.{OutputConfig.TIME_DECIMAL_PLACES}f} 秒
シミュレーション時間: {self.step_count} ステップ

車両統計:
- 累積車両数: {len(self.total_vehicles_seen)} 台
- 最大同時車両数: {self.max_simultaneous_vehicles} 台

{control_info}停止分析結果:
- 総停止回数: {total_stops} 回
- 停止発生エッジ数: {edges_with_stops} 個
- 監視対象エッジ数: {len(self.valid_stop_edges)} 個

エッジ別停止回数:
"""
        
        if total_stops > 0:
            sorted_edges = sorted(self.stop_counts.items(), key=lambda x: x[1], reverse=True)
            for edge_id, count in sorted_edges:
                if count > 0:
                    result_content += f"{edge_id}: {count} 回\n"
        else:
            result_content += "停止は検出されませんでした\n"
        
        # ファイル保存
        result_path = os.path.join(self.log_dir, PathConfig.STOP_COUNT_RESULTS_TXT)
        try:
            with open(result_path, "w", encoding=OutputConfig.REPORT_ENCODING) as f:
                f.write(result_content)
            print(f"💾 停止結果を{result_path}に保存")
        except Exception as e:
            print(f"⚠️ 停止結果保存エラー: {e}")
    
    def save_stop_csv(self):
        """停止イベントをCSVで保存"""
        if self.stop_events:
            try:
                csv_path = os.path.join(self.log_dir, PathConfig.STOP_COUNT_DETAILED_CSV)
                with open(csv_path, 'w', newline=OutputConfig.CSV_NEWLINE, 
                         encoding=OutputConfig.CSV_ENCODING) as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        'time', 'vehicle_id', 'edge_id', 'duration', 'total_count'
                    ])
                    writer.writeheader()
                    writer.writerows(self.stop_events)
                print(f"📊 停止詳細データを{csv_path}に保存")
            except Exception as e:
                print(f"⚠️ 停止CSV保存エラー: {e}")
    
    def print_integrated_summary(self):
        """統合サマリー表示"""
        total_stops = sum(self.stop_counts.values())
        
        print("🎯 統合監視サマリー:")
        print(f"   💨 総CO2排出量: {self.total_co2:.{OutputConfig.CO2_DECIMAL_PLACES}f} g")
        print(f"   🛑 総停止回数: {total_stops} 回")
        print(f"   🚗 監視車両数: {len(self.total_vehicles_seen)} 台")
        
        if self.target_vehicle_count > 0:
            print(f"   🎯 車両制御: 目標{self.target_vehicle_count}台, AV{self.target_av_penetration:.1%}")
            print(f"   🔄 生成車両数: {self.vehicle_id_counter - 2000} 台")
        
        if len(self.total_vehicles_seen) > 0:
            avg_co2_per_vehicle = self.total_co2 / len(self.total_vehicles_seen)
            avg_stops_per_vehicle = total_stops / len(self.total_vehicles_seen)
            print(f"   📊 車両あたりCO2: {avg_co2_per_vehicle:.{OutputConfig.CO2_DECIMAL_PLACES}f} g/台")
            print(f"   📊 車両あたり停止: {avg_stops_per_vehicle:.{OutputConfig.CO2_DECIMAL_PLACES}f} 回/台")
        
        # 停止上位エッジ表示
        if total_stops > 0:
            print(f"   🎯 停止回数上位{StopMonitoringConfig.TOP_EDGES_TO_DISPLAY}エッジ:")
            sorted_edges = sorted(self.stop_counts.items(), key=lambda x: x[1], reverse=True)
            for i, (edge_id, count) in enumerate(sorted_edges[:StopMonitoringConfig.TOP_EDGES_TO_DISPLAY]):
                if count > 0:
                    print(f"      {i+1:2d}. {edge_id}: {count} 回")

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
    """メイン実行関数（動的制御対応版）"""
    parser = argparse.ArgumentParser(description='統合監視システム（CO2+停止回数+動的車両制御）')
    parser.add_argument('--config', '-c', default=PathConfig.DEFAULT_SUMO_CONFIG, 
                       help=f'SUMO設定ファイル (デフォルト: {PathConfig.DEFAULT_SUMO_CONFIG})')
    parser.add_argument('--gui', action='store_true', 
                       help='SUMO-GUIで実行')
    
    # 動的車両制御用パラメータ
    parser.add_argument('--vehicles', type=int, default=0,
                       help='目標車両数（0で動的制御無効）')
    parser.add_argument('--av-penetration', type=float, default=50.0,
                       help='AV普及率%% (0-100)')
    
    args = parser.parse_args()
    
    # SUMOコマンド設定
    sumo_binary = SimulationConfig.SUMO_GUI_BINARY if args.gui else SimulationConfig.SUMO_BINARY
    sumo_cmd = [sumo_binary, "-c", args.config] + SimulationConfig.SUMO_CMD_OPTIONS
    
    print("🔍 統合監視システム開始（動的制御対応版）...")
    print("【同時実行】CO2排出量測定 + 停止回数カウント + 動的車両制御")
    
    if args.vehicles > 0:
        print(f"【車両制御】目標{args.vehicles}台, AV普及率{args.av_penetration}%")
    else:
        print("【車両制御】無効（既存車両のみ監視）")
    
    print("⏹️  Ctrl+C で途中終了可能")
    print(OutputConfig.SECTION_SEPARATOR)
    
    # シグナルハンドラー設定
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        traci.start(sumo_cmd)
        monitor = IntegratedMonitor()
        
        # 動的車両制御を設定
        if args.vehicles > 0:
            monitor.set_vehicle_control_params(args.vehicles, args.av_penetration)
        
        # 監視初期化
        if not monitor.initialize_monitoring():
            print("❌ 監視初期化に失敗しました")
            return
        
        last_check_time = 0
        
        # シミュレーションループ
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            monitor.step_count += 1
            current_time = traci.simulation.getTime()
            
            # CO2監視更新
            monitor.update_co2_monitoring(current_time)
            
            # 停止監視更新
            if current_time - last_check_time >= monitor.check_interval:
                monitor.update_stop_monitoring(current_time)
                last_check_time = current_time
            
            # 動的車両制御を追加
            if args.vehicles > 0:
                monitor.update_vehicle_control(current_time, SimulationConfig.DEFAULT_END_TIME)
            
            # 定期的に表示更新
            if monitor.step_count % CO2MonitoringConfig.REPORT_INTERVAL_STEPS == 0:
                monitor.print_status(current_time)

            
        
        print("\n\n🎉 統合監視完了!")
        monitor.save_results()
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        if DebugConfig.DEBUG_MODE:
            import traceback
            traceback.print_exc()
    finally:
        try:
            traci.close()
        except:
            pass

if __name__ == "__main__":
    main()