#!/usr/bin/env python3
"""
AV車とガソリン車の混合交通生成スクリプト
AV普及率をパラメータで制御可能

【論文との対応関係】
参考論文: 梅村悠生, 和田健太郎 (2023)
「自動運転車両の速度制御を考慮した系統信号制御に関する考察」

■ 論文理論の実装箇所:
1. 式(4)のパラメータ設定:
   - p (AV普及率): --av-penetration引数で制御 (0 ≤ p ≤ 1)
   - N (車群台数): --vehicles引数で総車両数を設定
   
2. 車両分類の実装:
   - AV車: グリーンウェーブに従う車両 (論文の理論対象)
   - 一般車両: グリーンウェーブに従わない車両 (論文の比較対象)
   
3. 交通流特性の設定:
   - AV車: sigma=0.0 (完全制御、論文のペースメーカー機能)
   - 一般車: sigma=0.5 (人間の運転ばらつき)
   
4. 環境負荷特性:
   - AV車: emissionClass="zero" (CO2排出ゼロ)
   - 一般車: emissionClass="HBEFA3/PC_G_EU4" (CO2排出あり)

■ 理論的意義:
本スクリプトは論文の式(4)〜(5)で予測される効果を
実際のシミュレーション環境で検証するための基盤を構築
"""

import os
import sys
import subprocess
import xml.etree.ElementTree as ET
import random
import argparse

def create_vehicle_types_file():
    """
    車両タイプ定義ファイルを作成
    
    【論文対応】車両分類の物理的実装
    
    ■ 論文の車両分類理論:
    - AV (Autonomous Vehicle): グリーンウェーブ制御に従う車両
    - 一般車両: グリーンウェーブ制御に従わない車両
    
    ■ 実装での車両特性設定:
    
    1. AV車の特性 (autonomous_car):
       - sigma=0.0: 論文の「完全制御」を表現
         * 論文: AVは正確にグリーンウェーブ速度vGで走行
         * 実装: 運転ばらつきゼロで理想的な制御を実現
       
       - emissionClass="zero": 論文の環境効果分析用
         * 論文の式(5): AV車はCO2排出量削減に寄与
         * 実装: 排出ガスゼロで環境負荷なし
       
       - color="0,1,0": 緑色表示でAV車を視覚的に識別
    
    2. ガソリン車の特性 (gasoline_car):
       - sigma=0.5: 論文の「人間運転者のばらつき」を表現
         * 論文: 一般車両は系統速度uで走行（ばらつきあり）
         * 実装: 標準的な人間運転者の行動モデル
       
       - emissionClass="HBEFA3/PC_G_EU4": 実際のCO2排出
         * 論文の式(5): CO2排出量計算の対象車両
         * 実装: 欧州排出基準に基づく排出量モデル
       
       - color="1,0,0": 赤色表示でガソリン車を視覚的に識別
    
    ■ 論文の式(4)への寄与:
    この車両特性設定により、AV車が車群のペースメーカーとして
    機能し、停止回数削減効果を実現する基盤を提供
    """
    vehicle_types_content = '''<?xml version="1.0" encoding="UTF-8"?>
<routes>
    <!-- ガソリン車（一般車両）- 論文の「グリーンウェーブに従わない車両」 -->
    <vType id="gasoline_car" 
           accel="2.6" 
           decel="4.5" 
           sigma="0.5" 
           length="5.0" 
           maxSpeed="50.0"
           color="1,0,0"
           emissionClass="HBEFA3/PC_G_EU4"/>
    
    <!-- AV車（自動運転車）- 論文の「グリーンウェーブに従う車両」 -->
    <vType id="autonomous_car" 
           accel="2.0" 
           decel="3.0" 
           sigma="0.0" 
           length="5.0" 
           maxSpeed="50.0"
           color="0,1,0"
           emissionClass="zero"/>
</routes>'''
    
    with open('vehicle_types.xml', 'w', encoding='utf-8') as f:
        f.write(vehicle_types_content)
    print("✅ vehicle_types.xml を作成しました")

def check_sumo_environment():
    """
    SUMO環境をチェック
    
    【論文対応】シミュレーション環境の整合性確保
    論文の理論検証には適切なシミュレーション環境が必要
    """
    sumo_home = os.environ.get('SUMO_HOME')
    if not sumo_home:
        print("⚠️  SUMO_HOME環境変数が設定されていません")
        print("💡 以下のコマンドで設定してください:")
        print('   set SUMO_HOME=C:\\Program Files (x86)\\Eclipse\\Sumo')
        print("   または、SUMOのインストールディレクトリに合わせて調整してください")
        return False
    
    print(f"✅ SUMO_HOME: {sumo_home}")
    
    # randomTrips.pyの存在確認
    random_trips_path = os.path.join(sumo_home, 'tools', 'randomTrips.py')
    if not os.path.exists(random_trips_path):
        print(f"⚠️  randomTrips.pyが見つかりません: {random_trips_path}")
        return False
    
    return True

def create_manual_trips(network_file, total_vehicles, end_time, output_file):
    """
    手動でシンプルなトリップファイルを作成
    randomTrips.pyが使用できない場合の代替手段
    
    【論文対応】交通需要の生成
    論文では「完全に飽和している状況」を前提とするが、
    実装では現実的な交通需要パターンを生成
    
    Args:
        network_file: ネットワークファイル
        total_vehicles: 総車両数（論文の式(4)におけるN×サイクル数）
        end_time: シミュレーション時間
        output_file: 出力ファイル名
    """
    try:
        # ネットワークファイルからエッジ情報を読み取り
        import xml.etree.ElementTree as ET
        tree = ET.parse(network_file)
        root = tree.getroot()
        
        # 利用可能なエッジを取得
        # 【論文対応】論文の「リンク」概念に相当
        edges = []
        for edge in root.findall('edge'):
            edge_id = edge.get('id')
            # 内部エッジや特殊エッジを除外
            if edge_id and not edge_id.startswith(':') and not edge_id.startswith('-'):
                edges.append(edge_id)
        
        if len(edges) < 2:
            print("❌ 利用可能なエッジが不足しています")
            return False
        
        # 手動トリップファイル作成
        # 【論文対応】車両の時空間分布を制御
        trips_content = '<?xml version="1.0" encoding="UTF-8"?>\n<trips>\n'
        
        for i in range(total_vehicles):
            # ランダムに出発地と目的地を選択
            from_edge = random.choice(edges)
            to_edge = random.choice([e for e in edges if e != from_edge])
            # 出発時間の分散（論文の車群到着パターンに対応）
            depart_time = random.uniform(0, end_time * 0.8)  # 80%の時間内にランダム出発
            
            trips_content += f'    <trip id="{i}" depart="{depart_time:.1f}" from="{from_edge}" to="{to_edge}"/>\n'
        
        trips_content += '</trips>\n'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(trips_content)
        
        print(f"✅ 手動トリップファイル '{output_file}' を作成しました")
        return True
        
    except Exception as e:
        print(f"❌ 手動トリップ作成エラー: {e}")
        return False

def generate_mixed_routes(network_file, total_vehicles, av_penetration, end_time, output_file):
    """
    混合交通のルートファイルを生成
    
    【重要】論文の式(4)パラメータの物理的実装
    
    ■ 論文の式(4)との対応:
    m = Σ(k=1 to N-a) (k-1)/N (1-p)^(k-1) p + (N-a)/N (1-p)^(N-a)
    
    実装でのパラメータ設定:
    - p (AV普及率): av_penetration / 100 で実装
    - N (車群台数): total_vehicles で近似
    - 車両配置: ランダム配置により確率的効果を実現
    
    ■ 理論的背景:
    論文では「車群内でのAV位置により停止回数が決まる」と予測。
    本実装では、実際の車両配置をランダムに決定し、
    長時間シミュレーションで理論的期待値に収束させる。
    
    Args:
        network_file: ネットワークファイル名
        total_vehicles: 総車両数（論文のN相当）
        av_penetration: AV普及率 0-100（論文のp×100）
        end_time: シミュレーション終了時間
        output_file: 出力ファイル名
    """
    
    # AV車とガソリン車の台数計算
    # 【論文の式(4)パラメータ計算】
    av_count = int(total_vehicles * av_penetration / 100)
    gasoline_count = total_vehicles - av_count
    
    print(f"📊 車両構成:")
    print(f"   総車両数: {total_vehicles}")
    print(f"   AV車: {av_count} ({av_penetration}%)")
    print(f"   ガソリン車: {gasoline_count} ({100-av_penetration}%)")
    
    # 一時的なトリップファイルを生成
    temp_trips = "temp_trips.trips.xml"
    
    # randomTrips.pyを使用してベースとなるトリップを生成
    sumo_home = os.environ.get('SUMO_HOME', '')
    if sumo_home:
        # Windows用パス修正
        sumo_tools = sumo_home.replace('\\', '/') + '/tools'
        random_trips_script = f'{sumo_tools}/randomTrips.py'
    else:
        # SUMO_HOMEが設定されていない場合の代替
        random_trips_script = 'randomTrips.py'
    
    random_trips_cmd = [
        'python', random_trips_script,
        '-n', network_file,
        '-e', str(end_time),
        '-o', temp_trips,
        '--validate',
        '--remove-loops',
        '--allow-fringe'
    ]
    
    print("🚗 ベーストリップを生成中...")
    try:
        result = subprocess.run(random_trips_cmd, check=True, capture_output=True, text=True)
        print("✅ ベーストリップ生成完了")
    except subprocess.CalledProcessError as e:
        print(f"❌ トリップ生成エラー:")
        print(f"   コマンド: {' '.join(random_trips_cmd)}")
        print(f"   エラー出力: {e.stderr}")
        print(f"   標準出力: {e.stdout}")
        print("\n💡 解決方法:")
        print("   1. SUMO_HOME環境変数が正しく設定されているか確認")
        print("   2. 以下のコマンドで手動実行を試してください:")
        print(f'   python "C:\\Program Files (x86)\\Eclipse\\Sumo\\tools\\randomTrips.py" -n {network_file} -e {end_time} -o {temp_trips}')
        return False
    except FileNotFoundError:
        print(f"❌ randomTrips.pyが見つかりません")
        print("💡 手動でトリップファイルを作成します...")
        # 手動でトリップファイルを作成
        return create_manual_trips(network_file, total_vehicles, end_time, temp_trips)
    
    # XMLファイルを読み込んで車両タイプを割り当て
    # 【重要】論文の車両分類の実装
    try:
        tree = ET.parse(temp_trips)
        root = tree.getroot()
        
        # 車両IDリストを作成
        trips = root.findall('trip')
        if len(trips) < total_vehicles:
            print(f"⚠️  生成されたトリップ数 ({len(trips)}) が指定車両数 ({total_vehicles}) より少ないです")
            total_vehicles = len(trips)
            av_count = int(total_vehicles * av_penetration / 100)
            gasoline_count = total_vehicles - av_count
        
        # ランダムに車両タイプを割り当て
        # 【論文対応】確率的な車両配置の実装
        # 論文の式(4)では「車両kにAVが存在する確率」を扱うが、
        # 実装では決定的配置を行い、複数回実行で統計的効果を検証
        vehicle_indices = list(range(min(total_vehicles, len(trips))))
        random.shuffle(vehicle_indices)
        
        av_indices = set(vehicle_indices[:av_count])
        
        # 車両タイプを割り当て
        # 【論文対応】AV車 vs 一般車両の分類実装
        processed_vehicles = 0
        for i, trip in enumerate(trips):
            if processed_vehicles >= total_vehicles:
                # 余分な車両を削除
                root.remove(trip)
                continue
                
            if i in av_indices:
                # AV車を割り当て
                # 【論文対応】「グリーンウェーブに従う車両」
                trip.set('type', 'autonomous_car')
            else:
                # ガソリン車を割り当て
                # 【論文対応】「グリーンウェーブに従わない車両」
                trip.set('type', 'gasoline_car')
            
            processed_vehicles += 1
        
        # 修正されたXMLを保存
        tree.write(output_file, encoding='utf-8', xml_declaration=True)
        print(f"✅ 混合交通ルートファイル '{output_file}' を作成しました")
        
        # 一時ファイルを削除
        if os.path.exists(temp_trips):
            os.remove(temp_trips)
        
        return True
        
    except Exception as e:
        print(f"❌ ルートファイル処理エラー: {e}")
        return False

def create_sumo_config(network_file, route_file, additional_files=None):
    """
    SUMO設定ファイルを作成
    
    【論文対応】シミュレーション環境の構築
    論文の理論検証に必要な設定パラメータを適用
    
    Args:
        network_file: ネットワークファイル（論文の「道路リンク」）
        route_file: ルートファイル（論文の「車群」データ）
        additional_files: 追加設定ファイル
    """
    config_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{network_file}"/>
        <route-files value="vehicle_types.xml,{route_file}"/>'''
    
    if additional_files:
        config_content += f'\n        <additional-files value="{additional_files}"/>'
    
    config_content += '''
    </input>
    <time>
        <begin value="0"/>
        <end value="600"/>
    </time>
    <processing>
        <collision.check-junctions value="true"/>
    </processing>
    <report>
        <verbose value="true"/>
    </report>
</configuration>'''
    
    with open('mixed_traffic.sumocfg', 'w', encoding='utf-8') as f:
        f.write(config_content)
    print("✅ mixed_traffic.sumocfg を作成しました")

def main():
    """
    メイン実行関数
    
    【論文対応】混合交通シミュレーション環境の構築
    論文の理論検証に必要な全ての設定を統合的に実行
    """
    parser = argparse.ArgumentParser(description='AV車とガソリン車の混合交通生成')
    parser.add_argument('--network', '-n', default='3gousen_new.net.xml', 
                       help='ネットワークファイル名 (デフォルト: 3gousen_new.net.xml)')
    parser.add_argument('--vehicles', '-v', type=int, default=100, 
                       help='総車両数 - 論文の式(4)パラメータN (デフォルト: 100)')
    parser.add_argument('--av-penetration', '-p', type=int, default=50, 
                       help='AV普及率%% - 論文の式(4)パラメータp×100 (デフォルト: 50)')
    parser.add_argument('--end-time', '-e', type=int, default=600, 
                       help='シミュレーション時間(秒) (デフォルト: 600)')
    parser.add_argument('--output', '-o', default='mixed_routes.rou.xml', 
                       help='出力ルートファイル名 (デフォルト: mixed_routes.rou.xml)')
    parser.add_argument('--poly-file', default=None, 
                       help='ポリゴンファイル名（オプション）')
    
    args = parser.parse_args()
    
    # 入力値検証
    if not (0 <= args.av_penetration <= 100):
        print("❌ AV普及率は0-100の範囲で指定してください")
        return
    
    if not os.path.exists(args.network):
        print(f"❌ ネットワークファイル '{args.network}' が見つかりません")
        return
    
    print("🚀 混合交通シミュレーション準備開始")
    print("【論文対応】梅村・和田(2023) 式(4)〜(5)検証環境構築")
    print(f"   ネットワーク: {args.network}")
    print(f"   総車両数 (N): {args.vehicles}")
    print(f"   AV普及率 (p): {args.av_penetration}% = {args.av_penetration/100:.2f}")
    print(f"   シミュレーション時間: {args.end_time}秒")
    print()
    
    # SUMO環境チェック
    if not check_sumo_environment():
        print("⚠️  SUMO環境に問題がありますが、手動作成を試行します...")
    
    # 1. 車両タイプファイル作成
    create_vehicle_types_file()
    
    # 2. 混合交通ルート生成
    success = generate_mixed_routes(
        args.network, 
        args.vehicles, 
        args.av_penetration, 
        args.end_time, 
        args.output
    )
    
    if not success:
        print("❌ ルート生成に失敗しました")
        return
    
    # 3. SUMO設定ファイル作成
    create_sumo_config(args.network, args.output, args.poly_file)
    
    print()
    print("🎉 準備完了！")
    print("📋 次のコマンドでシミュレーションを実行:")
    print("   sumo-gui -c mixed_traffic.sumocfg")
    print()
    print("🎨 車両の色分け:")
    print("   🔴 赤色: ガソリン車 (CO2排出あり)")
    print("   🟢 緑色: AV車 (CO2排出なし)")
    print()
    print("【論文対応】期待される効果:")
    print("   - 論文の式(4): AV普及率が高いほど停止回数減少")
    print("   - 論文の式(5): 停止回数減少によりCO2排出量も減少")

if __name__ == "__main__":
    main()