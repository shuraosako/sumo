@echo off
chcp 65001 > nul
echo ========================================
echo    AV車・ガソリン車混合交通シミュレーション
echo         【統合監視システム v2.0】
echo         【動的車両制御対応版】
echo ========================================
echo 🔧 新機能: フォルダ分離による管理性向上
echo 💫 改善点: 1回のシミュレーションで全監視実行
echo ⭐ 追加機能: 動的車両制御による車両数維持
echo ========================================
echo.

REM 現在のディレクトリ確認（monitoring/ フォルダから実行される前提）
echo 📁 実行フォルダ: %CD%
echo.

REM 設定ファイル存在チェック
if not exist "monitoring_config.py" (
    echo ❌ monitoring_config.py が見つかりません
    echo 📝 設定ファイルが必要です。monitoring フォルダ内に配置してください。
    pause
    exit /b 1
)

if not exist "integrated_monitor.py" (
    echo ❌ integrated_monitor.py が見つかりません  
    echo 📝 メインファイルが必要です。monitoring フォルダ内に配置してください。
    pause
    exit /b 1
)

REM 必要なフォルダ・ファイルの存在確認
if not exist "..\simulation\generate_mixed_traffic.py" (
    echo ❌ ..\simulation\generate_mixed_traffic.py が見つかりません
    echo 📝 simulation フォルダにファイルが必要です。
    pause
    exit /b 1
)

if not exist "..\analysis\integrated_results_display.py" (
    echo ❌ ..\analysis\integrated_results_display.py が見つかりません
    echo 📝 analysis フォルダにファイルが必要です。
    pause
    exit /b 1
)

REM 設定値検証
echo 🔍 設定ファイル検証中...
python -c "import monitoring_config; monitoring_config.validate_config()"
if errorlevel 1 (
    echo ❌ 設定ファイルに問題があります
    pause
    exit /b 1
)
echo ✅ 設定ファイル検証完了

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
echo.
echo 💡 動作説明:
echo    [1] GUI可視化: traffic_controller.py による動的制御
echo    [2] 統合分析: integrated_monitor.py による動的制御 + 同時監視
echo    両方とも車両数が%total_vehicles%台で維持されます
echo.
echo 📊 監視設定 (monitoring_config.py):
python -c "from monitoring_config import print_config_summary; print_config_summary()"
echo.
set /p confirm="この設定で実行しますか？ (y/n): "
if /i not "%confirm%"=="y" goto input_penetration

echo.
echo 🔧 車両ルート生成中...
cd ..\simulation
python generate_mixed_traffic.py --vehicles %total_vehicles% --av-penetration %av_penetration%
cd ..\monitoring

if errorlevel 1 (
    echo ❌ ルート生成に失敗しました
    pause
    exit /b 1
)

echo.
echo 🎯 実行方法を選択してください:
echo [1] SUMO-GUI で可視化実行（手動制御 + 動的車両制御）
echo [2] 統合分析実行 (CO2測定 + 停止回数カウント + 動的車両制御 同時実行)
echo [3] 設定表示のみ
echo [4] キャンセル
set /p choice="選択 (1-4): "

if "%choice%"=="1" (
    echo 🖥️  SUMO-GUI を起動中...
    echo 🎯 動的車両制御: 目標%total_vehicles%台, AV普及率%av_penetration%% で実行
    cd ..\simulation
    python traffic_controller.py %total_vehicles% %av_penetration%
    cd ..\monitoring
    
) else if "%choice%"=="2" (
    echo.
    echo 📊 統合分析を実行中...
    echo ========================================
    echo 🔍 CO2排出量測定 + 停止回数カウント + 動的車両制御 を同時実行
    echo ✅ 改善点1: 1回のシミュレーションで全監視を実行
    echo ✅ 改善点2: フォルダ分離により保守性向上
    echo ⭐ 新機能: 車両数%total_vehicles%台を動的に維持
    echo ⭐ 新機能: AV普及率%av_penetration%%を維持
    echo ✅ 利点: データ一貫性保証、実行時間半減、安定したデータ品質
    echo.
    
    REM 統合監視システム実行（動的制御パラメータ付き）
    python integrated_monitor.py --config ../config/mixed_traffic.sumocfg --vehicles %total_vehicles% --av-penetration %av_penetration%
    
    if errorlevel 1 (
        echo ❌ 統合分析に失敗しました
        pause
        exit /b 1
    )
    
    echo.
    echo 📋 統合結果を生成中...
    cd ..\analysis
    python integrated_results_display.py
    cd ..\monitoring
    
    if errorlevel 1 (
        echo ⚠️ 結果表示でエラーが発生しましたが、データは保存されています
    )
    
) else if "%choice%"=="3" (
    echo.
    echo 📋 現在の設定詳細:
    echo ========================================
    python -c "
import monitoring_config as cfg
print('🔧 ファイルパス設定:')
print(f'   ログディレクトリ: {cfg.PathConfig.LOG_DIR}')
print(f'   SUMO設定ファイル: {cfg.PathConfig.DEFAULT_SUMO_CONFIG}')
print()
print('🚗 車両設定:')
print(f'   ガソリン車タイプ: {cfg.VehicleConfig.GASOLINE_CAR_TYPE}')
print(f'   AV車タイプ: {cfg.VehicleConfig.AUTONOMOUS_CAR_TYPE}')
print(f'   最大追加車両数/ステップ: {cfg.VehicleConfig.MAX_VEHICLES_PER_STEP}')
print(f'   生成停止時間(終了前): {cfg.VehicleConfig.STOP_GENERATION_BEFORE_END}秒')
print()
print('💨 CO2監視設定:')
print(f'   レポート間隔: {cfg.CO2MonitoringConfig.REPORT_INTERVAL_STEPS} ステップ')
print()
print('🛑 停止監視設定:')
print(f'   停止速度閾値: {cfg.StopMonitoringConfig.STOP_SPEED_THRESHOLD} m/s')
print(f'   最小停止時間: {cfg.StopMonitoringConfig.MIN_STOP_DURATION} 秒')
print(f'   監視エッジ数: {len(cfg.StopMonitoringConfig.TARGET_EDGES)} 個')
print()
print('🔧 システム設定:')
print(f'   システム名: {cfg.ReportConfig.SYSTEM_NAME}')
print(f'   バージョン: {cfg.ReportConfig.VERSION}')
print()
print('💡 動的制御設定:')
print(f'   目標車両数: %total_vehicles% 台')
print(f'   目標AV普及率: %av_penetration%%%')
print(f'   制御間隔: 3秒ごと')
"
    echo ========================================
    
) else (
    echo キャンセルしました
    goto end
)

echo.
echo ✅ 完了
echo.
echo 📊 生成されたファイル:
if exist "..\data\log\co2_emission_report.txt" (
    echo    ✅ CO2排出量レポート: ..\data\log\co2_emission_report.txt
    for %%i in ("..\data\log\co2_emission_report.txt") do echo       サイズ: %%~zi bytes
)
if exist "..\data\log\co2_emission_log.csv" (
    echo    ✅ CO2時系列データ: ..\data\log\co2_emission_log.csv
    for %%i in ("..\data\log\co2_emission_log.csv") do echo       サイズ: %%~zi bytes
)
if exist "..\data\log\stop_count_results.txt" (
    echo    ✅ 停止回数レポート: ..\data\log\stop_count_results.txt
    for %%i in ("..\data\log\stop_count_results.txt") do echo       サイズ: %%~zi bytes
)
if exist "..\data\log\stop_count_detailed.csv" (
    echo    ✅ 停止詳細データ: ..\data\log\stop_count_detailed.csv
    for %%i in ("..\data\log\stop_count_detailed.csv") do echo       サイズ: %%~zi bytes
)
if exist "..\data\log\integrated_results.csv" (
    echo    ✅ 統合分析結果: ..\data\log\integrated_results.csv
    for %%i in ("..\data\log\integrated_results.csv") do echo       サイズ: %%~zi bytes
)

echo.
echo 📊 車両制御結果の確認:
echo    CO2レポートの「動的車両制御統計」セクションで
echo    目標車両数の維持状況を確認できます
echo.

echo 📋 詳細結果ファイルを開きますか？
set /p open_results="(y/n): "
if /i "%open_results%"=="y" (
    echo 📂 ファイルを開いています...
    if exist "..\data\log\co2_emission_report.txt" (
        start notepad "..\data\log\co2_emission_report.txt"
        timeout /t 1 /nobreak > nul
    )
    if exist "..\data\log\stop_count_results.txt" (
        start notepad "..\data\log\stop_count_results.txt"  
        timeout /t 1 /nobreak > nul
    )
    if exist "..\data\log\integrated_results.csv" (
        start "" "..\data\log\integrated_results.csv"
    )
)

echo.
echo 💡 設定変更方法:
echo    monitoring_config.py を編集して監視パラメータを調整できます
echo    例: 停止判定速度、監視エッジ、車両制御間隔など

pause
goto end

:end
echo.
echo ========================================  
echo 👋 お疲れ様でした！
echo 📈 統合監視システム v2.0 実行完了
echo 🎯 動的車両制御により安定したデータ収集を実現
echo ========================================