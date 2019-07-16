# Stochastic Nag - Adaptive self-monitoring skinner box for efficient habit-building
# Copyright (C) 2015  Robin Neufeld

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


# TODO: Output timestamp data of responses, and plot time series (credit Kelvin)

# TODO: fix linux crashes -- seems to crash on second attempt to play the sound file, which never manages to play in the first place
# maybe this will be fine using phonon instead of qsound?

# TODO: allow app to respond to ctrl+c interrupts

# TODO: fix the alert not working on windows 10

# TODO: tune parameters

# TODO: respond to changes in config on the fly
# TODO: add in-app configuration / credits
	# be sure to undo the divison of interval by successfactor if changes are saved while the program isn't active

# TODO: do code review and cleanup

# TODO: double check GPLv3 requirements at https://tldrlegal.com/license/gnu-general-public-license-v3-%28gpl-3%29

# TODO: license considerations for icon
# TODO: version numbering

# Cobbled together with help from http://zetcode.com/gui/pyqt4/ , StackOverflow, and the Python documentation.
# Windows build made with pyinstaller (https://github.com/pyinstaller/pyinstaller/wiki).
# Also uses:
	# appdirs (https://pypi.python.org/pypi/appdirs), licensed under the BSD license
	# configobj (https://pypi.python.org/pypi/configobj), licensed under the MIT license
	# PyQt4 (https://www.riverbankcomputing.com/software/pyqt/download), licensed under GPLv3

# Bell sound modified from fauxpress's "Bell Meditation.mp3",
# taken from https://www.freesound.org/people/fauxpress/sounds/42095/
# under the Creative Commons 0 License.

# Icon taken from the film "1984" (1984).

import collections
import os
import random as rng
import sys
import threading

import appdirs
from configobj import ConfigObj, ParseError
from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4.phonon import Phonon

appname = "Stognastic"

# cast or fallback on a default value
# from http://stackoverflow.com/a/6330109
def safe_cast(val, to_type, default=None):
    try:
    	if to_type != bool:
        	return to_type(val)
        else:
        	return str(val).lower() == 'true'
    except ValueError:
        return default

class NagWidget(QtGui.QWidget):

	config_file_path = 'config.ini'

	# default configuration
	# will be overridden if config.ini is present
	config = collections.OrderedDict()
	config['interval'] = 30.
	config['successfactor'] = 1.1
	config['failfactor'] = 0.75
	config['minabsinterval'] = 15.
	config['minrelinterval'] = 0.5
	config['audioalertvol'] = 100
	config['audiopath'] = 'bell.wav'
	config['taskbaralert'] = True
	config['flashalert'] = True
	config['flashcolor'] = '#96deff'
	config['startmsg'] = 'Are you ready to maintain your posture?'
	config['query'] = 'Did you remember to maintain good posture?'
	config['goodmsg'] = 'Good. Stay vigilant for the next %s'
	config['badmsg'] = 'Hmph. Try to manage for %s'

	def __init__(self, app):
		super(NagWidget, self).__init__()
		self.app = app

		self.bgthread = None

		# load options from file
		try:
			self.loadConfig()
		except ParseError:
			print "Couldn't parse configuration file `" + self.config_file_path + "`. Using default configuration."

		self.config['interval'] /= self.config['successfactor'] # negate effect of first 'yes' when user starts program

		# important to set this as a self.___ property else it gets accidentally garbage collected...
		self.audio_output = Phonon.AudioOutput(Phonon.NotificationCategory)
		self.audio_output.setVolume(self.config['audioalertvol'] / 100.)
		self.bellsound = Phonon.MediaObject()
		Phonon.createPath(self.bellsound, self.audio_output)
		self.bellsound.setCurrentSource(Phonon.MediaSource(self.config['audiopath']))

		self.initUI()

	def loadConfig(self):
		# first, try to intelligently choose where config file is
		# it could be in the same directory as the script, or in the user profile
		# CWD is the default, but if profile has an existing config, or CWD is not writable, then switch
		
		# use filename provided on command-line instead of config.ini, if specified
		if len(sys.argv) > 1:
			if len(sys.argv) > 2:
				print "Note that all command-line arguments besides the first will be ignored."
			# goofy safety mechanism from http://stackoverflow.com/q/9532499
			if os.access(sys.argv[1], os.W_OK):
				self.config_file_path = sys.argv[1]
			else:
				try:
					open(sys.argv[1], 'w').close()
					os.unlink(sys.argv[1])
					self.config_file_path = sys.argv[1]
				except (OSError, IOError):
					print "Could not use " + sys.argv[1] + " as a configuration file."

		# test write capabilities
		cwdwritable = True
		try:
			fp = open(self.config_file_path, 'a')
		except IOError as e:
			cwdwritable = False
		else:
			fp.close()

		profiledir = appdirs.user_data_dir(appname, False, roaming=True)
		profileconf = profiledir + os.path.sep + self.config_file_path
		self.save_conf = True # if this is unset, configuration will not be saved at all

		if os.path.isfile(profileconf) or not cwdwritable:
			self.config_file_path = profileconf
			try:
				if not os.path.exists(profiledir):
					os.makedirs(profiledir)
			except:
				self.save_conf = False

		if self.save_conf:
			print "Using", os.path.abspath(self.config_file_path), "as configuration file."
			# test if the config file we chose is even writable
			try:
				fp = open(self.config_file_path, 'a')
			except IOError as e:
				self.save_conf = False
			else:
				fp.close()

		if not self.save_conf:
			print "There was a problem writing to the configuration file. Please ensure that it is possible to write to config.ini either in the same directory as Stognastic, or in " + profileconf

		if len(sys.argv) == 1:
			print "Note that alternate configuration files can be used. Just specify the path to the desired configuration file as a command-line argument when running the program."

		config_in = ConfigObj(self.config_file_path)
		# cast to the proper type if possible based on the default configuration,
		# and fall back on default values if something is unspecified or invalidly specified
		for key, value in self.config.items():
			self.config[key] = safe_cast(config_in.get(key, value), type(value), value)

		# fix volume to sane levels, between 0 and 100%
		self.config['audioalertvol'] = max(min(self.config['audioalertvol'], 100), 0)

		# fix malformed format strings to have either one or zero instances of '%s', and not other tokens
		# rather than parsing, it just does simple replacements, so it can still be defeated by pathological cases
		remove_placeholder = lambda s: s.replace('%s', '').replace('%%', '%').replace('%', '%%')
		def clean_formatstr(msg):
			placeholder = msg.find('%s')
			if placeholder > -1:
				return remove_placeholder(msg[0:placeholder]) + '%s' + remove_placeholder(msg[placeholder+2:])
			else:
				return remove_placeholder(msg)
		self.config['goodmsg'] = clean_formatstr(self.config['goodmsg'])
		self.config['badmsg'] = clean_formatstr(self.config['badmsg'])


	def saveConfig(self):
		if not self.save_conf:
			return

		config_out = ConfigObj()
		config_out.filename = self.config_file_path

		for key, value in self.config.items():
			config_out[key] = value

		config_out.write()

	def initUI(self):
		# message
		self.lblMessage = QtGui.QLabel(self.config['startmsg'])

		# yes button
		self.ybtn = QtGui.QPushButton('Yes', self)
		self.ybtn.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Y))
		self.ybtn.clicked.connect(self.yesClick)
		self.ybtn.resize(self.ybtn.sizeHint())

		# no button
		self.nbtn = QtGui.QPushButton('No', self)
		self.nbtn.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_N))
		self.nbtn.clicked.connect(self.noClick)
		self.nbtn.resize(self.nbtn.sizeHint())
		self.nbtn.setStyleSheet("QPushButton { color : red; }")
		self.nbtn.setEnabled(False)

		# layout container stuff
		# top level is a vbox containing the message label, and an hbox which holds both buttons
		buttonbox = QtGui.QHBoxLayout()
		buttonbox.addWidget(self.ybtn)
		buttonbox.addWidget(self.nbtn)
		vbox = QtGui.QVBoxLayout()
		vbox.addWidget(self.lblMessage)
		vbox.addLayout(buttonbox)

		# final window setup
		self.setLayout(vbox)

		self.resize(self.sizeHint())
		self.setWindowTitle('Stognastic')
		self.setWindowIcon(QtGui.QIcon('icons/1984-96.png')) 

		self.show()

	# increase base interval, give user a time estimate, then lock the interface
	def yesClick(self):
		self.config['interval'] = max(self.config['interval']*self.config['successfactor'], self.config['minabsinterval'])
		self.saveConfig()

		if self.config['goodmsg'].find('%s') > -1:
			self.lblMessage.setText(self.config['goodmsg'] % self.formatTime(self.config['interval']))
		else:
			self.lblMessage.setText(self.config['goodmsg'] % ())
		
		self.disableInterface()

	# decrease base interval, give user a time estimate, then lock the interface
	def noClick(self):
		self.config['interval'] = max(self.config['interval']*self.config['failfactor'], self.config['minabsinterval'])
		self.saveConfig()

		if self.config['badmsg'].find('%s') > -1:
			self.lblMessage.setText(self.config['badmsg'] % self.formatTime(self.config['interval']))
		else:
			self.lblMessage.setText(self.config['badmsg'] % ())

		self.disableInterface()

	# make string containing time estimate with appropriate units
	def formatTime(self, seconds):
		seconds = max(seconds, self.config['minabsinterval'])

		value = 0
		message = ""
		if seconds / 60 < 1:
			value = int(round(seconds))
			message = str(value) + " second"
		elif seconds / 3600 < 1:
			value = int(round(seconds / 60.))
			message = str(value) + " minute"
		else:
			value = int(round(seconds / 3600.))
			message = str(value) + " hour"

		# fix plural
		if value > 1:
			return message + "s."
		
		return message + "."

	# shut down the interface for the next time interval
	def disableInterface(self):
		# shut down previous countdown/animation
		if not self.bgthread is None:
			self.bgthread.cancel()
			self.anim_cancel.set()

		self.ybtn.setEnabled(False)
		self.nbtn.setEnabled(False)

		actual_interval = self.pickInterval()

		print "Actual interval:", actual_interval

		self.anim_cancel = threading.Event()
		self.bgthread = threading.Timer(actual_interval, self.enableInterface)
		self.anim_cancel.clear()
		self.bgthread.start()

	# pick an appropriate time interval, based on various options and constraints
	def pickInterval(self):
		# pick a random number (raising it to a power < 1o favour numbers closer to 1 over numbers closer to 0)
		rn = rng.random() ** 0.75

		# make sure it's larger than the minrelinterval
		fraction = rn * (1. - self.config['minrelinterval']) + self.config['minrelinterval']

		return max(self.config['interval'] * fraction, self.config['minabsinterval'])

	# re-enable interface and pester user to respond
	def enableInterface(self):
		# cache current flag to avoid conflicts when stopping one timer and starting another
		flag = self.anim_cancel

		self.lblMessage.setText(self.config['query'])
		self.ybtn.setEnabled(True)
		self.nbtn.setEnabled(True)
		if self.config['taskbaralert']:
			self.app.alert(self)

		# reset state of media file before playing again
		self.bellsound.stop()
		self.bellsound.play()

		# play basic visual animation until the termination flag is set
		while True:
			if self.config['flashalert']:
				QtCore.QMetaObject.invokeMethod(self, 'flash_bg', QtCore.Qt.QueuedConnection)
				flag.wait(0.5)
				QtCore.QMetaObject.invokeMethod(self, 'blank_bg', QtCore.Qt.QueuedConnection)
				
				if flag.is_set(): # respond to termination while background colour is neutral
					break

				flag.wait(0.5)

			if flag.is_set(): # respond to termination while background colour is neutral
				break

			# more pestering if the user minimizes the window again
			if self.config['taskbaralert']:
				self.app.alert(self)

	# set the window background color to a specific shade as a visual cue
	@QtCore.pyqtSlot()
	def flash_bg(self):
		self.setStyleSheet("background-color: " + self.config['flashcolor'] + ";");

	# clear the window background color
	@QtCore.pyqtSlot()
	def blank_bg(self):
		self.setStyleSheet("");
		
	# clean up any timers still running when we close the window
	def closeEvent(self, event):
		if not self.bgthread is None:
			self.bgthread.cancel()
			self.anim_cancel.set()

def main():
	# set CWD to the script's directory, since we are assuming audio files, icon, (and maybe the config) are there
	os.chdir(os.path.dirname(os.path.realpath(sys.argv[0])))
	app = QtGui.QApplication(sys.argv)
	ex = NagWidget(app)

	sys.exit(app.exec_())

if __name__ == '__main__':
	main()