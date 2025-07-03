@echo off
chcp 65001 > nul
echo ========================================
echo    AV車・ガソリン車混合交通シミュレーション
echo ========================================
echo 【論文対応】梅村・和田(2023) 式(4)・(5) 検証実験
echo グリーンウェーブ制御対応版
echo.

:input_penetration
set /p av_penetration="AV普及率を入力してください (0-100): "
if "%av_penetration%"=="" goto input_penetration
if %av_penetration% LSS 0 goto input_penetration
if %av_penetration% GTR 100 goto input_penetration

:input_vehicles
set /p total_vehicles="総車両数を入力してください (デフォルト: 100): "
if "%total_vehicles%"=="" set total_vehicles=100

echo.
echo 🚗 設定内容:
echo    総車両数: %total_vehicles%
echo    AV普及率: %av_penetration%%%
set /p confirm="この設定で実行しますか？ (y/n): "
if /i not "%confirm%"=="y" goto input_penetration

echo.
echo 🔧 車両ルート生成中...
python generate_mixed_traffic.py --vehicles %total_vehicles% --av-penetration %av_penetration%

if errorlevel 1 (
    echo ❌ ルート生成に失敗しました
    pause
    exit /b 1
)

echo.
echo ========================================
echo 🎯 実行方法を選択してください:
echo ========================================
echo [1] SUMO-GUI 基本可視化実行
echo [2] グリーンウェーブ制御実験 (GUI)
echo [3] 統合分析実行 (CO2測定 + 停止回数カウント)
echo [4] グリーンウェーブ制御付き統合分析
echo [5] キャンセル
echo ========================================
set /p choice="選択 (1-5): "

if "%choice%"=="1" (
    echo.
    echo 🖥️  SUMO-GUI 基本実行を開始中...
    echo 車両制御のみ（グリーンウェーブなし）
    echo ========================================
    python traffic_controller.py %total_vehicles% %av_penetration%
    
) else if "%choice%"=="2" (
    echo.
    echo 🌊 グリーンウェーブ制御実験を開始中...
    echo AV車のみ最適速度制御を実行
    echo ========================================
    python green_wave_controller.py %av_penetration% gui
    
) else if "%choice%"=="3" (
    echo.
    echo 📊 統合分析を実行中（グリーンウェーブなし）...
    echo ========================================
    echo.
    
    echo 📈 [1/3] CO2排出量測定を開始します...
    python fixed_co2_monitor.py
    
    if errorlevel 1 (
        echo ❌ CO2測定に失敗しました
        pause
        exit /b 1
    )
    
    echo.
    echo 🚥 [2/3] 停止回数カウントを開始します...
    python fixed_stop_counter.py
    
    if errorlevel 1 (
        echo ❌ 停止回数カウントに失敗しました
        pause
        exit /b 1
    )
    
    echo.
    echo 📋 [3/3] 統合結果を生成中...
    python integrated_results_display.py
    
) else if "%choice%"=="4" (
    echo.
    echo 🌊📊 グリーンウェーブ制御付き統合分析を実行中...
    echo ========================================
    echo このモードではAV車にグリーンウェーブ制御を適用し、
    echo 同時にCO2排出量と停止回数を測定します
    echo.
    
    echo 🌊 [1/4] グリーンウェーブ制御 + CO2測定を開始します...
    echo 注意: バックグラウンドで複数プロセスが同時実行されます
    echo.
    
    REM 複数プロセス同時実行（Windows用）
    echo SUMOプロセス開始...
    start /B python green_wave_controller.py %av_penetration% ^> data\log\greenwave_output.log 2^>^&1
    
    REM 少し待ってからCO2測定開始
    timeout /t 5 /nobreak >nul
    echo CO2測定プロセス開始...
    start /B python fixed_co2_monitor.py ^> data\log\co2_output.log 2^>^&1
    
    REM さらに少し待ってから停止回数測定開始
    timeout /t 3 /nobreak >nul
    echo 停止回数測定プロセス開始...
    python fixed_stop_counter.py
    
    echo.
    echo ⏳ 全プロセス完了を待機中...
    timeout /t 5 /nobreak >nul
    
    echo.
    echo 📋 [4/4] 統合結果を生成中...
    python integrated_results_display.py
    
    echo.
    echo 🌊 グリーンウェーブ制御ログも確認してください:
    if exist "data\log\green_wave_control_log.csv" (
        echo ✅ グリーンウェーブ制御ログ: data\log\green_wave_control_log.csv
    )
    if exist "data\log\green_wave_control_report.txt" (
        echo ✅ グリーンウェーブ制御レポート: data\log\green_wave_control_report.txt
    )
    
) else (
    echo キャンセルしました
    goto end
)

echo.
echo ✅ 実行完了
echo ========================================

echo.
echo 📊 結果ファイルの確認:
if exist "data\log\co2_emission_report.txt" (
    echo ✅ CO2排出量レポート: data\log\co2_emission_report.txt
)
if exist "data\log\stop_count_results.txt" (
    echo ✅ 停止回数レポート: data\log\stop_count_results.txt
)
if exist "data\log\integrated_results.csv" (
    echo ✅ 統合結果CSV: data\log\integrated_results.csv
)
if exist "data\log\green_wave_control_report.txt" (
    echo ✅ グリーンウェーブ制御レポート: data\log\green_wave_control_report.txt
)

echo.
echo 📋 詳細結果ファイルを開きますか？
set /p open_results="(y/n): "
if /i "%open_results%"=="y" (
    echo ファイルを開いています...
    if exist "data\log\co2_emission_report.txt" start notepad "data\log\co2_emission_report.txt"
    if exist "data\log\stop_count_results.txt" start notepad "data\log\stop_count_results.txt"
    if exist "data\log\integrated_results.csv" (
        start excel "data\log\integrated_results.csv" 2>nul || start "data\log\integrated_results.csv"
    )
    if exist "data\log\green_wave_control_report.txt" start notepad "data\log\green_wave_control_report.txt"
)

echo.
echo 🎓 論文検証実験のヒント:
echo ========================================
echo 💡 異なるAV普及率で複数回実験を実行し、以下を比較してください:
echo    - AV普及率 0%%, 25%%, 50%%, 75%%, 100%% での効果
echo    - グリーンウェーブあり/なしでの比較
echo    - CO2削減率と停止回数の相関関係
echo.
echo 📈 期待される結果:
echo    - AV普及率↑ → 停止回数↓ → CO2排出量↓
echo    - グリーンウェーブ制御により更なる改善効果
echo    - 論文の式(4)・(5)の実証的検証
echo.

:end
pause