@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo ================================================
echo   Mise a jour : College de France + Luma
echo ================================================
echo.

echo [1/4] Recuperation des dernieres donnees GitHub...
git pull
echo.

echo [2/4] College de France + Luma...
echo       (plusieurs minutes : 9 pages Luma + geocodage, c'est normal)
python scraper\refresh_local.py
echo.

echo [3/4] Enregistrement...
git add data/ e/ i/ sitemap.xml og.png
git commit -m "maj College de France + Luma"
echo.

echo [4/4] Publication sur GitHub...
git push
echo.

echo ================================================
echo   Termine. Tu peux fermer cette fenetre.
echo   (Si une fenetre GitHub s'ouvre, confirme la connexion.)
echo ================================================
pause
