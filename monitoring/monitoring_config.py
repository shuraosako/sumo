#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#monitoring_config.py
"""
統合監視システム設定ファイル（AV信号予測機能追加版）
全ての設定値、定数、パラメータをここで管理
"""

import os
TARGET_EDGES = [
    "1","2","3","4","5","6","7","8","9","10","11","12",
    "-1","-2","-3","-4","-5","-6","-7","-8","-9","-10","-11","-12",
]
# =============================================================================
# ファイル・ディレクトリ設定
# =============================================================================

class PathConfig:
    """ファイルパス設定"""
    # ログ出力ディレクトリ（monitoring/フォルダから相対パス）
    LOG_DIR = os.path.join("..", "data", "log")
    
    # SUMOファイル（monitoring/フォルダから相対パス）
    DEFAULT_SUMO_CONFIG = os.path.join("..", "config", "mixed_traffic.sumocfg")
    DEFAULT_NETWORK_FILE = os.path.join("..", "config", "3gousen_new.net.xml")
    
    # 出力ファイル名
    CO2_EMISSION_LOG_CSV = "co2_emission_log.csv"
    CO2_EMISSION_REPORT_TXT = "co2_emission_report.txt"
    STOP_COUNT_RESULTS_TXT = "stop_count_results.txt"
    STOP_COUNT_DETAILED_CSV = "stop_count_detailed.csv"
    INTEGRATED_RESULTS_CSV = "integrated_results.csv"
    
    # AV信号予測関連出力ファイル（新規追加）
    AV_SIGNAL_RESULTS_TXT = "av_signal_results.txt"
    AV_SIGNAL_PREDICTIONS_CSV = "av_signal_predictions.csv"

# =============================================================================
# 車両設定
# =============================================================================

class VehicleConfig:
    """車両関連設定"""
    # 車両タイプ定義
    GASOLINE_CAR_TYPE = "gasoline_car"
    AUTONOMOUS_CAR_TYPE = "autonomous_car"
    
    # 車両タイプ一覧
    VEHICLE_TYPES = [GASOLINE_CAR_TYPE, AUTONOMOUS_CAR_TYPE]
    
    # 車両生成設定
    DEFAULT_TOTAL_VEHICLES = 100
    DEFAULT_AV_PENETRATION = 0.5  # 50%
    
    # 動的車両制御（traffic_controller用）
    MAX_VEHICLES_PER_STEP = 5  # 一度に追加する最大車両数
    STOP_GENERATION_BEFORE_END = 60  # 終了X秒前に車両生成停止

# =============================================================================
# CO2監視設定
# =============================================================================

class CO2MonitoringConfig:
    """CO2排出量監視設定"""
    # 測定単位変換
    MG_TO_G_CONVERSION = 1000.0  # mg → g 変換
    
    # レポート設定
    REPORT_INTERVAL_STEPS = 10  # X ステップごとに状況表示

# =============================================================================
# 停止回数監視設定
# =============================================================================

class StopMonitoringConfig:
    """停止回数監視設定"""
    # 停止判定パラメータ
    STOP_SPEED_THRESHOLD = 0.1  # m/s - この速度以下で停止と判定
    MIN_STOP_DURATION = 1.0     # 秒 - この時間以上停止で カウント
    CHECK_INTERVAL = 1.0        # 秒 - チェック間隔
    
    # 監視対象エッジID一覧
    TARGET_EDGES = [
        "1","2","3","4","5","6","7","8","9","10","11","12",
        "-1","-2","-3","-4","-5","-6","-7","-8","-9","-10","-11","-12",
    ]
    
    # 停止回数表示設定
    MAX_STOP_EVENTS_TO_PRINT = 3  # リアルタイムで表示する停止イベント数
    TOP_EDGES_TO_DISPLAY = 5      # サマリーで表示する上位エッジ数

# =============================================================================
# AV信号予測設定（新規追加）
# =============================================================================

class AVSignalConfig:
    """AV車信号予測機能の設定"""
    
    # 監視対象道路ID（文字列形式）
    TARGET_ROAD_EDGES = [
        "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12",
        "-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9", "-10", "-11", "-12"
    ]
    
    # 監視間隔設定
    CHECK_INTERVAL = 1.0                # AV信号予測チェック間隔 (秒)
    
    # 表示設定
    SHOW_REAL_TIME_PREDICTIONS = True   # リアルタイム予測結果表示
    MAX_PREDICTIONS_TO_PRINT = 10       # リアルタイム表示する予測数
    
    # 信号予測設定
    SIGNAL_DIRECTION_CACHE_SIZE = 100   # 信号方向キャッシュサイズ
    DEFAULT_POSITIVE_SIGNAL_INDEX = 0   # 正方向のデフォルト信号インデックス
    DEFAULT_NEGATIVE_SIGNAL_INDEX = 2   # 逆方向のデフォルト信号インデックス
    
    # 予測精度設定
    TIME_PRECISION = 1                  # 時間予測精度（小数点以下桁数）
    
    # 道路ネットワーク設定（J1〜J13の構造）
    MAX_JUNCTION_INDEX = 13             # 最大交差点番号
    MIN_JUNCTION_INDEX = 1              # 最小交差点番号

# =============================================================================
# シミュレーション制御設定
# =============================================================================

class SimulationConfig:
    """シミュレーション制御設定"""
    # デフォルト実行時間
    DEFAULT_END_TIME = 1000  # 秒
    DEFAULT_STEP_LENGTH = 1.0  # ステップ長（秒）
    
    # SUMOコマンド設定
    SUMO_BINARY = "sumo"
    SUMO_GUI_BINARY = "sumo-gui"
    SUMO_CMD_OPTIONS = ["--start", "--no-warnings", "--time-to-teleport", "-1"]
    
    # 表示・ログ設定
    STATUS_DISPLAY_INTERVAL = 10  # 秒ごとに状況表示
    PROGRESS_DISPLAY_INTERVAL = 200  # ステップごとに進捗表示

# =============================================================================
# レポート設定
# =============================================================================

class ReportConfig:
    """レポート関連設定"""
    # レポートタイトル
    SYSTEM_NAME = "統合監視システム"
    VERSION = "v2.4"  # AV信号予測+速度制御機能追加でバージョンアップ
    
    # AV信号予測レポート設定（新規追加）
    INCLUDE_AV_SIGNAL_STATS = True      # AV信号統計を含める
    INCLUDE_ROAD_WISE_ANALYSIS = True   # 道路別分析を含める

# =============================================================================
# エラーハンドリング・デバッグ設定
# =============================================================================

class DebugConfig:
    """デバッグ・エラーハンドリング設定"""
    # ログレベル
    VERBOSE_MODE = True  # 詳細ログ出力
    DEBUG_MODE = False   # デバッグモード
    
    # エラー処理
    MAX_RETRIES = 3             # 最大リトライ回数
    CONTINUE_ON_MINOR_ERRORS = True  # 軽微なエラーでも継続
    
    # 車両生成エラー処理
    MAX_VEHICLE_ADD_ATTEMPTS = 10  # 車両追加の最大試行回数
    SKIP_INVALID_VEHICLES = True   # 無効車両をスキップ
    
    # AV信号予測デバッグ設定（新規追加）
    LOG_AV_SIGNAL_DETAILS = True    # AV信号詳細ログ
    LOG_SIGNAL_PREDICTION_ERRORS = True  # 信号予測エラーログ

# =============================================================================
# 出力フォーマット設定
# =============================================================================

class OutputConfig:
    """出力フォーマット設定"""
    # CSVファイル設定
    CSV_ENCODING = 'utf-8'
    CSV_NEWLINE = ''
    
    # レポート設定
    REPORT_ENCODING = 'utf-8'
    REPORT_SEPARATOR = "=" * 70
    SECTION_SEPARATOR = "-" * 70
    
    # 数値フォーマット
    CO2_DECIMAL_PLACES = 2      # CO2排出量の小数点以下桁数
    PERCENTAGE_DECIMAL_PLACES = 1  # パーセンテージの小数点以下桁数
    TIME_DECIMAL_PLACES = 1     # 時間の小数点以下桁数
    
    # AV信号予測表示設定（新規追加）
    AV_SIGNAL_TIME_FORMAT = "{:.1f}"    # AV信号時間表示フォーマット
    AV_SIGNAL_SUMMARY_TOP_N = 10        # サマリー表示上位N件

# =============================================================================
# ヘルパー関数
# =============================================================================

def validate_config():
    """設定値の妥当性をチェック"""
    errors = []
    
    # 停止監視設定チェック
    if StopMonitoringConfig.STOP_SPEED_THRESHOLD < 0:
        errors.append("停止速度閾値は0以上である必要があります")
    
    if StopMonitoringConfig.MIN_STOP_DURATION <= 0:
        errors.append("最小停止時間は0より大きい必要があります")
    
    # エッジリストチェック
    if not StopMonitoringConfig.TARGET_EDGES:
        errors.append("監視対象エッジが設定されていません")
    
    # 車両設定チェック
    if not (0 <= VehicleConfig.DEFAULT_AV_PENETRATION <= 1):
        errors.append("AV普及率は0-1の範囲である必要があります")
    
    # AV信号予測設定チェック（新規追加）
    if AVSignalConfig.CHECK_INTERVAL <= 0:
        errors.append("AV信号予測チェック間隔は0より大きい必要があります")
    
    if not AVSignalConfig.TARGET_ROAD_EDGES:
        errors.append("AV信号予測対象道路が設定されていません")
    
    if AVSignalConfig.SIGNAL_DIRECTION_CACHE_SIZE <= 0:
        errors.append("信号方向キャッシュサイズは0より大きい必要があります")
    
    if not (1 <= AVSignalConfig.MIN_JUNCTION_INDEX <= AVSignalConfig.MAX_JUNCTION_INDEX):
        errors.append("交差点番号の範囲が不正です")
    
    return errors

def print_config_summary():
    """設定サマリーを表示"""
    print("=" * 50)
    print("      統合監視システム設定サマリー")
    print(f"             {ReportConfig.VERSION}")
    print("=" * 50)
    print(f"監視対象エッジ数: {len(StopMonitoringConfig.TARGET_EDGES)}")
    print(f"停止判定速度: {StopMonitoringConfig.STOP_SPEED_THRESHOLD} m/s")
    print(f"停止時間閾値: {StopMonitoringConfig.MIN_STOP_DURATION} 秒")
    print(f"デフォルト車両数: {VehicleConfig.DEFAULT_TOTAL_VEHICLES}")
    print(f"デフォルトAV普及率: {VehicleConfig.DEFAULT_AV_PENETRATION*100:.1f}%")
    print(f"ログ出力先: {PathConfig.LOG_DIR}")
    print()
    print("🤖 AV信号予測設定:")
    print(f"監視対象道路数: {len(AVSignalConfig.TARGET_ROAD_EDGES)}")
    print(f"予測チェック間隔: {AVSignalConfig.CHECK_INTERVAL} 秒")
    print(f"リアルタイム表示: {'有効' if AVSignalConfig.SHOW_REAL_TIME_PREDICTIONS else '無効'}")
    print(f"交差点範囲: J{AVSignalConfig.MIN_JUNCTION_INDEX}〜J{AVSignalConfig.MAX_JUNCTION_INDEX}")
    print("=" * 50)

# =============================================================================
# 設定値検証（モジュール読み込み時に実行）
# =============================================================================

if __name__ == "__main__":
    # 設定値チェック
    config_errors = validate_config()
    if config_errors:
        print("❌ 設定エラーが検出されました:")
        for error in config_errors:
            print(f"   - {error}")
    else:
        print("✅ 設定値は正常です")
        print_config_summary()