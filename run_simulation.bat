@echo off
chcp 65001 > nul
echo ========================================
echo    AV車・ガソリン車混合交通シミュレーション
echo ========================================
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
echo 🎯 実行方法を選択してください:
echo [1] SUMO-GUI で可視化実行
echo [2] 統合分析実行 (CO2測定 + 停止回数カウント)
echo [3] キャンセル
set /p choice="選択 (1-3): "

if "%choice%"=="1" (
    echo 🖥️  SUMO-GUI を起動中...
    python traffic_controller.py %total_vehicles% %av_penetration%
) else if "%choice%"=="2" (
    echo.
    echo 📊 統合分析を実行中...
    echo ========================================
    echo.
    
    echo 📈 [1/2] CO2排出量測定を開始します...
    python fixed_co2_monitor.py
    
    if errorlevel 1 (
        echo ❌ CO2測定に失敗しました
        pause
        exit /b 1
    )
    
    echo.
    echo 🚥 [2/2] 停止回数カウントを開始します...
    python fixed_stop_counter.py
    
    if errorlevel 1 (
        echo ❌ 停止回数カウントに失敗しました
        pause
        exit /b 1
    )
    
    echo.
    echo 📋 統合結果を生成中...
    python integrated_results_display.py
    
) else (
    echo キャンセルしました
    goto end
)

echo.
echo ✅ 完了
pause
goto end

    echo.
    echo 📋 詳細結果ファイルを開きますか？
    set /p open_results="(y/n): "
    if /i "%open_results%"=="y" (
        if exist "data\log\co2_emission_report.txt" start notepad "data\log\co2_emission_report.txt"
        if exist "data\log\stop_count_results.txt" start notepad "data\log\stop_count_results.txt"
        if exist "data\log\integrated_results.csv" start excel "data\log\integrated_results.csv"
    )

:end