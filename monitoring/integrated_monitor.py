#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合監視システム メインファイル（AV信号予測機能追加版）
CO2排出量と停止回数を同時に監視し、車両数を動的に制御するシステム
+ AV車の信号先読み予測機能

新機能:
- AV車が道路に入った時の信号先読み予測
- 青信号までの残り時間(S)を計算・記録

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
    # AV信号予測設定をインポート（新機能）
    try:
        from monitoring_config import AVSignalConfig
        AV_SIGNAL_ENABLED = True
    except ImportError:
        AV_SIGNAL_ENABLED = False
        print("ℹ️ AV信号予測機能は無効です（設定が見つかりません）")
except ImportError as e:
    print(f"❌ 設定ファイル読み込みエラー: {e}")
    print("monitoring_config.py が同じディレクトリにあることを確認してください")
    sys.exit(1)

class AVSignalPredictor:
    """AV車向け先読み信号予測クラス"""
    
    def __init__(self):
        """初期化"""
        self.direction_cache = {}  # 信号方向インデックスのキャッシュ
        self.verbose = DebugConfig.VERBOSE_MODE
    
    def get_signal_id_for_road(self, current_edge_id: int) -> str:
        """現在の道路IDから対応する信号機IDを取得（実際のSUMOネットワークに基づく）"""
        # 実際のSUMOネットワークで判明した道路→信号機の対応関係
        road_to_signal_map = {
            '1': 'J1',
            '2': '1682382343',
            '3': '818521964',
            '4': '818520867',
            '5': 'J0',
            '6': 'cluster_2579637038_818520857',
            '7': '818520813',
            '8': '1717000300',
            '9': '1846875078',
            '10': '818520784',
            '11': '1818759484',
            '12': '8154759359',
            '-1': 'J13',
            '-2': '8154759359',
            '-3': '1818759484',
            '-4': '818520784',
            '-5': '1846875078',
            '-6': '1717000300',
            '-7': '818520813',
            '-8': 'cluster_2579637038_818520857',
            '-9': 'J0',
            '-10': '818520867',
            '-11': '818521964',
            '-12': '1682382343',
        }
        
        signal_id = road_to_signal_map.get(str(current_edge_id))
        if not signal_id:
            if self.verbose:
                print(f"⚠️ 道路{current_edge_id}に対応する信号機が見つかりません")
            return None
        
        return signal_id
    
    def get_signal_direction_index(self, junction_id: str, edge_id: int) -> int:
        """進行方向に対応する信号インデックスを取得"""
        cache_key = f"{junction_id}_{edge_id}"
        
        if cache_key in self.direction_cache:
            return self.direction_cache[cache_key]
        
        try:
            # 交差点の制御レーン情報を取得
            controlled_lanes = traci.trafficlight.getControlledLanes(junction_id)
            
            # 進行方向を判定
            is_positive_direction = edge_id > 0
            
            # 進行方向に対応するレーンインデックスを探す
            for i, lane in enumerate(controlled_lanes):
                try:
                    lane_edge_id = int(lane.split('_')[0])
                    
                    if (is_positive_direction and lane_edge_id > 0) or \
                       (not is_positive_direction and lane_edge_id < 0):
                        signal_index = i % 4  # 通常は4方向（NSEW）
                        self.direction_cache[cache_key] = signal_index
                        return signal_index
                except (ValueError, IndexError):
                    continue
            
            # デフォルト：正方向=0, 逆方向=2
            default_index = 0 if is_positive_direction else 2
            self.direction_cache[cache_key] = default_index
            return default_index
            
        except traci.TraCIException as e:
            if self.verbose:
                print(f"⚠️ 信号方向取得エラー {junction_id}: {e}")
            return 0 if edge_id > 0 else 2
    
    def calculate_time_to_green(self, junction_id: str, signal_index: int) -> float:
        """指定方向の信号が次に青になるまでの時間を計算"""
        try:
            # 現在の信号状態を取得
            current_state = traci.trafficlight.getRedYellowGreenState(junction_id)
            current_phase = traci.trafficlight.getPhase(junction_id)
            time_to_next_switch = traci.trafficlight.getNextSwitch(junction_id) - traci.simulation.getTime()
            
            # 信号プログラム定義を取得
            programs = traci.trafficlight.getCompleteRedYellowGreenDefinition(junction_id)
            
            if not programs:
                return 0.0
            
            current_program = programs[0]
            phases = current_program.phases
            
            if signal_index >= len(current_state):
                return 0.0
            
            # 現在の信号状態をチェック
            current_signal = current_state[signal_index]
            
            if current_signal.upper() == 'G':
                # 既に青の場合は次回の青まで計算
                accumulated_time = time_to_next_switch
                next_phase_idx = (current_phase + 1) % len(phases)
                
                while next_phase_idx != current_phase:
                    phase = phases[next_phase_idx]
                    phase_state = phase.state
                    
                    if signal_index < len(phase_state) and phase_state[signal_index].upper() == 'G':
                        return accumulated_time
                    
                    accumulated_time += phase.duration
                    next_phase_idx = (next_phase_idx + 1) % len(phases)
                
                return time_to_next_switch
            else:
                # 赤または黄の場合、次の青を探す
                accumulated_time = time_to_next_switch
                next_phase_idx = (current_phase + 1) % len(phases)
                
                while True:
                    phase = phases[next_phase_idx]
                    phase_state = phase.state
                    
                    if signal_index < len(phase_state) and phase_state[signal_index].upper() == 'G':
                        return accumulated_time
                    
                    accumulated_time += phase.duration
                    next_phase_idx = (next_phase_idx + 1) % len(phases)
                    
                    if next_phase_idx == (current_phase + 1) % len(phases):
                        break
                
                return accumulated_time
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ {junction_id}の信号計算エラー: {e}")
            return 0.0
    
    def calculate_time_to_red(self, signal_id: str, signal_index: int) -> float:
        """指定方向の信号が次に赤になるまでの時間を計算"""
        try:
            # 現在の信号状態を取得
            current_state = traci.trafficlight.getRedYellowGreenState(signal_id)
            current_phase = traci.trafficlight.getPhase(signal_id)
            time_to_next_switch = traci.trafficlight.getNextSwitch(signal_id) - traci.simulation.getTime()
            
            # 信号プログラム定義を取得
            programs = traci.trafficlight.getCompleteRedYellowGreenDefinition(signal_id)
            
            if not programs:
                return 0.0
            
            current_program = programs[0]
            phases = current_program.phases
            
            if signal_index >= len(current_state):
                return 0.0
            
            # 現在の信号状態をチェック
            current_signal = current_state[signal_index]
            
            if current_signal.upper() == 'R':
                # 既に赤の場合：次の青フェーズ + その青フェーズの終了まで
                accumulated_time = time_to_next_switch
                next_phase_idx = (current_phase + 1) % len(phases)
                
                # 次の青フェーズを探す
                while next_phase_idx != current_phase:
                    phase = phases[next_phase_idx]
                    phase_state = phase.state
                    
                    if signal_index < len(phase_state) and phase_state[signal_index].upper() == 'G':
                        # 青フェーズが見つかった - この青フェーズの終了時間まで加算
                        accumulated_time += phase.duration
                        
                        # この青フェーズの次を確認（黄があるかも）
                        yellow_phase_idx = (next_phase_idx + 1) % len(phases)
                        if yellow_phase_idx < len(phases):
                            yellow_phase = phases[yellow_phase_idx]
                            if signal_index < len(yellow_phase.state) and yellow_phase.state[signal_index].upper() == 'Y':
                                accumulated_time += yellow_phase.duration
                        
                        return accumulated_time
                    
                    accumulated_time += phase.duration
                    next_phase_idx = (next_phase_idx + 1) % len(phases)
                
                return accumulated_time
                
            elif current_signal.upper() == 'G':
                # 現在青の場合：青の残り時間 + 黄色時間
                accumulated_time = time_to_next_switch
                
                # 次のフェーズが黄色かチェック
                next_phase_idx = (current_phase + 1) % len(phases)
                if next_phase_idx < len(phases):
                    next_phase = phases[next_phase_idx]
                    if signal_index < len(next_phase.state) and next_phase.state[signal_index].upper() == 'Y':
                        accumulated_time += next_phase.duration
                
                return accumulated_time
                
            elif current_signal.upper() == 'Y':
                # 現在黄の場合：黄の残り時間
                return time_to_next_switch
                
            else:
                return 0.0
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ {signal_id}の赤信号計算エラー: {e}")
            return 0.0
    
    def get_green_phase_duration(self, signal_id: str, signal_index: int) -> float:
        """信号サイクルの最初の青フェーズの時間を取得"""
        try:
            # 信号プログラム定義を取得
            programs = traci.trafficlight.getCompleteRedYellowGreenDefinition(signal_id)
            
            if not programs:
                return 0.0
            
            current_program = programs[0]
            phases = current_program.phases
            
            # 最初の青フェーズを探す
            for phase in phases:
                if signal_index < len(phase.state) and phase.state[signal_index].upper() == 'G':
                    return phase.duration
            
            return 0.0
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ {signal_id}の青フェーズ時間取得エラー: {e}")
            return 0.0
    
    def get_lane_length(self, vehicle_id: str) -> float:
        """車両が現在いるレーンの長さを取得"""
        try:
            # 車両の現在のレーンIDを取得
            current_lane = traci.vehicle.getLaneID(vehicle_id)
            
            # レーンの長さを取得（メートル単位）
            length = traci.lane.getLength(current_lane)
            return length
            
        except Exception as e:
            if self.verbose:
                print(f"⚠️ 車両{vehicle_id}のレーン長取得エラー: {e}")
            return 0.0
    
    def calculate_speed(self, L: float, P: float, S: float, R: float, G: float) -> float:
        """
        交通信号制御における車両の最適速度を決定する関数
        
        Parameters:
        L (float): リンク長（メートル）
        P (float): AV車の普及率（0-1の小数）
        S (float): 次の信号が青になるまでの時間[s]
        R (float): 次の信号が赤になるまでの時間[s]
        G (float): 次の信号の青信号継続時間[s]
        
        Returns:
        float: 決定された速度（km/h）
        """
        C = 90  # サイクル長[s]
        vj = 60  # 法定速度[km/h]
        T = G * P  # 閾値[s]
        
        # ゼロ除算防止のためのガード条件
        if S <= 0.1 or R <= 0.1 or L <= 0.1 or G <= 0:
            # 信号情報が不正な場合は法定速度で走行
            if self.verbose:
                print(f"⚠️ 信号情報不正 (S:{S:.1f}, R:{R:.1f}, L:{L:.1f}, G:{G:.1f}) → 法定速度{vj}km/h使用")
            return vj
        
        # 速度決定ロジック
        if R <= T:  # （青）次の信号に合わせると遅すぎるから法定速度で走る
            v = vj
        elif (L / S) * 3.6 <= vj:  # 次の青にビタで入るように走る
            v = (L / S) * 3.6
        elif (L / R) * 3.6 <= vj:  # 次の信号に合わせると遅すぎるから法定速度で走る
            v = vj
        else:  # 次の青に合わせようとすると法定速度守れないから、次の青のビタに合わせる
            if S + C > 0.1:  # ゼロ除算防止
                v = (L / (S + C)) * 3.6
            else:
                v = vj  # フォールバック
        
        # 計算結果の妥当性チェック
        if v <= 0 or v > 100:  # 0以下または100km/h超過の場合
            if self.verbose:
                print(f"⚠️ 計算速度異常 (V:{v:.1f}km/h) → 法定速度{vj}km/h使用")
            v = vj
        
        return v
    
    def get_signal_timing_with_speed_control(self, vehicle_id: str, current_edge_id: int, av_penetration: float) -> tuple:
        """
        AV車が現在の道路から完全な信号タイミング情報を取得し、最適速度を車両に適用
        
        Returns:
            tuple: (S, R, L, G, V, current_speed)
            - S: 青信号までの時間（秒）
            - R: 赤信号までの時間（秒）
            - L: レーン（エッジ）の長さ（メートル）
            - G: 青信号の設定時間（秒）
            - V: 計算された最適速度（km/h）
            - current_speed: 制御前の現在速度（km/h）
        """
        # 現在の道路に対応する信号機IDを取得
        signal_id = self.get_signal_id_for_road(current_edge_id)
        
        if not signal_id:
            return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0  # 対応する信号機が見つからない場合
        
        # 進行方向に対応する信号インデックスを取得
        signal_index = self.get_signal_direction_index(signal_id, current_edge_id)
        
        # 青信号までの時間を計算（S）
        S = self.calculate_time_to_green(signal_id, signal_index)
        
        # 赤信号までの時間を計算（R）
        R = self.calculate_time_to_red(signal_id, signal_index)
        
        # レーンの長さを取得（L）
        L = self.get_lane_length(vehicle_id)
        
        # 青信号の設定時間を取得（G）
        G = self.get_green_phase_duration(signal_id, signal_index)
        
        # 現在の車両速度を取得（制御前）
        try:
            current_speed_ms = traci.vehicle.getSpeed(vehicle_id)  # m/s
            current_speed_kmh = current_speed_ms * 3.6  # km/h
        except:
            current_speed_kmh = 0.0
        
        # 最適速度を計算（V）
        V = self.calculate_speed(L, av_penetration, S, R, G)
        
        # デバッグ: 普及率の値を確認（初回のみ表示）
        if not hasattr(self, '_penetration_debug_shown'):
            self._penetration_debug_shown = True
            if self.verbose:
                print(f"🔧 デバッグ: AV普及率P = {av_penetration:.3f} (速度計算で使用)")
        
        # 計算された速度を車両に適用
        try:
            optimal_speed_ms = V / 3.6  # km/h → m/s変換
            traci.vehicle.setSpeed(vehicle_id, optimal_speed_ms)
            
            if self.verbose:
                direction = "正方向" if current_edge_id > 0 else "逆方向"
                print(f"🚙 AV速度制御: {vehicle_id} 道路{current_edge_id}({direction}) → {current_speed_kmh:.1f}→{V:.1f}km/h (S:{S:.1f}s, R:{R:.1f}s, L:{L:.1f}m, G:{G:.1f}s)")
                
        except Exception as e:
            if self.verbose:
                print(f"⚠️ 車両{vehicle_id}の速度制御エラー: {e}")
        
        return S, R, L, G, V, current_speed_kmh
    
    def get_signal_timing_full(self, vehicle_id: str, current_edge_id: int) -> tuple:
        """
        AV車が現在の道路から完全な信号タイミング情報を取得（速度制御なし）
        
        Returns:
            tuple: (S, R, L, G)
        """
        # 現在の道路に対応する信号機IDを取得
        signal_id = self.get_signal_id_for_road(current_edge_id)
        
        if not signal_id:
            return 0.0, 0.0, 0.0, 0.0  # 対応する信号機が見つからない場合
        
        # 進行方向に対応する信号インデックスを取得
        signal_index = self.get_signal_direction_index(signal_id, current_edge_id)
        
        # 青信号までの時間を計算（S）
        S = self.calculate_time_to_green(signal_id, signal_index)
        
        # 赤信号までの時間を計算（R）
        R = self.calculate_time_to_red(signal_id, signal_index)
        
        # レーンの長さを取得（L） 
        L = self.get_lane_length(vehicle_id)
        
        # 青信号の設定時間を取得（G）
        G = self.get_green_phase_duration(signal_id, signal_index)
        
        if self.verbose:
            direction = "正方向" if current_edge_id > 0 else "逆方向"
            print(f"🤖 AV完全予測: 道路{current_edge_id}({direction}) → 信号機'{signal_id}' → S:{S:.1f}s, R:{R:.1f}s, L:{L:.1f}m, G:{G:.1f}s")
        
        return S, R, L, G
    
    def get_signal_timing(self, vehicle_id: str, current_edge_id: int) -> tuple:
        """下位互換のためのメソッド（SとRのみを返す）"""
        S, R, L, G = self.get_signal_timing_full(vehicle_id, current_edge_id)
        return S, R
    
    def get_time_to_green_signal(self, vehicle_id: str, current_edge_id: int) -> float:
        """下位互換のためのメソッド（Sのみを返す）"""
        S, R = self.get_signal_timing(vehicle_id, current_edge_id)
        return S

class IntegratedMonitor:
    """
    CO2排出量と停止回数を同時に監視し、車両数を動的制御するクラス
    + AV車信号予測機能
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
        
        # ===== AV信号予測関連（新機能） =====
        if AV_SIGNAL_ENABLED:
            self.signal_predictor = AVSignalPredictor()
            self.av_signal_predictions = []  # AV信号予測ログ
            self.av_vehicles_tracked = set()  # 追跡済みAV車両
            self.target_road_edges = getattr(AVSignalConfig, 'TARGET_ROAD_EDGES', [])
            print("✅ AV信号予測機能が有効です")
        else:
            self.signal_predictor = None
            self.av_signal_predictions = []
            self.av_vehicles_tracked = set()
            self.target_road_edges = []
        
        # ===== シミュレーション管理 =====
        self.step_count = 0
        self.start_time = time.time()
        self.start_datetime = datetime.now()
        self.total_vehicles_seen = set()
        self.max_simultaneous_vehicles = 0
        
        if DebugConfig.VERBOSE_MODE:
            av_status = "有効" if AV_SIGNAL_ENABLED else "無効"
            print(f"✅ 統合監視システム初期化完了（AV信号予測: {av_status}）")
    
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
    
    def update_av_signal_monitoring(self, current_time):
        """AV車の信号予測監視を更新（新機能）"""
        if not AV_SIGNAL_ENABLED or not self.signal_predictor:
            return
            
        current_vehicles = set(traci.vehicle.getIDList())
        
        for vehicle_id in current_vehicles:
            # AV車のみを対象
            if vehicle_id in self.vehicle_types and \
               self.vehicle_types[vehicle_id] == VehicleConfig.AUTONOMOUS_CAR_TYPE:
                
                try:
                    # 現在の道路IDを取得
                    current_edge = traci.vehicle.getRoadID(vehicle_id)
                    
                    # 対象道路かチェック
                    if current_edge in self.target_road_edges:
                        # まだ予測していない車両
                        tracking_key = f"{vehicle_id}_{current_edge}"
                        
                        if tracking_key not in self.av_vehicles_tracked:
                            # 道路IDを数値に変換
                            try:
                                edge_num = int(current_edge)
                                
                                # 信号予測と速度制御を実行（S, R, L, G, V, current_speed を取得）
                                S, R, L, G, V, current_speed = self.signal_predictor.get_signal_timing_with_speed_control(
                                    vehicle_id, edge_num, self.target_av_penetration
                                )
                                
                                # 対応する信号機IDを取得
                                signal_id = self.signal_predictor.get_signal_id_for_road(edge_num)
                                
                                # ログに記録
                                prediction_record = {
                                    'time': current_time,
                                    'vehicle_id': vehicle_id,
                                    'current_edge': current_edge,
                                    'signal_id': signal_id if signal_id else 'unknown',
                                    'time_to_green': S,
                                    'time_to_red': R,
                                    'lane_length': L,
                                    'green_duration': G,
                                    'optimal_speed': V,
                                    'previous_speed': current_speed,
                                    'speed_change': V - current_speed,
                                    'current_speed_ms': traci.vehicle.getSpeed(vehicle_id)
                                }
                                
                                self.av_signal_predictions.append(prediction_record)
                                self.av_vehicles_tracked.add(tracking_key)
                                
                                # リアルタイム表示
                                if hasattr(AVSignalConfig, 'SHOW_REAL_TIME_PREDICTIONS') and \
                                   AVSignalConfig.SHOW_REAL_TIME_PREDICTIONS:
                                    direction = "正方向" if edge_num > 0 else "逆方向"
                                    signal_display = signal_id if signal_id else 'unknown'
                                    speed_change_display = f"({current_speed:.1f}→{V:.1f}km/h)" if V != current_speed else f"({V:.1f}km/h維持)"
                                    print(f"🚙 AV制御: {vehicle_id} 道路{current_edge}({direction}) → {speed_change_display} S:{S:.1f}s R:{R:.1f}s")
                                
                            except ValueError:
                                # 数値変換失敗（対象外道路）
                                continue
                                
                except traci.TraCIException:
                    # 車両が削除された可能性
                    continue
        
        # 削除された車両の追跡状態をクリア
        vehicles_to_remove = []
        for tracking_key in self.av_vehicles_tracked:
            vehicle_id = tracking_key.split('_')[0]
            if vehicle_id not in current_vehicles:
                vehicles_to_remove.append(tracking_key)
        
        for tracking_key in vehicles_to_remove:
            self.av_vehicles_tracked.remove(tracking_key)
    
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
        
        # AV信号監視対象エッジの確認
        if AV_SIGNAL_ENABLED and self.target_road_edges:
            valid_signal_edges = [edge for edge in self.target_road_edges if edge in all_edges]
            print(f"✅ AV信号監視対象道路: {len(valid_signal_edges)}/{len(self.target_road_edges)} 個")
        
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
        
        # AV予測表示
        av_prediction_status = ""
        if AV_SIGNAL_ENABLED:
            av_predictions_count = len(self.av_signal_predictions)
            av_prediction_status = f" | 🤖 AV予測: {av_predictions_count:3d}回"
        
        print(f"\r⏰ 時刻: {current_time:6.0f}s | "
              f"🚗 車両: {total_vehicles:3d}{control_status} | "
              f"🔴 ガソリン車: {gasoline_count:3d} | "
              f"🟢 AV車: {av_count:3d} | "
              f"💨 CO2: {self.gasoline_co2:8.{OutputConfig.CO2_DECIMAL_PLACES}f}g | "
              f"🛑 停止: {total_stops:4d}回{av_prediction_status}", end="")
    
    def save_results(self):
        """結果保存"""
        if DebugConfig.VERBOSE_MODE:
            print("\n\n🔄 結果保存中...")
        
        print("\n\n" + OutputConfig.REPORT_SEPARATOR)
        av_status = "AV信号予測機能付き" if AV_SIGNAL_ENABLED else "動的制御対応版"
        print(f"           🎯 統合監視結果（{av_status}）")
        print(OutputConfig.REPORT_SEPARATOR)
        
        # 各種結果を保存
        self.save_co2_csv()
        self.save_co2_report()
        self.save_stop_results()
        self.save_stop_csv()
        
        # AV信号予測結果を保存（新機能）
        if AV_SIGNAL_ENABLED and self.av_signal_predictions:
            self.save_av_signal_results()
            self.save_av_signal_csv()
        
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
        
        # AV信号予測統計（新機能）
        av_signal_info = ""
        if AV_SIGNAL_ENABLED and self.av_signal_predictions:
            avg_time_to_green = sum(p['time_to_green'] for p in self.av_signal_predictions) / len(self.av_signal_predictions)
            avg_time_to_red = sum(p['time_to_red'] for p in self.av_signal_predictions) / len(self.av_signal_predictions)
            avg_lane_length = sum(p['lane_length'] for p in self.av_signal_predictions) / len(self.av_signal_predictions)
            avg_green_duration = sum(p['green_duration'] for p in self.av_signal_predictions) / len(self.av_signal_predictions)
            av_signal_info = f"""
🤖 AV信号予測統計:
   総予測回数: {len(self.av_signal_predictions)}
   監視対象道路: {len(self.target_road_edges)}個
   平均S(青まで): {avg_time_to_green:.1f}秒
   平均R(赤まで): {avg_time_to_red:.1f}秒
   平均L(レーン長): {avg_lane_length:.1f}メートル
   平均G(青時間): {avg_green_duration:.1f}秒
   追跡済み車両-道路組合せ: {len(self.av_vehicles_tracked)}
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
{control_info}{av_signal_info}
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
        
        # AV信号予測統計（新機能）
        av_signal_info = ""
        if AV_SIGNAL_ENABLED and self.av_signal_predictions:
            avg_time_to_green = sum(p['time_to_green'] for p in self.av_signal_predictions) / len(self.av_signal_predictions)
            avg_time_to_red = sum(p['time_to_red'] for p in self.av_signal_predictions) / len(self.av_signal_predictions)
            avg_lane_length = sum(p['lane_length'] for p in self.av_signal_predictions) / len(self.av_signal_predictions)
            avg_green_duration = sum(p['green_duration'] for p in self.av_signal_predictions) / len(self.av_signal_predictions)
            av_signal_info = f"""
AV信号予測統計:
- 総予測回数: {len(self.av_signal_predictions)}
- 監視対象道路: {len(self.target_road_edges)}個
- 平均S(青まで): {avg_time_to_green:.1f}秒
- 平均R(赤まで): {avg_time_to_red:.1f}秒
- 平均L(レーン長): {avg_lane_length:.1f}メートル
- 平均G(青時間): {avg_green_duration:.1f}秒

"""
        
        result_content = f"""停止回数カウント結果（統合監視・動的制御対応版）

実行時刻: {self.start_datetime.strftime('%Y-%m-%d %H:%M:%S')} - {datetime.now().strftime('%H:%M:%S')}
実行時間: {execution_time:.{OutputConfig.TIME_DECIMAL_PLACES}f} 秒
シミュレーション時間: {self.step_count} ステップ

車両統計:
- 累積車両数: {len(self.total_vehicles_seen)} 台
- 最大同時車両数: {self.max_simultaneous_vehicles} 台

{control_info}{av_signal_info}停止分析結果:
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
    
    def save_av_signal_results(self):
        """AV信号予測結果保存（新機能）"""
        if not self.av_signal_predictions:
            return
        
        # 統計計算
        total_predictions = len(self.av_signal_predictions)
        avg_time_to_green = sum(p['time_to_green'] for p in self.av_signal_predictions) / total_predictions
        avg_time_to_red = sum(p['time_to_red'] for p in self.av_signal_predictions) / total_predictions
        avg_lane_length = sum(p['lane_length'] for p in self.av_signal_predictions) / total_predictions
        avg_green_duration = sum(p['green_duration'] for p in self.av_signal_predictions) / total_predictions
        avg_optimal_speed = sum(p['optimal_speed'] for p in self.av_signal_predictions) / total_predictions
        avg_speed_change = sum(abs(p['speed_change']) for p in self.av_signal_predictions) / total_predictions
        
        max_time_to_green = max(p['time_to_green'] for p in self.av_signal_predictions)
        min_time_to_green = min(p['time_to_green'] for p in self.av_signal_predictions)
        max_time_to_red = max(p['time_to_red'] for p in self.av_signal_predictions)
        min_time_to_red = min(p['time_to_red'] for p in self.av_signal_predictions)
        max_lane_length = max(p['lane_length'] for p in self.av_signal_predictions)
        min_lane_length = min(p['lane_length'] for p in self.av_signal_predictions)
        
        # 道路別統計
        edge_stats = defaultdict(lambda: {
            'green_times': [], 'red_times': [], 'lane_lengths': [], 
            'green_durations': [], 'optimal_speeds': [], 'speed_changes': []
        })
        for pred in self.av_signal_predictions:
            edge_stats[pred['current_edge']]['green_times'].append(pred['time_to_green'])
            edge_stats[pred['current_edge']]['red_times'].append(pred['time_to_red'])
            edge_stats[pred['current_edge']]['lane_lengths'].append(pred['lane_length'])
            edge_stats[pred['current_edge']]['green_durations'].append(pred['green_duration'])
            edge_stats[pred['current_edge']]['optimal_speeds'].append(pred['optimal_speed'])
            edge_stats[pred['current_edge']]['speed_changes'].append(abs(pred['speed_change']))
        
        result_content = f"""AV信号予測・速度制御結果（統合監視システム）

実行時刻: {self.start_datetime.strftime('%Y-%m-%d %H:%M:%S')} - {datetime.now().strftime('%H:%M:%S')}
実行時間: {time.time() - self.start_time:.{OutputConfig.TIME_DECIMAL_PLACES}f} 秒

AV信号予測・速度制御統計:
- 総制御回数: {total_predictions} 回
- 平均青信号待ち時間(S): {avg_time_to_green:.1f} 秒
- 平均赤信号待ち時間(R): {avg_time_to_red:.1f} 秒
- 平均レーン長(L): {avg_lane_length:.1f} メートル
- 平均青信号時間(G): {avg_green_duration:.1f} 秒
- 平均最適速度(V): {avg_optimal_speed:.1f} km/h
- 平均速度変化: {avg_speed_change:.1f} km/h
- 最大青信号待ち時間: {max_time_to_green:.1f} 秒
- 最小青信号待ち時間: {min_time_to_green:.1f} 秒  
- 最大赤信号待ち時間: {max_time_to_red:.1f} 秒
- 最小赤信号待ち時間: {min_time_to_red:.1f} 秒
- 最大レーン長: {max_lane_length:.1f} メートル
- 最小レーン長: {min_lane_length:.1f} メートル
- 監視対象道路数: {len(self.target_road_edges)} 個
- AV普及率: {self.target_av_penetration:.1%}

道路別制御統計:
"""
        
        for edge_id in sorted(edge_stats.keys()):
            green_times = edge_stats[edge_id]['green_times']
            red_times = edge_stats[edge_id]['red_times']
            lane_lengths = edge_stats[edge_id]['lane_lengths']
            green_durations = edge_stats[edge_id]['green_durations']
            optimal_speeds = edge_stats[edge_id]['optimal_speeds']
            speed_changes = edge_stats[edge_id]['speed_changes']
            
            avg_green = sum(green_times) / len(green_times)
            avg_red = sum(red_times) / len(red_times)
            avg_lane = sum(lane_lengths) / len(lane_lengths)
            avg_g_duration = sum(green_durations) / len(green_durations)
            avg_opt_speed = sum(optimal_speeds) / len(optimal_speeds)
            avg_speed_change = sum(speed_changes) / len(speed_changes)
            
            result_content += f"道路{edge_id}: {len(green_times)}回制御, S={avg_green:.1f}s, V={avg_opt_speed:.1f}km/h, 速度変化={avg_speed_change:.1f}km/h\n"
        
        # ファイル保存
        if hasattr(PathConfig, 'AV_SIGNAL_RESULTS_TXT'):
            result_path = os.path.join(self.log_dir, PathConfig.AV_SIGNAL_RESULTS_TXT)
        else:
            result_path = os.path.join(self.log_dir, "av_signal_results.txt")
            
        try:
            with open(result_path, "w", encoding=OutputConfig.REPORT_ENCODING) as f:
                f.write(result_content)
            print(f"🤖 AV信号予測結果を{result_path}に保存")
        except Exception as e:
            print(f"⚠️ AV信号予測結果保存エラー: {e}")
    
    def save_av_signal_csv(self):
        """AV信号予測データをCSVで保存（新機能）"""
        if self.av_signal_predictions:
            try:
                if hasattr(PathConfig, 'AV_SIGNAL_PREDICTIONS_CSV'):
                    csv_path = os.path.join(self.log_dir, PathConfig.AV_SIGNAL_PREDICTIONS_CSV)
                else:
                    csv_path = os.path.join(self.log_dir, "av_signal_predictions.csv")
                    
                with open(csv_path, 'w', newline=OutputConfig.CSV_NEWLINE, 
                         encoding=OutputConfig.CSV_ENCODING) as f:
                    writer = csv.DictWriter(f, fieldnames=[
                        'time', 'vehicle_id', 'current_edge', 'signal_id', 
                        'time_to_green', 'time_to_red', 'lane_length', 'green_duration', 
                        'optimal_speed', 'previous_speed', 'speed_change', 'current_speed_ms'
                    ])
                    writer.writeheader()
                    writer.writerows(self.av_signal_predictions)
                print(f"🤖 AV信号予測データを{csv_path}に保存")
            except Exception as e:
                print(f"⚠️ AV信号予測CSV保存エラー: {e}")
    
    def print_integrated_summary(self):
        """統合サマリー表示（簡潔版）"""
        total_stops = sum(self.stop_counts.values())
        
        print("🎯 統合監視結果:")
        print(f"   💨 総CO2排出量: {self.total_co2:.{OutputConfig.CO2_DECIMAL_PLACES}f} g")
        print(f"   🛑 総停止回数: {total_stops} 回")

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
    """メイン実行関数（動的制御対応版 + AV信号予測機能）"""
    parser = argparse.ArgumentParser(description='統合監視システム（CO2+停止回数+動的車両制御+AV信号予測）')
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
    feature_list = "CO2排出量測定 + 停止回数カウント + 動的車両制御"
    if AV_SIGNAL_ENABLED:
        feature_list += " + AV信号先読み予測"
    print(f"【同時実行】{feature_list}")
    
    if args.vehicles > 0:
        print(f"【車両制御】目標{args.vehicles}台, AV普及率{args.av_penetration}%")
    else:
        print("【車両制御】無効（既存車両のみ監視）")
    
    if AV_SIGNAL_ENABLED:
        print("【AV信号予測】対象道路でのAV車信号先読み機能有効")
    
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
        last_av_check_time = 0
        
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
            
            # AV信号予測監視更新（新機能）
            if AV_SIGNAL_ENABLED:
                av_check_interval = getattr(AVSignalConfig, 'CHECK_INTERVAL', 1.0)
                if current_time - last_av_check_time >= av_check_interval:
                    monitor.update_av_signal_monitoring(current_time)
                    last_av_check_time = current_time
            
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