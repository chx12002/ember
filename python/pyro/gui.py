#!/usr/bin/env python

import sys
import threading
import numpy as np
from PySide import QtGui, QtCore
import utils
import input
import pyro
import time

import matplotlib
matplotlib.rcParams['backend.qt4'] = 'PySide'
matplotlib.use('Qt4Agg')
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class SolverThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self)
        self.solver = kwargs['solver']
        self.conf = kwargs['conf']
        self.solver.lock = threading.Lock()
        self.solver.progress = 0.0
        self._stop = False
        self.daemon = True
        self.stage = 0

        self.frac0 = 0.15

    def run(self):
        done = 0
        i = 0
        while not self._stop and not done:
            i += 1
            with self.solver.lock:
                done = self.solver.step()
            time.sleep(1e-4)
            if not i % 5:
                self.updateProgress()
            if done:
                self.solver.progress = 1.0
        self._stop = True

    def stop(self):
        self._stop = True

    def updateProgress(self):
        TC = self.conf.terminationCondition
        errNow = self.solver.terminationCondition
        if TC.measurement is None:
            self.solver.progress = self.solver.timeVector[-1] / TC.tEnd
        elif self.stage == 0:
            # First part: getting past the minimum steady-state measurement period
            self.solver.progress = self.frac0 * self.solver.timeVector[-1] / TC.steadyPeriod
            if errNow < 1e9:
                self.refCond = errNow
                self.stage = 1
        else:
            # Second part: vaguely linearizing the approach to steady-state
            A = (np.log10(TC.tolerance + (errNow-TC.tolerance)/self.refCond) /
                 np.log10(TC.tolerance))
            P = min(self.frac0 + (1-self.frac0) * A ** 0.5 , 1.0)
            self.solver.progress = max(P, self.solver.progress) # never go backwards

class OptionWidget(QtGui.QWidget):
    def __init__(self, label, opt, *args, **kwargs):
        QtGui.QWidget.__init__(self)

        self.opt = opt
        self.label = label
        self.optName = self.label.text()
        self.setLayout(QtGui.QHBoxLayout())
        self.layout().setContentsMargins(0,0,0,0)

    def checkDefault(self):
        if self.opt.value != self.opt.default:
            self.label.setText('<i>%s</i>' %  self.optName)
        else:
            self.label.setText('%s' %  self.optName)


class StringOptionWidget(OptionWidget):
    def __init__(self, label, opt, *args, **kwargs):
        OptionWidget.__init__(self, label, opt)
        self.text = QtGui.QLineEdit(opt.value)
        self.layout().addWidget(self.text)
        self.text.textChanged.connect(self.updateOpt)

    def updateOpt(self):
        self.opt.value = str(self.text.text())
        self.checkDefault()


class NumericOptionWidget(OptionWidget):
    def __init__(self, label, opt, *args, **kwargs):
        OptionWidget.__init__(self, label, opt)
        self.text = QtGui.QLineEdit(str(opt.value))
        self.layout().addWidget(self.text)
        self.text.textChanged.connect(self.updateOpt)

    def updateOpt(self):
        try:
            self.opt.value = float(self.text.text())
        except ValueError:
            pass
        self.checkDefault()


class IntegerOptionWidget(NumericOptionWidget):
    def updateOpt(self):
        try:
            self.opt.value = int(self.text.text())
        except ValueError:
            pass
        self.checkDefault()


class BoolOptionWidget(OptionWidget):
    def __init__(self, label, opt, *args, **kwargs):
        OptionWidget.__init__(self, label, opt)

        self.trueWidget = QtGui.QRadioButton('True')
        self.falseWidget = QtGui.QRadioButton('False')
        if opt.value:
            self.trueWidget.toggle()
        else:
            self.falseWidget.toggle()
        self.layout().addWidget(self.trueWidget)
        self.layout().addWidget(self.falseWidget)

        self.trueWidget.toggled.connect(self.updateOpt)
        self.layout().addStretch(1)

    def updateOpt(self):
        self.opt.value = self.trueWidget.isChecked()
        self.checkDefault()


class EnumOptionWidget(OptionWidget):
    def __init__(self, label, opt, *args, **kwargs):
        OptionWidget.__init__(self, label, opt)

        self.combo = QtGui.QComboBox()
        self.items = {}
        for i,choice in enumerate(opt.choices):
            if choice == opt.value:
                startIndex = i

            self.combo.addItem(str(choice))
            self.items[i] = choice

        self.combo.setCurrentIndex(startIndex)
        self.layout().addWidget(self.combo)
        self.combo.currentIndexChanged.connect(self.updateOpt)

    def updateOpt(self):
        self.opt.value = self.items[self.combo.currentIndex()]
        self.checkDefault()


class OptionsWidget(QtGui.QGroupBox):
    def __init__(self, opts, *args, **kwargs):
        QtGui.QGroupBox.__init__(self)
        self.opts = opts
        self.setLayout(QtGui.QGridLayout())
        self.layout().setSpacing(0)
        self.setTitle(self.opts.__class__.__name__)

        width = 0
        for i,(name,opt) in enumerate(self.opts):
            label = QtGui.QLabel(name)
            self.layout().addWidget(label, i, 0)
            width = max(label.sizeHint().width(), width)

            if opt.choices is not None:
                w = EnumOptionWidget(label, opt)
            elif isinstance(opt, input.StringOption):
                w = StringOptionWidget(label, opt)
            elif isinstance(opt, input.IntegerOption):
                w = IntegerOptionWidget(label, opt)
            elif isinstance(opt, input.FloatOption):
                w = NumericOptionWidget(label, opt)
            elif isinstance(opt, input.BoolOption):
                w = BoolOptionWidget(label, opt)
            else:
                w = QtGui.QLabel(str(opt.value))

            self.layout().addWidget(w, i, 1)

        self.layout().setVerticalSpacing(4)
        self.layout().setColumnMinimumWidth(0, width + 5)
        spacer = QtGui.QSpacerItem(1, 1000, QtGui.QSizePolicy.Minimum,
                                   QtGui.QSizePolicy.Maximum)
        self.layout().addItem(spacer, i+1, 0)


class MultiOptionsWidget(QtGui.QWidget):
    """ Widget used for presenting solver configuration options """
    def __init__(self, conf, *args, **kwargs):
        QtGui.QWidget.__init__(self)
        self.conf = conf
        self.setLayout(QtGui.QHBoxLayout())
        self.optionsList = QtGui.QListWidget()
        self.optionsList.setSpacing(1)
        self.layout().addWidget(self.optionsList)
        self.activeOptionWidget = None

        height = 0
        for item in self.conf:
            listitem = QtGui.QListWidgetItem(item.__class__.__name__)
            self.optionsList.addItem(listitem)
            w = OptionsWidget(item)
            height = max(height, w.minimumSizeHint().height())
            listitem.widget = w
            self.layout().addWidget(w)
            w.hide()

        self.optionsList.setCurrentRow(0)
        self.setActiveWidget(self.optionsList.currentItem())
        self.setMinimumHeight(height)
        width = self.optionsList.sizeHintForColumn(0) + 5
        self.optionsList.setMinimumWidth(width)
        self.optionsList.setMaximumWidth(width)
        self.optionsList.currentItemChanged.connect(self.setActiveWidget)
        self.optionsList.setSizePolicy(QtGui.QSizePolicy.Fixed,
                                       QtGui.QSizePolicy.Preferred)

    def setActiveWidget(self, listitem):
        if self.activeOptionWidget is not None:
            self.activeOptionWidget.hide()

        self.activeOptionWidget = listitem.widget
        self.activeOptionWidget.show()

class SolverWidget(QtGui.QWidget):
    """ Widget used to run and monitor the Pyro solver """
    def __init__(self, conf, *args, **kwargs):
        QtGui.QWidget.__init__(self)

        self.conf = conf
        self.setLayout(QtGui.QVBoxLayout())

        # Buttons
        self.startButton = QtGui.QPushButton('Start')
        self.pauseButton = QtGui.QPushButton('Pause')
        self.stopButton = QtGui.QPushButton('Stop')
        self.buttons = QtGui.QWidget()
        self.buttons.setLayout(QtGui.QHBoxLayout())
        self.buttons.layout().addWidget(self.startButton)
        self.buttons.layout().addWidget(self.pauseButton)
        self.buttons.layout().addWidget(self.stopButton)
        self.layout().addWidget(self.buttons)

        self.startButton.pressed.connect(self.run)
        self.pauseButton.pressed.connect(self.pause)
        self.stopButton.pressed.connect(self.stop)

        # Progress Bar
        self.progressBar = QtGui.QProgressBar()
        self.layout().addWidget(self.progressBar)
        self.progressBar.setRange(0, 1000)
        self.progressBar.setValue(0)

        # Graphs
        self.graphContainer = QtGui.QWidget()
        self.graphContainer.setLayout(QtGui.QHBoxLayout())
        self.layout().addWidget(self.graphContainer)

        self.fig = Figure(figsize=(600,400), dpi=72)
        self.ax1 = self.fig.add_subplot(1,2,1)
        self.Sc_timeseries = self.ax1.plot([0],[0], lw=2)[0]

        self.ax2a = self.fig.add_subplot(1,2,2)
        self.ax2b = self.ax2a.twinx()

        self.T_profile = self.ax2a.plot([0],[0], 'b', lw=2)[0]
        self.hrr_profile = self.ax2b.plot([0],[0], 'r', lw=2)[0]

        self.canvas = FigureCanvas(self.fig)
        self.graphContainer.layout().addWidget(self.canvas)
        bgcolor = self.palette().color(QtGui.QPalette.Window)
        self.fig.set_facecolor((bgcolor.redF(), bgcolor.greenF(), bgcolor.blueF()))
        #self.fig.patch.set_alpha(0.1)

        # internals
        self.solver = None
        self.solverThread = None
        self.updateTimer = QtCore.QTimer()
        self.updateTimer.setInterval(0.2)
        self.updateTimer.timeout.connect(self.updateStatus)

    def run(self):
        if self.solverThread is not None and self.solverThread.is_alive():
            return

        if self.solver is None:
            self.conf.validate()
            self.conf.setup()
            self.solver = pyro.FlameSolver(self.conf)
            self.solver.initialize()

        self.solverThread = SolverThread(solver=self.solver,
                                         conf=self.conf)
        self.solverThread.start()
        self.updateTimer.start()

    def pause(self):
        if not self.solverThread:
            return

        if not self.solverThread.is_alive():
            self.pauseButton.setText('Pause')
            self.run()
            self.updateTimer.start()
        else:
            self.pauseButton.setText('Continue')
            self.solverThread.stop()
            self.updateTimer.stop()

    def stop(self):
        if self.solverThread:
            self.solverThread.stop()
            self.updateTimer.stop()

    def updateStatus(self):
        if not self.solver:
            return

        if not self.solverThread.is_alive():
            self.updateTimer.stop()

        self.progressBar.setValue(1000 * self.solver.progress)
        with self.solver.lock:
            self.Sc_timeseries.set_data(self.solver.timeVector,
                                        self.solver.consumptionSpeed)
            self.T_profile.set_data(self.solver.grid.x,
                                    self.solver.T)
            self.hrr_profile.set_data(self.solver.grid.x,
                                      self.solver.qDot)

        for ax in (self.ax1, self.ax2a, self.ax2b):
            ax.relim()
            ax.autoscale_view(False, True, True)
        self.canvas.draw()


class MainWindow(QtGui.QMainWindow):
    def __init__(self, *args, **kwargs):
        QtGui.QMainWindow.__init__(self)

        w = QtGui.QWidget()
        self.setCentralWidget(w)
        self.resize(800,600)
        self.setWindowTitle('Simple')

        fileMenu = self.menuBar().addMenu('&File')
        a = QtGui.QAction('&New', self)
        a.triggered.connect(lambda: self.newConf())
        fileMenu.addAction(a)

        a = QtGui.QAction('&Quit', self)
        a.triggered.connect(self.close)
        fileMenu.addAction(a)

        self.new()

    def new(self):
        self.conf = input.Config(input.Paths(logFile='gui-runlog.txt'))

        self.tabWidget = QtGui.QTabWidget()
        self.setCentralWidget(self.tabWidget)

        self.confWidget = MultiOptionsWidget(self.conf)
        self.tabWidget.addTab(self.confWidget, 'Configure')

        self.runWidget = SolverWidget(self.conf)
        self.tabWidget.addTab(self.runWidget, 'Run')
        self.tabWidget.addTab(QtGui.QWidget(), 'Analyze') #TODO: unimplemented


def main():
    app = QtGui.QApplication(sys.argv)
    window = MainWindow()
    window.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()