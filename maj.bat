@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

echo ================================================
echo   Mise a jour : College de France, Museum, Academies, Ifri, IRIS, Jean-Jaures + Luma
echo ================================================
echo.

echo [1/4] Recuperation des dernieres donnees GitHub...
rem --rebase : une maj precedente jamais publiee (push refuse) passe par-dessus
rem au lieu de laisser des fichiers en conflit ; --autostash : le travail en
rem cours dans ce dossier est mis de cote le temps de la mise a jour.
git pull --rebase --autostash -X theirs origin main
if errorlevel 1 git rebase --abort
echo.

echo [2/4] College de France, Museum, Academies (sciences, medecine), Ifri, IRIS, Jean-Jaures + Luma...
echo       (plusieurs minutes : 9 pages Luma + geocodage, c'est normal)
python scraper\refresh_local.py
echo.

echo [3/4] Enregistrement...
git add data/ e/ i/ d/ s/ index.html sitemap.xml og.png *.txt
git commit -m "maj College de France, Museum, Academie, Ifri, IRIS, Jean-Jaures + Luma"
echo.

echo [4/4] Publication sur GitHub...
rem Le robot GitHub a pu publier pendant la maj : on se replace par-dessus
rem (nos donnees l'emportent, elles incluent deja les siennes), puis on pousse.
git pull --rebase --autostash -X theirs origin main
if errorlevel 1 git rebase --abort
git push
echo.

echo ================================================
echo   Termine. Tu peux fermer cette fenetre.
echo   (Si une fenetre GitHub s'ouvre, confirme la connexion.)
echo ================================================
pause
