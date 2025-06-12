#!/usr/bin/env python3
"""
簡易版混合交通生成スクリプト
randomTrips.pyに依存しない版
"""

import xml.etree.ElementTree as ET
import random
import argparse

def create_vehicle_types():
    """車両タイプファイルを作成"""
    content = '''<?xml version="1.0" encoding="UTF-8"?>
<routes>
    <!-- ガソリン車 -->
    <vType id="gasoline_car" 
           accel="2.6" 
           decel="4.5" 
           sigma="0.5" 
           length="5.0" 
           maxSpeed="50.0"
           color="1,0,0"
           emissionClass="HBEFA3/PC_G_EU4"/>
    
    <!-- AV車 -->
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
        f.write(content)
    print("✅ vehicle_types.xml を作成しました")

def get_edges_from_network(network_file):
    """ネットワークファイルからエッジリストを取得"""
    try:
        tree = ET.parse(network_file)
        root = tree.getroot()
        
        edges = []
        for edge in root.findall('edge'):
            edge_id = edge.get('id')
            # 通常のエッジのみ選択（内部エッジや特殊エッジを除外）
            if edge_id and not edge_id.startswith(':'):
                # 双方向エッジの場合、正方向のみ使用
                if not edge_id.startswith('-'):
                    edges.append(edge_id)
        
        return edges
    except Exception as e:
        print(f"❌ ネットワークファイル読み込みエラー: {e}")
        return []

def create_simple_routes(network_file, total_vehicles, av_penetration, end_time):
    """シンプルなルートファイルを作成"""
    
    # エッジリスト取得
    edges = get_edges_from_network(network_file)
    if len(edges) < 2:
        print("❌ 利用可能なエッジが不足しています")
        return False
    
    print(f"📍 利用可能なエッジ数: {len(edges)}")
    
    # AV車とガソリン車の台数計算
    av_count = int(total_vehicles * av_penetration / 100)
    gasoline_count = total_vehicles - av_count
    
    print(f"📊 車両構成:")
    print(f"   AV車: {av_count} ({av_penetration}%)")
    print(f"   ガソリン車: {gasoline_count} ({100-av_penetration}%)")
    
    # ルートファイル作成
    routes_content = '<?xml version="1.0" encoding="UTF-8"?>\n<routes>\n'
    
    # 車両タイプ定義を含める
    routes_content += '''    <!-- 車両タイプ定義 -->
    <vType id="gasoline_car" accel="2.6" decel="4.5" sigma="0.5" length="5.0" maxSpeed="50.0" color="1,0,0" emissionClass="HBEFA3/PC_G_EU4"/>
    <vType id="autonomous_car" accel="2.0" decel="3.0" sigma="0.0" length="5.0" maxSpeed="50.0" color="0,1,0" emissionClass="zero"/>
    
'''
    
    # 車両・ルート生成
    vehicle_id = 0
    
    # AV車を生成
    for i in range(av_count):
        from_edge = random.choice(edges)
        to_edge = random.choice([e for e in edges if e != from_edge])
        depart_time = random.uniform(0, end_time * 0.8)
        
        routes_content += f'    <trip id="av_{vehicle_id}" type="autonomous_car" depart="{depart_time:.1f}" from="{from_edge}" to="{to_edge}"/>\n'
        vehicle_id += 1
    
    # ガソリン車を生成
    for i in range(gasoline_count):
        from_edge = random.choice(edges)
        to_edge = random.choice([e for e in edges if e != from_edge])
        depart_time = random.uniform(0, end_time * 0.8)
        
        routes_content += f'    <trip id="gas_{vehicle_id}" type="gasoline_car" depart="{depart_time:.1f}" from="{from_edge}" to="{to_edge}"/>\n'
        vehicle_id += 1
    
    routes_content += '</routes>\n'
    
    # ファイル保存
    with open('simple_mixed_routes.rou.xml', 'w', encoding='utf-8') as f:
        f.write(routes_content)
    
    print("✅ simple_mixed_routes.rou.xml を作成しました")
    return True

def create_sumo_config(network_file):
    """SUMO設定ファイルを作成"""
    config_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="{network_file}"/>
        <route-files value="simple_mixed_routes.rou.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="600"/>
    </time>
    <processing>
        <collision.check-junctions value="true"/>
    </processing>
</configuration>'''
    
    with open('simple_mixed.sumocfg', 'w', encoding='utf-8') as f:
        f.write(config_content)
    print("✅ simple_mixed.sumocfg を作成しました")

def main():
    parser = argparse.ArgumentParser(description='簡易版混合交通生成')
    parser.add_argument('--network', '-n', default='3gousen_new.net.xml')
    parser.add_argument('--vehicles', '-v', type=int, default=100)
    parser.add_argument('--av-penetration', '-p', type=int, default=50)
    parser.add_argument('--end-time', '-e', type=int, default=600)
    
    args = parser.parse_args()
    
    print("🚀 簡易版混合交通生成開始")
    print(f"   ネットワーク: {args.network}")
    print(f"   総車両数: {args.vehicles}")
    print(f"   AV普及率: {args.av_penetration}%")
    print()
    
    # 1. 車両タイプファイル作成
    create_vehicle_types()
    
    # 2. ルートファイル作成
    success = create_simple_routes(args.network, args.vehicles, args.av_penetration, args.end_time)
    if not success:
        return
    
    # 3. SUMO設定ファイル作成
    create_sumo_config(args.network)
    
    print()
    print("🎉 準備完了！")
    print("📋 実行コマンド:")
    print("   sumo-gui -c simple_mixed.sumocfg")
    print()
    print("🎨 車両の色分け:")
    print("   🔴 赤色: ガソリン車")
    print("   🟢 緑色: AV車")

if __name__ == "__main__":
    main()