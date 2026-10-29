@echo off
setlocal
pushd "%~dp0"
set "BUILDER_APP=quest-builder.pyz"
if not exist "%BUILDER_APP%" set "BUILDER_APP=quest_builder.py"
py -3 -c "import sys; sys.exit(sys.version_info < (3,11))" >nul 2>&1
if not errorlevel 1 (
  py -3 "%BUILDER_APP%" start
  goto done
)
python -c "import sys; sys.exit(sys.version_info < (3,11))" >nul 2>&1
if not errorlevel 1 (
  python "%BUILDER_APP%" start
  goto done
)
echo Python 3.11 or newer is required. Install Python and enable its launcher or PATH entry.
:done
pause
popd
endlocal
