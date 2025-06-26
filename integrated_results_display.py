import os
import re
import csv
import sys
from datetime import datetime

# 結果ファイルの保存先ディレクトリ
LOG_DIR = os.path.join("data", "log")

def ensure_log_directory():
    """ログディレクトリが存在することを確認"""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except Exception as e:
        print(f"⚠️ ログディレクトリ作成エラー: {e}")
        return False
    return True

def read_co2_results():
    """
    CO2排出量結果を読み取り
    
    Returns:
        dict: CO2排出量データ
    """
    co2_data = {
        'gasoline_co2': 0.0,
        'av_co2': 0.0,
        'total_co2': 0.0,
        'av_penetration': 0.0,
        'total_vehicles': 0,
        'simulation_steps': 0,
        'execution_time': 0.0
    }
    
    # CO2レポートファイルを読み取り
    co2_report_path = os.path.join(LOG_DIR, 'co2_emission_report.txt')
    if os.path.exists(co2_report_path):
        try:
            with open(co2_report_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # 正規表現で数値を抽出
                gasoline_match = re.search(r'ガソリン車総排出量:\s*([\d.]+)\s*g', content)
                if gasoline_match:
                    co2_data['gasoline_co2'] = float(gasoline_match.group(1))
                
                av_match = re.search(r'AV車総排出量:\s*([\d.]+)\s*g', content)
                if av_match:
                    co2_data['av_co2'] = float(av_match.group(1))
                
                total_match = re.search(r'全体総排出量:\s*([\d.]+)\s*g', content)
                if total_match:
                    co2_data['total_co2'] = float(total_match.group(1))
                
                # AV普及率
                penetration_match = re.search(r'AV普及率 \(p\):\s*([\d.]+)', content)
                if penetration_match:
                    co2_data['av_penetration'] = float(penetration_match.group(1))
                
                # 総車両数
                vehicles_match = re.search(r'総車両数:\s*(\d+)', content)
                if vehicles_match:
                    co2_data['total_vehicles'] = int(vehicles_match.group(1))
                
                # シミュレーションステップ数
                steps_match = re.search(r'シミュレーション時間:\s*(\d+)\s*ステップ', content)
                if steps_match:
                    co2_data['simulation_steps'] = int(steps_match.group(1))
                
                # 実行時間
                time_match = re.search(r'実行時間:\s*([\d.]+)\s*秒', content)
                if time_match:
                    co2_data['execution_time'] = float(time_match.group(1))
                    
        except Exception as e:
            print(f"⚠️ CO2レポート読み取りエラー: {e}")
    
    return co2_data

def read_stop_results():
    """
    停止回数結果を読み取り
    
    Returns:
        dict: 停止回数データ
    """
    stop_data = {
        'total_stops': 0,
        'monitored_edges': 0,
        'edge_details': []
    }
    
    # 停止回数結果の読み取り（修正版対応）
    stop_files = [
        os.path.join(LOG_DIR, 'stop_count_results.txt'), 
        os.path.join(LOG_DIR, 'stop_count_backup.txt')
    ]
    
    for stop_file in stop_files:
        if os.path.exists(stop_file):
            try:
                with open(stop_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # 合計停止回数
                    total_match = re.search(r'総停止回数:\s*(\d+)\s*回', content)
                    if total_match:
                        stop_data['total_stops'] = int(total_match.group(1))
                    
                    # 監視エッジ数
                    edges_match = re.search(r'監視対象エッジ数:\s*(\d+)\s*個', content)
                    if edges_match:
                        stop_data['monitored_edges'] = int(edges_match.group(1))
                    
                    # エッジ別詳細（個別の停止回数）
                    lines = content.split('\n')
                    in_edge_section = False
                    for line in lines:
                        if 'エッジ別停止回数:' in line:
                            in_edge_section = True
                            continue
                        if in_edge_section:
                            edge_match = re.match(r'^([^:]+):\s*(\d+)\s*回', line.strip())
                            if edge_match and int(edge_match.group(2)) > 0:
                                edge_id = edge_match.group(1).strip()
                                count = int(edge_match.group(2))
                                stop_data['edge_details'].append((edge_id, count))
                    
                    break  # 最初に見つかったファイルを使用
                    
            except Exception as e:
                print(f"⚠️ {stop_file} 読み取りエラー: {e}")
                continue
    
    return stop_data

def calculate_metrics(co2_data, stop_data):
    """
    統合指標を計算
    
    Args:
        co2_data (dict): CO2データ
        stop_data (dict): 停止回数データ
    
    Returns:
        dict: 計算された指標
    """
    metrics = {}
    
    # CO2削減率（AV vs ガソリン車）
    if co2_data['gasoline_co2'] > 0:
        if co2_data['av_co2'] > 0:
            metrics['co2_reduction_rate'] = ((co2_data['gasoline_co2'] - co2_data['av_co2']) / co2_data['gasoline_co2']) * 100
        else:
            metrics['co2_reduction_rate'] = 100.0  # AV車が完全にゼロエミッション
    else:
        metrics['co2_reduction_rate'] = 0.0
    
    # 車両あたりの平均CO2排出量
    if co2_data['total_vehicles'] > 0:
        metrics['co2_per_vehicle'] = co2_data['total_co2'] / co2_data['total_vehicles']
    else:
        metrics['co2_per_vehicle'] = 0.0
    
    # エッジあたりの平均停止回数
    if stop_data['monitored_edges'] > 0:
        metrics['stops_per_edge'] = stop_data['total_stops'] / stop_data['monitored_edges']
    else:
        metrics['stops_per_edge'] = 0.0
    
    # 車両あたりの平均停止回数（推定）
    if co2_data['total_vehicles'] > 0:
        metrics['stops_per_vehicle'] = stop_data['total_stops'] / co2_data['total_vehicles']
    else:
        metrics['stops_per_vehicle'] = 0.0
    
    return metrics

def display_integrated_results():
    """
    統合結果を表示
    """
    # ログディレクトリの確認
    if not ensure_log_directory():
        print("⚠️ ログディレクトリにアクセスできません")
        return
    
    print("=" * 70)
    print("           🎯 統合分析結果サマリー")
    print("=" * 70)
    print("【論文検証】AV普及による交通環境改善効果の定量評価")
    print("・CO2排出量: 梅村・和田(2023) 式(5)実装検証")
    print("・停止回数: 梅村・和田(2023) 式(4)実装検証")
    print("-" * 70)
    
    # データ読み取り
    co2_data = read_co2_results()
    stop_data = read_stop_results()
    metrics = calculate_metrics(co2_data, stop_data)
    
    # シミュレーション設定
    print("🔧 シミュレーション設定:")
    print(f"   AV普及率: {co2_data['av_penetration']:.1%}")
    print(f"   総車両数: {co2_data['total_vehicles']} 台")
    print(f"   シミュレーション時間: {co2_data['simulation_steps']} ステップ")
    print(f"   実行時間: {co2_data['execution_time']:.1f} 秒")
    print()
    
    # CO2排出量結果
    print("💨 CO2排出量分析結果:")
    print(f"   🔴 ガソリン車総排出量: {co2_data['gasoline_co2']:.2f} g")
    print(f"   🟢 AV車総排出量: {co2_data['av_co2']:.2f} g")
    print(f"   📈 全体総排出量: {co2_data['total_co2']:.2f} g")
    print(f"   📊 車両あたり平均: {metrics['co2_per_vehicle']:.2f} g/台")
    if metrics['co2_reduction_rate'] > 0:
        print(f"   ✨ CO2削減効果: {metrics['co2_reduction_rate']:.1f}%")
    print()
    
    # 停止回数結果
    print("🚥 停止回数分析結果:")
    print(f"   🛑 総停止回数: {stop_data['total_stops']} 回")
    print(f"   🛣️  監視エッジ数: {stop_data['monitored_edges']} 個")
    print(f"   📊 エッジあたり平均: {metrics['stops_per_edge']:.2f} 回/エッジ")
    print(f"   🚗 車両あたり推定: {metrics['stops_per_vehicle']:.2f} 回/台")
    print()
    
    # 停止が発生したエッジの詳細（上位5件）
    if stop_data['edge_details']:
        print("🎯 停止発生箇所 (上位5件):")
        sorted_edges = sorted(stop_data['edge_details'], key=lambda x: x[1], reverse=True)
        for i, (edge_id, count) in enumerate(sorted_edges[:5]):
            print(f"   {i+1:2d}. {edge_id}: {count} 回")
        if len(sorted_edges) > 5:
            print(f"   ... 他 {len(sorted_edges)-5} 箇所")
        print()
    
    # 総合評価
    print("🏆 総合評価:")
    
    # AV普及率に基づく効果評価
    if co2_data['av_penetration'] > 0:
        print(f"   📈 AV普及率 {co2_data['av_penetration']:.1%} による効果:")
        
        if metrics['co2_reduction_rate'] > 0:
            print(f"   ✅ CO2削減効果: {metrics['co2_reduction_rate']:.1f}% の削減を達成")
        else:
            print("   ⚠️ CO2削減効果: 有意な削減は観測されませんでした")
        
        # 理論値との比較（概算）
        expected_reduction = min(co2_data['av_penetration'] * 30, 25)  # 最大25%削減の仮定
        if abs(metrics['co2_reduction_rate'] - expected_reduction) < 5:
            print(f"   📊 理論予測との整合性: 良好 (予測: 約{expected_reduction:.1f}%)")
        else:
            print(f"   📊 理論予測との差異: あり (予測: 約{expected_reduction:.1f}%)")
    else:
        print("   ℹ️ AV車なしのベースラインシミュレーション")
    
    # 交通流への影響
    if stop_data['total_stops'] == 0:
        print("   🎉 停止なし: 理想的な交通流を実現")
    elif metrics['stops_per_vehicle'] < 1.0:
        print("   ✅ 低停止率: 効率的な交通流")
    else:
        print("   ⚠️ 停止多発: 交通流の改善余地あり")
    
    print()
    
    # ファイル出力情報
    print("📊 詳細レポート:")
    files_available = []
    file_checks = [
        ('co2_emission_report.txt', "CO2排出量詳細"),
        ('co2_emission_log.csv', "CO2時系列データ"),
        ('stop_count_results.txt', "停止回数詳細"),
        ('stop_count_detailed.csv', "停止イベント詳細"),
        ('stop_count_backup.txt', "停止回数バックアップ")
    ]
    
    for filename, description in file_checks:
        filepath = os.path.join(LOG_DIR, filename)
        if os.path.exists(filepath):
            files_available.append(f"{description}: {filepath}")
    
    for file_info in files_available:
        print(f"   ✅ {file_info}")
    
    if not files_available:
        print("   ⚠️ 詳細レポートファイルが見つかりません")
    
    print("=" * 70)
    
    # 結果を統合CSVファイルに保存
    save_integrated_csv(co2_data, stop_data, metrics)

def save_integrated_csv(co2_data, stop_data, metrics):
    """
    統合結果をCSVファイルに保存
    
    Args:
        co2_data (dict): CO2データ
        stop_data (dict): 停止回数データ
        metrics (dict): 計算指標
    """
    try:
        csv_path = os.path.join(LOG_DIR, 'integrated_results.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # ヘッダー
            writer.writerow([
                'timestamp', 'av_penetration', 'total_vehicles', 'simulation_steps',
                'gasoline_co2_g', 'av_co2_g', 'total_co2_g', 'co2_reduction_rate_%',
                'total_stops', 'monitored_edges', 'stops_per_vehicle', 'co2_per_vehicle_g'
            ])
            
            # データ
            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                co2_data['av_penetration'],
                co2_data['total_vehicles'],
                co2_data['simulation_steps'],
                co2_data['gasoline_co2'],
                co2_data['av_co2'],
                co2_data['total_co2'],
                metrics['co2_reduction_rate'],
                stop_data['total_stops'],
                stop_data['monitored_edges'],
                metrics['stops_per_vehicle'],
                metrics['co2_per_vehicle']
            ])
        
        print(f"📁 統合結果を{csv_path}に保存しました")
        
    except Exception as e:
        print(f"⚠️ CSV保存エラー: {e}")

def main():
    """
    メイン実行関数
    """
    if len(sys.argv) > 1 and sys.argv[1] == '--csv-only':
        # CSVのみ生成モード
        co2_data = read_co2_results()
        stop_data = read_stop_results()
        metrics = calculate_metrics(co2_data, stop_data)
        save_integrated_csv(co2_data, stop_data, metrics)
    else:
        # 通常の表示モード
        display_integrated_results()

if __name__ == "__main__":
    main()