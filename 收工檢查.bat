@echo off
REM ============================================================
REM stroke-order session-close check (double-click to run)
REM 1) fetch-first SOP  2) full pytest  3) commit only if green
REM NOTE: ASCII-only on purpose -- cmd.exe parses this file in
REM       the OEM codepage; Chinese text lives in the UTF-8
REM       commit-message file read via "git commit -F".
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate.bat

echo.
echo === [1/3] SOP-0 fetch-first ===
git fetch origin
git log HEAD..origin/main --oneline
echo (If commits are listed above: cross-machine changes exist.
echo  Run "git pull" first, then re-run this script.)
echo.

echo === [2/3] full pytest ===
python -m pytest tests/ -q
if errorlevel 1 (
    echo.
    echo ******** TESTS FAILED -- NOT committing. ********
    echo ******** Paste the failures above to Claude. ********
    pause
    exit /b 1
)

echo.
echo === [2b/3] node tests (tests\*.mjs) ===
where node >nul 2>nul
if errorlevel 1 (
    echo WARNING: node not found -- mjs tests SKIPPED on this machine.
    echo          CI will still run them on push.
    pause
) else (
    for %%f in (tests\*.mjs) do node --test "%%f" || goto :nodefail
)

echo.
echo === [3/3] tests green -- committing ===
REM pick the newest prepared commit-message file automatically
set "MSGFILE="
for /f "delims=" %%f in ('dir /b /o:n "docs\_commit_msg\*.txt"') do set "MSGFILE=docs\_commit_msg\%%f"
if "%MSGFILE%"=="" (
    echo No commit message file found in docs\_commit_msg\ -- aborting.
    pause
    exit /b 1
)
echo Using message file: %MSGFILE%
git add -A
git status -s
git commit -F "%MSGFILE%"

echo.
echo === done. last 3 commits: ===
git log --oneline -3
echo.
echo Reminder: README badges must match THIS run's pytest output
echo           (tests count) and pyproject.toml (version). Copy the
echo           actual numbers -- never use expected/estimated values.
pause

goto :eof
:nodefail
echo.
echo ******** NODE TESTS FAILED -- NOT committing. ********
echo ******** Paste the failures above to Claude. ********
pause
exit /b 1
