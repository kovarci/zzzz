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
if errorlevel 1 (
  git rebase --abort
  rem Une maj precedente jamais publiee qui ne passe plus par-dessus la version
  rem en ligne, un fichier supprime d'un cote et modifie de l'autre : sans ceci,
  rem toutes les maj suivantes echouaient a leur tour. Mise de cote dans la
  rem branche maj-non-publiee : celle-ci la refait a partir des donnees en ligne.
  echo [!] Une maj precedente non publiee est mise de cote : branche maj-non-publiee
  git branch -f maj-non-publiee
  git reset --keep origin/main
)
echo.

echo [2/4] College de France, Museum, Academies (sciences, medecine), Ifri, IRIS, Jean-Jaures + Luma...
echo       (plusieurs minutes : 9 pages Luma + geocodage, c'est normal)
python scraper\refresh_local.py
echo.

echo [3/4] Enregistrement...
git add data/ e/ i/ d/ s/ p/ index.html sitemap.xml og.png *.txt
git commit -m "maj College de France, Museum, Academie, Ifri, IRIS, Jean-Jaures + Luma"
echo.

echo [4/4] Publication sur GitHub...
rem Gros envois (5/10/2026 : 18 Mo) : sans tampon assez grand, git echoue sur
rem « unable to rewind rpc post data » des que la connexion hoquete.
git config http.postBuffer 524288000
rem Le robot GitHub a pu publier pendant la maj : on se replace par-dessus
rem (nos donnees l'emportent, elles incluent deja les siennes), puis on pousse.
git pull --rebase --autostash -X theirs origin main
if errorlevel 1 (
  git rebase --abort
  rem Le robot a publie pendant la maj et les deux versions ne se fusionnent pas :
  rem on repart de la version en ligne et on refait la maj par-dessus.
  echo [!] La version en ligne a change pendant la maj : on la refait par-dessus...
  git branch -f maj-non-publiee
  git reset --keep origin/main
  python scraper\refresh_local.py
  git add data/ e/ i/ d/ s/ p/ index.html sitemap.xml og.png *.txt
  git commit -m "maj College de France, Museum, Academie, Ifri, IRIS, Jean-Jaures + Luma"
)
git push
if errorlevel 1 (
  rem 3 octobre 2026 : maj enregistree mais jamais publiee, connexion GitHub
  rem ou reseau indisponible a ce moment-la. 5 octobre : coupure reseau de
  rem plus de 30 s. Deux nouveaux essais, 1 puis 3 minutes plus tard.
  echo [!] Publication refusee : nouvel essai dans 1 minute...
  timeout /t 60 /nobreak >nul
  git pull --rebase --autostash -X theirs origin main
  if errorlevel 1 git rebase --abort
  git push
)
if errorlevel 1 (
  echo [!] Toujours refusee : dernier essai dans 3 minutes...
  timeout /t 180 /nobreak >nul
  git pull --rebase --autostash -X theirs origin main
  if errorlevel 1 git rebase --abort
  git push
)
if errorlevel 1 (
  echo.
  echo [!] PUBLICATION IMPOSSIBLE : verifie ta connexion internet.
  echo     La maj est enregistree sur ce PC ; la prochaine maj.bat la publiera.
)
echo.

echo ================================================
echo   Termine. Tu peux fermer cette fenetre.
echo   (Si une fenetre GitHub s'ouvre, confirme la connexion.)
echo ================================================
pause
