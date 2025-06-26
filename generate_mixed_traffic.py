import os
import sys
import subprocess
import xml.etree.ElementTree as ET
import random
import argparse

def create_vehicle_types_file():
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
    #SUMO環境をチェック
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
    try:
        # ネットワークファイルからエッジ情報を読み取り
        import xml.etree.ElementTree as ET
        tree = ET.parse(network_file)
        root = tree.getroot()
        
        # 利用可能なエッジを取得
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
        <end value="1000"/>
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
    parser = argparse.ArgumentParser(description='AV車とガソリン車の混合交通生成')
    parser.add_argument('--network', '-n', default='3gousen_new.net.xml', 
                       help='ネットワークファイル名 (デフォルト: 3gousen_new.net.xml)')
    parser.add_argument('--vehicles', '-v', type=int, default=100, 
                       help='総車両数 - 論文の式(4)パラメータN (デフォルト: 100)')
    parser.add_argument('--av-penetration', '-p', type=int, default=50, 
                       help='AV普及率%% - 論文の式(4)パラメータp×100 (デフォルト: 50)')
    parser.add_argument('--end-time', '-e', type=int, default=1000, 
                       help='シミュレーション時間(秒) (デフォルト: 1000)')
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