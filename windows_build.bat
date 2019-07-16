:: Build script to generate a Stognastic EXE for Windows, and put it in a zip together with necessary resources.
:: This script assumes UPX and 7-zip are installed in the relevant locations, and that pyinstaller is on the PATH.
pyinstaller --upx-dir="C:/upx391w/" -F -w -i "icons/Stognastic.ico" --distpath=./win32/dist --workpath=./win32 Stognastic.py
del Stognastic_win32.zip
copy win32\dist\Stognastic.exe .
"C:\Program Files\7-Zip\7z.exe" a Stognastic_win32.zip Stognastic.exe LICENSE.txt LICENSE_appdirs.txt LICENSE_configobj.txt README.txt bell.wav icons\*
del Stognastic.exe
