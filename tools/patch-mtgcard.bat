@echo off
setlocal
if "%~1"=="" (
  echo Drag your official MtgCard-fabric-1.7.0-26.2.jar onto this BAT file.
  echo It will create a separate patched JAR; the original stays untouched.
  pause
  exit /b 1
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0patch_mtgcard_mousetweaks.py" "%~1"
) else (
  python "%~dp0patch_mtgcard_mousetweaks.py" "%~1"
)
if errorlevel 1 (
  echo.
  echo No changes made to your original JAR. Check the error above.
) else (
  echo.
  echo Remove the original MTGCard JAR from mods before installing the patched copy.
)
pause
