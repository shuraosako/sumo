import traci

def calculate_speed(L, g, P, d):
    """
    交通信号制御における車両の最適速度を決定する関数
    
    Parameters:
    L (float): リンク長（メートル）
    g (float): 信号サイクルのずれ（秒）
    P (float): AV車の普及率（0-1の小数）
    
    Returns:
    float: 決定された速度（km/h）
    """
    C = 90  # サイクル長
    vj = 60  # 法定速度（km/h）
    
    T = (C / 2) * P
    d = (L / vj) * 3.6 - g
    
    # 速度決定ロジック
    if d == 0 and (L / g) <= vj:
        v = (L / g) * 3.6  # m/s → km/h変換
    elif 0 < d <= T:
        v = vj  # 既にkm/h
    else:
        v = (L / (g + C)) * 3.6  # m/s → km/h変換
    
    return v

if __name__ == "__main__":
    # テスト用のパラメータ
    L = 100  # リンク長（メートル）
    g = 20   # 信号サイクルのずれ（秒）
    P = 0.5  # AV車普及率
    
    speed = calculate_speed(L, g, P)
    traci.vehicle.setSpeed(vehId, speed)
    
    print(f"リンク長: {L}m, サイクルずれ: {g}s, AV普及率: {P}")
    print(f"決定された速度: {speed:.2f} km/h")
    
    # 複数のケースでテスト
    test_cases = [
        (100, 20, 0.5),
        (200, 30, 0.3),
        (150, 25, 1),
        (50, 10, 0.2)
    ]
    
    print("\n--- テスト結果 ---")
    for L, g, P in test_cases:
        speed = calculate_speed(L, g, P)
        d = (L / 60) * 3.6 - g
        T = (90 / 2) * P
        print(f"L={L}m, g={g}s, P={P*100}% -> 速度={speed:.2f} km/h (d={d:.2f}, T={T:.2f})")