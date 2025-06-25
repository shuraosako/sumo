import traci
import random
import xml.etree.ElementTree as ET
import sys

# 引数チェック（日本語）
try:
    TOTAL_VEHICLES = int(sys.argv[1])
    AV_PENETRATION = float(sys.argv[2]) / 100  # 0.0〜1.0 に変換
except (IndexError, ValueError):
    print("使い方: python traffic_controller.py <総車両数> <AV普及率(0〜100)>")
    print("例: python traffic_controller.py 100 40  ← 総車両数100台、AV比率40%")
    sys.exit(1)

# === パラメータ設定 ===
NETWORK_FILE = "3gousen_new.net.xml"
CONFIG_FILE = "mixed_traffic.sumocfg"

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
            return  # 成功したので終了

    print(f"⚠️ 車両追加失敗: {veh_id} から有効なルートが見つかりませんでした")



# === メイン実行 ===
def main():
    edge_ids = get_valid_edges(NETWORK_FILE)
    if not edge_ids:
        print("❌ 有効な出発エッジが見つかりません。ネットワークファイルを確認してください。")
        sys.exit(1)

    traci.start(["sumo-gui", "-c", CONFIG_FILE])  # GUIなしで実行する場合は "sumo"

    step = 0
    print_interval = 2  # 2秒ごとに表示（SUMOの1ステップ = 1秒）
    veh_id_counter = 2000  # 新規車両ID用カウンター

    try:
        while step < 10000:
            traci.simulationStep()

            current_vehicles = traci.vehicle.getIDList()
            num_current = len(current_vehicles)

            # ◉ 2秒ごとに車両数を表示
            if step % print_interval == 0:
                print(f"[{step}秒] 現在の車両数: {num_current}")

            # ◉ 車両補充ロジック
            if num_current < TOTAL_VEHICLES:
                for _ in range(TOTAL_VEHICLES - num_current):
                    is_av = random.random() < AV_PENETRATION
                    veh_id = f"gen_{veh_id_counter}"
                    add_vehicle(veh_id, is_av, edge_ids)
                    veh_id_counter += 1

            step += 1

    finally:
        traci.close()

if __name__ == "__main__":
    main()
