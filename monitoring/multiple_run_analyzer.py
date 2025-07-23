#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
交通シミュレーション複数回実行・統計分析システム
同一パラメータで複数回実行し、結果を統計分析

使用方法:
    python multiple_run_analyzer.py --vehicles 100 --av-penetration 50 --runs 3
    python multiple_run_analyzer.py --vehicles 50 --av-penetration 30 --runs 5
"""

import os
import sys
import subprocess
import argparse
import time
import re
import csv
import statistics
from datetime import datetime
from pathlib import Path

class MultipleRunAnalyzer:
    """複数回実行・統計分析クラス"""
    
    def __init__(self, vehicles, av_penetration, num_runs):
        """
        初期化
        
        Args:
            vehicles (int): 総車両数
            av_penetration (float): AV普及率 (%)
            num_runs (int): 実行回数
        """
        self.vehicles = vehicles
        self.av_penetration = av_penetration
        self.num_runs = num_runs
        
        # パス設定
        self.monitoring_dir = Path(".")  # monitoring/ フォルダから実行想定
        self.log_dir = Path("..") / "data" / "log"
        self.integrated_monitor_script = Path("integrated_monitor.py")
        self.config_file = Path("..") / "config" / "mixed_traffic.sumocfg"
        
        # 結果格納
        self.results = []
        self.start_time = datetime.now()
        
        print(f"🔄 複数回実行分析システム初期化")
        print(f"📊 パラメータ: 車両数{vehicles}台, AV普及率{av_penetration}%")
        print(f"🔢 実行回数: {num_runs}回")
        print(f"🎲 ランダムシード: 自動変更")
        
    def ensure_directories(self):
        """必要なディレクトリの存在確認"""
        if not self.log_dir.exists():
            self.log_dir.mkdir(parents=True, exist_ok=True)
            print(f"📁 ログディレクトリ作成: {self.log_dir}")
        
        if not self.integrated_monitor_script.exists():
            print(f"❌ {self.integrated_monitor_script} が見つかりません")
            return False
            
        if not self.config_file.exists():
            print(f"❌ {self.config_file} が見つかりません")
            return False
            
        return True
    
    def run_single_simulation(self, run_number):
        """
        単一シミュレーション実行
        
        Args:
            run_number (int): 実行回数
            
        Returns:
            tuple: (総停止回数, ガソリン車CO2排出量, 実行時間) または None
        """
        print(f"\n🚀 {run_number}回目実行開始...")
        
        # コマンド構築
        cmd = [
            "python", str(self.integrated_monitor_script),
            "--config", str(self.config_file),
            "--vehicles", str(self.vehicles),
            "--av-penetration", str(self.av_penetration)
        ]
        
        # デバッグ：実行コマンド表示
        print(f"🔧 実行コマンド: {' '.join(cmd)}")
        
        start_time = time.time()
        
        try:
            # Windows環境での絵文字エラー対策：環境変数設定
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            
            # 実行
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',   # エンコーディングエラーを置換
                timeout=300,  # 5分タイムアウト
                env=env  # 環境変数を渡す
            )
            
            execution_time = time.time() - start_time
            
            # 実行結果の判定：エラーコードだけでなくファイル生成も確認
            stop_count, co2_emission = self.parse_results()
            
            if result.returncode != 0:
                print(f"⚠️ {run_number}回目プロセスエラー（戻り値: {result.returncode}）")
                # ただし、結果ファイルが生成されていれば成功とみなす
                if stop_count is not None and co2_emission is not None:
                    print(f"✅ {run_number}回目結果取得成功: 停止{stop_count}回, CO2={co2_emission:.1f}g, 時間{execution_time:.1f}s")
                    return stop_count, co2_emission, execution_time
                else:
                    stdout_msg = result.stdout[-200:] if result.stdout else "出力なし"
                    stderr_msg = result.stderr[-200:] if result.stderr else "エラー出力なし"
                    print(f"   stdout: {stdout_msg}")
                    print(f"   stderr: {stderr_msg}")
                    return None
            else:
                # 正常終了
                if stop_count is not None and co2_emission is not None:
                    print(f"✅ {run_number}回目完了: 停止{stop_count}回, CO2={co2_emission:.1f}g, 時間{execution_time:.1f}s")
                    return stop_count, co2_emission, execution_time
                else:
                    print(f"⚠️ {run_number}回目結果解析失敗")
                    return None
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {run_number}回目タイムアウト（5分超過）")
            return None
        except Exception as e:
            print(f"❌ {run_number}回目実行エラー: {e}")
            return None
    
    def parse_results(self):
        """
        結果ファイルから数値を抽出
        
        Returns:
            tuple: (総停止回数, ガソリン車CO2排出量) または (None, None)
        """
        stop_count = None
        co2_emission = None
        
        # ファイル存在確認とデバッグ情報
        stop_file = self.log_dir / "stop_count_results.txt"
        co2_file = self.log_dir / "co2_emission_report.txt"
        csv_file = self.log_dir / "co2_emission_log.csv"
        
        print(f"🔍 ファイル確認: 停止={stop_file.exists()}, CO2={co2_file.exists()}, CSV={csv_file.exists()}")
        
        # 停止回数を解析
        if stop_file.exists():
            try:
                with open(stop_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # "総停止回数: XXX 回" を検索
                    match = re.search(r'総停止回数:\s*(\d+)\s*回', content)
                    if match:
                        stop_count = int(match.group(1))
                        print(f"✅ 停止回数抽出成功: {stop_count}回")
                    else:
                        print("⚠️ 停止回数パターンが見つかりません")
            except Exception as e:
                print(f"⚠️ 停止回数解析エラー: {e}")
        
        # CO2排出量を解析
        if co2_file.exists():
            try:
                with open(co2_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # "🔴 ガソリン車総排出量: XXX.XX g" を検索
                    match = re.search(r'ガソリン車総排出量:\s*([\d.]+)\s*g', content)
                    if match:
                        co2_emission = float(match.group(1))
                        print(f"✅ CO2排出量抽出成功: {co2_emission:.1f}g")
                    else:
                        print("⚠️ CO2排出量パターンが見つかりません")
            except Exception as e:
                print(f"⚠️ CO2排出量解析エラー: {e}")
        
        # CSV からの代替解析（メインファイルが失敗した場合）
        if co2_emission is None and csv_file.exists():
            try:
                with open(csv_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if rows:
                        # 最終行の累積ガソリン車CO2
                        last_row = rows[-1]
                        co2_emission = float(last_row['total_gasoline'])
                        print(f"✅ CSV からCO2排出量抽出: {co2_emission:.1f}g")
            except Exception as e:
                print(f"⚠️ CSV CO2解析エラー: {e}")
        
        return stop_count, co2_emission
    
    def run_multiple_simulations(self):
        """複数回シミュレーション実行"""
        print("\n" + "="*60)
        print("🔄 複数回シミュレーション実行開始")
        print("="*60)
        
        if not self.ensure_directories():
            return False
        
        # 各回実行
        for run_num in range(1, self.num_runs + 1):
            result = self.run_single_simulation(run_num)
            
            if result is not None:
                stop_count, co2_emission, exec_time = result
                self.results.append({
                    'run': run_num,
                    'stop_count': stop_count,
                    'co2_emission': co2_emission,
                    'execution_time': exec_time
                })
            else:
                print(f"⚠️ {run_num}回目の結果を記録できませんでした")
                # 失敗した回もNoneで記録
                self.results.append({
                    'run': run_num,
                    'stop_count': None,
                    'co2_emission': None,
                    'execution_time': None
                })
        
        print(f"\n✅ 全{self.num_runs}回実行完了 (成功: {len([r for r in self.results if r['stop_count'] is not None])}回)")
        return True
    
    def calculate_statistics(self):
        """統計計算"""
        # 成功したデータのみ抽出
        valid_results = [r for r in self.results if r['stop_count'] is not None]
        
        if not valid_results:
            return None
        
        stop_counts = [r['stop_count'] for r in valid_results]
        co2_emissions = [r['co2_emission'] for r in valid_results]
        exec_times = [r['execution_time'] for r in valid_results]
        
        stats = {
            'valid_runs': len(valid_results),
            'total_runs': self.num_runs,
            'stop_count': {
                'values': stop_counts,
                'mean': statistics.mean(stop_counts),
                'stdev': statistics.stdev(stop_counts) if len(stop_counts) > 1 else 0.0,
                'min': min(stop_counts),
                'max': max(stop_counts),
                'median': statistics.median(stop_counts)
            },
            'co2_emission': {
                'values': co2_emissions,
                'mean': statistics.mean(co2_emissions),
                'stdev': statistics.stdev(co2_emissions) if len(co2_emissions) > 1 else 0.0,
                'min': min(co2_emissions),
                'max': max(co2_emissions),
                'median': statistics.median(co2_emissions)
            },
            'execution_time': {
                'values': exec_times,
                'mean': statistics.mean(exec_times),
                'stdev': statistics.stdev(exec_times) if len(exec_times) > 1 else 0.0,
                'min': min(exec_times),
                'max': max(exec_times)
            }
        }
        
        return stats
    
    def save_results(self, stats):
        """結果保存"""
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        
        # 詳細ログファイル
        log_filename = f"multiple_run_analysis_{self.vehicles}v_{self.av_penetration}av_{self.num_runs}runs_{timestamp}.txt"
        log_path = self.log_dir / log_filename
        
        # CSV結果ファイル
        csv_filename = f"multiple_run_data_{self.vehicles}v_{self.av_penetration}av_{self.num_runs}runs_{timestamp}.csv"
        csv_path = self.log_dir / csv_filename
        
        # 詳細レポート作成
        total_analysis_time = (datetime.now() - self.start_time).total_seconds()
        
        report = f"""複数回実行統計分析結果

実行設定:
- 総車両数: {self.vehicles} 台
- AV普及率: {self.av_penetration}%
- 実行回数: {self.num_runs} 回
- 成功回数: {stats['valid_runs']} 回
- 失敗回数: {self.num_runs - stats['valid_runs']} 回

実行日時: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} - {datetime.now().strftime('%H:%M:%S')}
総解析時間: {total_analysis_time:.1f} 秒

{"="*60}
停止回数統計:
{"="*60}
"""
        
        # 個別結果表示
        for i, result in enumerate(self.results, 1):
            if result['stop_count'] is not None:
                report += f"{i:2d}回目: {result['stop_count']:3d} 回 (実行時間: {result['execution_time']:5.1f}s)\n"
            else:
                report += f"{i:2d}回目: --- 回 (実行失敗)\n"
        
        # 統計サマリー
        if stats['valid_runs'] > 0:
            report += f"""
統計サマリー:
- 平均値: {stats['stop_count']['mean']:6.1f} 回
- 標準偏差: {stats['stop_count']['stdev']:6.1f} 回
- 最小値: {stats['stop_count']['min']:6d} 回
- 最大値: {stats['stop_count']['max']:6d} 回
- 中央値: {stats['stop_count']['median']:6.1f} 回

{"="*60}
ガソリン車CO2排出量統計:
{"="*60}
"""
            
            # CO2個別結果
            for i, result in enumerate(self.results, 1):
                if result['co2_emission'] is not None:
                    report += f"{i:2d}回目: {result['co2_emission']:8.1f} g (実行時間: {result['execution_time']:5.1f}s)\n"
                else:
                    report += f"{i:2d}回目: -----.-- g (実行失敗)\n"
            
            # CO2統計サマリー
            report += f"""
統計サマリー:
- 平均値: {stats['co2_emission']['mean']:8.1f} g
- 標準偏差: {stats['co2_emission']['stdev']:8.1f} g
- 最小値: {stats['co2_emission']['min']:8.1f} g
- 最大値: {stats['co2_emission']['max']:8.1f} g
- 中央値: {stats['co2_emission']['median']:8.1f} g

{"="*60}
実行時間統計:
{"="*60}
- 平均実行時間: {stats['execution_time']['mean']:6.1f} 秒
- 標準偏差: {stats['execution_time']['stdev']:6.1f} 秒
- 最短時間: {stats['execution_time']['min']:6.1f} 秒
- 最長時間: {stats['execution_time']['max']:6.1f} 秒

{"="*60}
変動性分析:
{"="*60}
停止回数の変動係数: {(stats['stop_count']['stdev'] / stats['stop_count']['mean'] * 100):5.1f}%
CO2排出量の変動係数: {(stats['co2_emission']['stdev'] / stats['co2_emission']['mean'] * 100):5.1f}%

分析結果:
"""
            
            # 変動性の評価
            stop_cv = stats['stop_count']['stdev'] / stats['stop_count']['mean'] * 100
            co2_cv = stats['co2_emission']['stdev'] / stats['co2_emission']['mean'] * 100
            
            if stop_cv < 5:
                report += "- 停止回数は非常に安定しています\n"
            elif stop_cv < 10:
                report += "- 停止回数は比較的安定しています\n"
            else:
                report += "- 停止回数にばらつきが見られます\n"
            
            if co2_cv < 5:
                report += "- CO2排出量は非常に安定しています\n"
            elif co2_cv < 10:
                report += "- CO2排出量は比較的安定しています\n"
            else:
                report += "- CO2排出量にばらつきが見られます\n"
        
        # ログファイル保存
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"📝 詳細ログ保存: {log_path}")
        except Exception as e:
            print(f"⚠️ ログ保存エラー: {e}")
        
        # CSV保存
        try:
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Run', 'StopCount', 'GasolineCO2_g', 'ExecutionTime_s', 'Status'])
                
                for result in self.results:
                    status = 'Success' if result['stop_count'] is not None else 'Failed'
                    writer.writerow([
                        result['run'],
                        result['stop_count'] if result['stop_count'] is not None else '',
                        result['co2_emission'] if result['co2_emission'] is not None else '',
                        result['execution_time'] if result['execution_time'] is not None else '',
                        status
                    ])
                
                # 統計行追加
                if stats['valid_runs'] > 0:
                    writer.writerow([])  # 空行
                    writer.writerow(['Statistics', 'StopCount', 'GasolineCO2_g', 'ExecutionTime_s', ''])
                    writer.writerow(['Mean', f"{stats['stop_count']['mean']:.1f}", 
                                   f"{stats['co2_emission']['mean']:.1f}", 
                                   f"{stats['execution_time']['mean']:.1f}", ''])
                    writer.writerow(['StdDev', f"{stats['stop_count']['stdev']:.1f}", 
                                   f"{stats['co2_emission']['stdev']:.1f}", 
                                   f"{stats['execution_time']['stdev']:.1f}", ''])
                    writer.writerow(['Min', stats['stop_count']['min'], 
                                   f"{stats['co2_emission']['min']:.1f}", 
                                   f"{stats['execution_time']['min']:.1f}", ''])
                    writer.writerow(['Max', stats['stop_count']['max'], 
                                   f"{stats['co2_emission']['max']:.1f}", 
                                   f"{stats['execution_time']['max']:.1f}", ''])
            
            print(f"📊 CSV データ保存: {csv_path}")
            
        except Exception as e:
            print(f"⚠️ CSV保存エラー: {e}")
        
        return log_path, csv_path
    
    def print_summary(self, stats):
        """コンソール用サマリー表示"""
        print("\n" + "="*60)
        print("📊 複数回実行結果サマリー")
        print("="*60)
        
        if stats is None or stats['valid_runs'] == 0:
            print("❌ 有効な結果がありません")
            return
        
        print(f"設定: 車両{self.vehicles}台, AV普及率{self.av_penetration}%, {self.num_runs}回実行")
        print(f"成功: {stats['valid_runs']}/{self.num_runs} 回")
        print()
        
        # 表形式で結果表示
        print("項目              | 平均値   | 標準偏差 | 最小値  | 最大値  | 中央値")
        print("-" * 60)
        print(f"総停止回数        | {stats['stop_count']['mean']:6.1f}回 | {stats['stop_count']['stdev']:6.1f}回 | {stats['stop_count']['min']:5d}回 | {stats['stop_count']['max']:5d}回 | {stats['stop_count']['median']:6.1f}回")
        print(f"ガソリン車CO2排出 | {stats['co2_emission']['mean']:6.1f}g | {stats['co2_emission']['stdev']:6.1f}g | {stats['co2_emission']['min']:5.1f}g | {stats['co2_emission']['max']:5.1f}g | {stats['co2_emission']['median']:6.1f}g")
        print(f"実行時間          | {stats['execution_time']['mean']:6.1f}s | {stats['execution_time']['stdev']:6.1f}s | {stats['execution_time']['min']:5.1f}s | {stats['execution_time']['max']:5.1f}s | -----s")
        
        print()
        print("変動性:")
        stop_cv = stats['stop_count']['stdev'] / stats['stop_count']['mean'] * 100
        co2_cv = stats['co2_emission']['stdev'] / stats['co2_emission']['mean'] * 100
        print(f"- 停止回数変動係数: {stop_cv:5.1f}%")
        print(f"- CO2排出変動係数: {co2_cv:5.1f}%")

def main():
    """メイン実行関数"""
    parser = argparse.ArgumentParser(description='交通シミュレーション複数回実行・統計分析')
    parser.add_argument('--vehicles', type=int, required=True,
                       help='総車両数')
    parser.add_argument('--av-penetration', type=float, required=True,
                       help='AV普及率%% (0-100)')
    parser.add_argument('--runs', type=int, default=3,
                       help='実行回数 (デフォルト: 3)')
    
    args = parser.parse_args()
    
    # パラメータチェック
    if args.vehicles <= 0:
        print("❌ 車両数は1以上である必要があります")
        return
        
    if not (0 <= args.av_penetration <= 100):
        print("❌ AV普及率は0-100の範囲である必要があります")
        return
        
    if args.runs <= 0:
        print("❌ 実行回数は1以上である必要があります")
        return
    
    # 分析実行
    analyzer = MultipleRunAnalyzer(args.vehicles, args.av_penetration, args.runs)
    
    if analyzer.run_multiple_simulations():
        stats = analyzer.calculate_statistics()
        
        if stats:
            analyzer.print_summary(stats)
            log_path, csv_path = analyzer.save_results(stats)
            print(f"\n✅ 分析完了!")
            print(f"📝 詳細結果: {log_path}")
            print(f"📊 CSVデータ: {csv_path}")
        else:
            print("❌ 統計計算に失敗しました")
    else:
        print("❌ 複数回実行に失敗しました")

if __name__ == "__main__":
    main()