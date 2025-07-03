import traci
import random
import xml.etree.ElementTree as ET
import sys

# 引数チェック（日本語）
try:
    TOTAL_VEHICLES = int(sys.argv[1])
    AV_PENETRATION = float(sys.argv[2]) / 100  # 0.0〜1.0 に変換
    # 終了時間を引数から取得（オプション）
    END_TIME = int(sys.argv[3]) if len(sys.argv) > 3 else 600  # デフォルト600秒
except (IndexError, ValueError):
    print("使い方: python traffic_controller.py <総車両数> <AV普及率(0〜100)> [終了時間(秒)]")
    print("例: python traffic_controller.py 100 40 600  ← 総車両数100台、AV比率40%、600秒実行")
    sys.exit(1)

# === パラメータ設定 ===
NETWORK_FILE = "3gousen_new.net.xml"
CONFIG_FILE = "mixed_traffic.sumocfg"

def get_simulation_end_time():
    """
    SUMOcfgファイルから終了時間を自動読み取り
    """
    try:
        tree = ET.parse(CONFIG_FILE)
        root = tree.getroot()
        time_elem = root.find('.//time')
        if time_elem is not None:
            end_elem = time_elem.find('end')
            if end_elem is not None:
                return int(float(end_elem.get('value', 600)))
    except Exception as e:
        print(f"⚠️ sumocfg読み取りエラー: {e}")
    return 600  # デフォルト値

# === ネットワークファイルから車両が通行可能なエッジIDを抽出 ===
def get_valid_edges(net_file):
    tree = ET.parse(net_file)
    root = tree.getroot()
    edge_ids = []

    for edge in root.findall("edge"):
        edge_id = edge.get("id")
        if edge.get("function") == "internal":
            continue
        if edge_id.startswith(":"):
            continue

        lanes = edge.findall("lane")
        if not lanes:
            continue

        for lane in lanes:
            allow = lane.get("allow")
            disallow = lane.get("disallow")

            if allow:
                if "passenger" in allow:
                    edge_ids.append(edge_id)
                    break
            elif disallow:
                if "passenger" not in disallow:
                    edge_ids.append(edge_id)
                    break
            else:
                # allow/disallow 未指定はpassenger許可とみなす
                edge_ids.append(edge_id)
                break

    return edge_ids

# === ランダムに車両を生成・追加 ===
def add_vehicle(veh_id, is_av, edge_ids):
    max_attempts = 10  # 無効ルートを繰り返さないための制限
    veh_type = "autonomous_car" if is_av else "gasoline_car"

    for _ in range(max_attempts):
        from_edge = random.choice(edge_ids)
        to_edge = random.choice([e for e in edge_ids if e != from_edge])

        route = traci.simulation.findRoute(from_edge, to_edge)
        if route.edges:  # ルートが存在するか確認
            route_id = f"route_{veh_id}"
            traci.route.add(route_id, route.edges)
            traci.vehicle.add(
                vehID=veh_id,
                routeID=route_id,
                typeID=veh_type,
                departPos="random"
            )
            print(f"✅ 車両追加: {veh_id}, from={from_edge}, to={to_edge}, type={veh_type}")
            return True

    print(f"⚠️ 車両追加失敗: {veh_id} から有効なルートが見つかりませんでした")
    return False

def main():
    # 終了時間の決定（優先順位: 引数 > sumocfg > デフォルト）
    if len(sys.argv) <= 3:
        END_TIME = get_simulation_end_time()
    
    print(f"🎯 シミュレーション設定:")
    print(f"   総車両数: {TOTAL_VEHICLES}")
    print(f"   AV普及率: {AV_PENETRATION*100:.1f}%")
    print(f"   実行時間: {END_TIME} 秒")
    print(f"   設定ファイル: {CONFIG_FILE}")
    
    edge_ids = get_valid_edges(NETWORK_FILE)
    if not edge_ids:
        print("❌ 有効な出発エッジが見つかりません。ネットワークファイルを確認してください。")
        sys.exit(1)

    print(f"🛣️ 有効エッジ数: {len(edge_ids)}")

    traci.start(["sumo-gui", "-c", CONFIG_FILE])  # GUIなしで実行する場合は "sumo"

    print_interval = 10  # 10秒ごとに表示
    veh_id_counter = 2000  # 新規車両ID用カウンター
    last_print_time = 0

    try:
        while True:  # 無限ループから脱却
            traci.simulationStep()
            
            # 現在のシミュレーション時間を取得
            current_sim_time = traci.simulation.getTime()
            
            # ★ 重要: 終了条件をシミュレーション時間ベースに変更 ★
            if current_sim_time >= END_TIME:
                print(f"\n✅ シミュレーション時間 {END_TIME} 秒に到達しました")
                break

            current_vehicles = traci.vehicle.getIDList()
            num_current = len(current_vehicles)

            # 定期的に車両数を表示
            if current_sim_time - last_print_time >= print_interval:
                print(f"[{current_sim_time:6.0f}秒] 現在の車両数: {num_current:3d} (目標: {TOTAL_VEHICLES})")
                last_print_time = current_sim_time

            # 車両補充ロジック（終了時刻近くでは追加停止）
            if current_sim_time < END_TIME - 60:  # 終了60秒前まで車両追加
                if num_current < TOTAL_VEHICLES:
                    shortage = min(TOTAL_VEHICLES - num_current, 5)
                    success_count = 0
                    
                    for _ in range(shortage):
                        is_av = random.random() < AV_PENETRATION
                        veh_id = f"gen_{veh_id_counter}"
                        if add_vehicle(veh_id, is_av, edge_ids):
                            success_count += 1
                        veh_id_counter += 1
                    
                    if success_count > 0:
                        print(f"🚗 {success_count}台追加 (時刻: {current_sim_time:.0f}s)")

            # 安全弁: シミュレーションに車両がいない場合は終了
            if current_sim_time > 60 and num_current == 0:
                print(f"\n⚠️ 車両がいなくなりました。シミュレーション終了 (時刻: {current_sim_time:.0f}s)")
                break

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print(f"\n📊 最終結果:")
        try:
            final_vehicles = traci.vehicle.getIDList()
            final_time = traci.simulation.getTime()
            print(f"   最終車両数: {len(final_vehicles)}")
            print(f"   最終時刻: {final_time:.0f} 秒")
            
            # 車両種別の集計
            gasoline_count = 0
            av_count = 0
            for veh_id in final_vehicles:
                try:
                    vtype = traci.vehicle.getTypeID(veh_id)
                    if vtype == "gasoline_car":
                        gasoline_count += 1
                    elif vtype == "autonomous_car":
                        av_count += 1
                except:
                    pass
            
            print(f"   ガソリン車: {gasoline_count} 台")
            print(f"   AV車: {av_count} 台")
            if gasoline_count + av_count > 0:
                actual_av_ratio = av_count / (gasoline_count + av_count) * 100
                print(f"   実際のAV比率: {actual_av_ratio:.1f}%")
        except:
            pass
        
        traci.close()
        print("🎉 シミュレーション正常終了")

if __name__ == "__main__":
    main()