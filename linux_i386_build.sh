# Build script to generate a Stognastic binary for Linux, and put it in a tarball together with necessary resources.
# This script assumes that pyinstaller is on the PATH.
# Although i386 is hardcoded into the filenames being used here, there is no technical relevance.
pyinstaller -F --distpath=./linux_i386/dist --workpath=./linux_i386 ./Stognastic.py
cp linux_i386/dist/Stognastic .
tar -cvzf Stognastic_linux_i386.tar.gz Stognastic bell.wav LICENSE.txt LICENSE_appdirs.txt LICENSE_configobj.txt README.txt icons/*
rm Stognastic
