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
python -m pytest tests/ -q --junitxml=pytest_report.xml
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
echo === [2c/3] auto-update README badges (from THIS run) ===
python scripts\update_readme_badges.py pytest_report.xml
if errorlevel 1 (
    echo WARNING: badge update failed -- check README badges by hand.
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
REM freshness guard (fail-open): the picked file is the lexicographically
REM greatest NAME, which is only "newest" if a file for THIS session was
REM dropped. If its name lacks TODAY's date it is a stale leftover that would
REM be silently reused as this commit's message (root cause of a 7/19 message
REM landing on a 7/22 commit). Block ONLY when we can positively prove it is
REM stale; if today's date cannot be read, skip the guard rather than block.
set "TODAY="
for /f "usebackq delims=" %%d in (`powershell -nop -c "Get-Date -Format yyyy-MM-dd" 2^>nul`) do set "TODAY=%%d"
if defined TODAY (
    echo %MSGFILE% | findstr /c:"%TODAY%" >nul
    if errorlevel 1 (
        echo.
        echo ******** STALE COMMIT MESSAGE -- NOT committing. ********
        echo Newest message file: %MSGFILE%
        echo does NOT match today's date ^(%TODAY%^) -- looks like no message
        echo file was prepared for THIS session. Create
        echo     docs\_commit_msg\%TODAY%_NN.txt
        echo with this session's message, then re-run this script.
        pause
        exit /b 1
    )
) else (
    echo WARNING: could not read today's date -- freshness guard skipped.
)
echo Using message file: %MSGFILE%
git add -A
git status -s
git commit -F "%MSGFILE%"

echo.
echo === done. last 3 commits: ===
git log --oneline -3
echo.
echo Note: README badges were auto-updated from THIS run's pytest
echo       report and pyproject.toml (scripts\update_readme_badges.py).
echo       Frontend cache keys (?v=) auto-track the version too.
pause

goto :eof
:nodefail
echo.
echo ******** NODE TESTS FAILED -- NOT committing. ********
echo ******** Paste the failures above to Claude. ********
pause
exit /b 1
