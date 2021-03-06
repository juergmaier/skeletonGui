

import os

from PyQt5.QtCore import pyqtSlot, QThreadPool
from PyQt5 import uic, QtWidgets
from PyQt5.QtWidgets import QMainWindow, QFileDialog

import config
import marvinglobal.marvinglobal as mg
import servoGuiUpdate
#import servoDefinitionGui
import detailGuiLogic


sliderInMove = None

def servoNameFromFunctionName(functionNameParts):

    return f"{functionNameParts[1]}.{functionNameParts[2].replace('Slider', '')}"


def getValueFunctionFromFunctionName(functionNameParts):

    sliderGetValueFunction = f"self.{functionNameParts[1]}_{functionNameParts[2]}.value()"
    return sliderGetValueFunction

''' 14.10.2020 jm should be obsolete with shared servo data
def addValueChangedFunctionToClass(functionName, cls):
    """
    add a dynamically named function to the class
    as this function is triggerd in high frequency when the slider is pressed down
    the arduino.requestServoPosition has a built in filter to avoid too many repositions
    in addition the refresh of the slider position is suppressed when the slider is pressed
    (implemented in config.SERVO_UPDATE section)
    :param name:
    :param cls:
    :return:
    """
    # retrieve the servos name from the function name
    servoName = servoNameFromFunctionName(functionName.split('_'))

    def fn(self, position):

        config.log(f"on_valueChanged, servoName: {servoName}, position: {position}")

        arduinoSend.requestServoPosition(servoName, position, 500)


    # add the function to the class
    setattr(cls, functionName, fn)
'''

def addSliderReleasedFunctionToClass(functionName, cls):
    """
    this adds dynamically an on_<slider>_sliderRelease function to the referenced class
    I use it to allow controlling the servos with the below-button sliders
    On release of the button the current value of the slider gets evaluated
    Works only when slider names follow the same naming rules
    slidername = <servo_Name>Slider
    :param functionName:
    :param cls:
    :return:
    """

    nameParts = functionName.split('_')
    servoName = servoNameFromFunctionName(nameParts)
    sliderGetValueFunction = getValueFunctionFromFunctionName(nameParts)

    def fn(self):

        # get value of the slider through the slider get value function name
        position = eval(sliderGetValueFunction)

        config.log(f"sliderReleased, servoName: {servoName}, position: {position}")

        # do not filter on sliderRelease request as it is the final position of the slider
        #arduinoSend.requestServoPosition(servoName, position, 500, filterSequence=False)
        config.md.servoRequestQueue.put()

    # add the function to the class
    setattr(cls, functionName, fn)


class SkeletonGui(QMainWindow):

    prevSelectedServoButton = None
    selectedServoName = None
    selectedServoType = None
    selectedServoDerived = None
    selectedServoCurrent = None
    minCommentCenter = 0
    maxCommentCenter = 0

    def __init__(self, *args, **kwargs):

        #QtWidgets.QDialog.__init__(self, *args, **kwargs)
        #self.setupUi(self)
        #super(SkeletonGui, self).__init__()
        super().__init__()

        uic.loadUi('skeletonGui.ui', self)

        # add on_valueChanged and on_sliderReleased functions
        # for all servo sliders below the buttons
        for servoName in config.md.servoStaticDict.keys():
            sliderName = servoName.replace('.', '_') + 'Slider'
            #addValueChangedFunctionToClass(f'on_{sliderName}_valueChanged', SkeletonGui)
            addSliderReleasedFunctionToClass(f'on_{sliderName}_sliderReleased', SkeletonGui)

        self.servoNameFormat = "<html><head/><body><p align=\"center\"><span style=\" font-size:10pt;\">ServoName</span></p></body></html>"

        self.threadpool = QThreadPool()
        self.threads = []

        # start thread for requested gui updates
        config.log("guiLogic.init, adding thread for handling gui updates")
        servoUpdateThread = servoGuiUpdate.GuiUpdateThread()

        servoUpdateThread.signals.updateArduino.connect(self.updateGuiArduino)
        servoUpdateThread.signals.updateServo.connect(self.updateGuiServo)
        servoUpdateThread.signals.updateProcess.connect(self.updateGuiProcess)

        self.threadpool.start(servoUpdateThread)

        # update arduino and servo state
        config.md.guiUpdateQueue.put({'type': 'dummy'})  # first message gets lost somehow
        for arduinoIndex, arduinoData in config.md.arduinoDict.items():
            info = {'type': 'arduinoUpdate', 'arduino': arduinoIndex, 'connected': arduinoData['connected']}
            config.log(f"request arduino update in gui: {info}")
            config.md.guiUpdateQueue.put(info)

        for servoName in config.md.servoStaticDict.keys():
            config.md.guiUpdateQueue.put({'type': 'servoUpdate', 'servoName': servoName})

        #        gesturePlay = i01.GesturePlay()
#        self.threadpool.start(gesturePlay)

#        i01.mouth.speakBlocking("ich bin jetzt bereit")
        config.startupDone = True

        self.minCommentCenter = self.minComment.geometry().center().x()
        self.maxCommentCenter = self.maxComment.geometry().center().x()

        # comboBox for special functions
        self.specialFunctions.addItem("capture reference face")
        self.specialFunctions.activated[str].connect(self.specialFunctionSelected)

        self.show()


    def specialFunctionSelected(self, text):
        config.log(f"specialFunction selected {text}")

        if text == "capture reference face":
            #success = eyeCamFunctions.newFaceRecording()
            config.md.imageProcessingQueue.put('newFaceRecording')


    @classmethod
    def clearLastSelectedServoButton(self):
        if self.prevSelectedServoButton is not None:
            self.prevSelectedServoButton.setStyleSheet("background-color: lightGray; color: black;")
        self.prevSelectedServoButton = None

    @classmethod
    def setSelectedServo(self, button, servoName):
        if self.prevSelectedServoButton is not None:
            self.clearLastSelectedServoButton()
        self.prevSelectedServoButton = button
        self.selectedServoName = servoName


    def showButtonActivated(self, button, servoName):
        '''
        Mark the selected servo button
        :param button: saved as "prevSelectedButton to undo selection
        :param servoName:
        :return:
        '''
        # user pressed the already selected servo, ignore
        if servoName == self.selectedServoName:
            return

        # if we have a previous selected button reset its color
        if self.prevSelectedServoButton is not None:
            self.prevSelectedServoButton.setStyleSheet("background-color: lightGray; color: black;")

        # show the current selected servo button in green
        button.setStyleSheet("background-color: green; color: white;")
        self.setSelectedServo(button, servoName)


    @pyqtSlot()
    def on_head_eyeY_clicked(self):
        self.showButtonActivated(self.head_eyeY, 'head.eyeY')
        self.setServoGuiValues('head.eyeY')

    @pyqtSlot()
    def on_head_eyeX_clicked(self):
        config.log(f"head_eyeX_clicked")
        self.showButtonActivated(self.head_eyeX, 'head.eyeX')
        self.setServoGuiValues('head.eyeX')

    @pyqtSlot()
    def on_head_jaw_clicked(self):
        self.showButtonActivated(self.head_jaw, 'head.jaw')
        self.setServoGuiValues('head.jaw')

    @pyqtSlot()
    def on_head_rothead_clicked(self):
        self.showButtonActivated(self.head_rothead, 'head.rothead')
        self.setServoGuiValues('head.rothead')

    @pyqtSlot()
    def on_head_neck_clicked(self):
        self.showButtonActivated(self.head_neck, 'head.neck')
        self.setServoGuiValues('head.neck')

    # left shoulder
    @pyqtSlot()
    def on_leftArm_rotate_clicked(self):
        self.showButtonActivated(self.leftArm_rotate, 'leftArm.rotate')
        self.setServoGuiValues('leftArm.rotate')

    @pyqtSlot()
    def on_leftArm_shoulder_clicked(self):
        self.showButtonActivated(self.leftArm_shoulder, 'leftArm.shoulder')
        self.setServoGuiValues('leftArm.shoulder')

    @pyqtSlot()
    def on_leftArm_omoplate_clicked(self):
        self.showButtonActivated(self.leftArm_omoplate, 'leftArm.omoplate')
        self.setServoGuiValues('leftArm.omoplate')

    @pyqtSlot()
    def on_leftArm_bicep_clicked(self):
        self.showButtonActivated(self.leftArm_bicep, 'leftArm.bicep')
        self.setServoGuiValues('leftArm.bicep')


    # right shoulder
    @pyqtSlot()
    def on_rightArm_rotate_clicked(self):
        self.showButtonActivated(self.rightArm_rotate, 'rightArm.rotate')
        self.setServoGuiValues('rightArm.rotate')

    @pyqtSlot()
    def on_rightArm_shoulder_clicked(self):
        self.showButtonActivated(self.rightArm_shoulder, 'rightArm.shoulder')
        self.setServoGuiValues('rightArm.shoulder')

    @pyqtSlot()
    def on_rightArm_omoplate_clicked(self):
        self.showButtonActivated(self.rightArm_omoplate, 'rightArm.omoplate')
        self.setServoGuiValues('rightArm.omoplate')

    @pyqtSlot()
    def on_rightArm_bicep_clicked(self):
        self.showButtonActivated(self.rightArm_bicep, 'rightArm.bicep')
        self.setServoGuiValues('rightArm.bicep')

    # left hand
    @pyqtSlot()
    def on_leftHand_thumb_clicked(self):
        self.showButtonActivated(self.leftHand_thumb, 'leftHand.thumb')
        self.setServoGuiValues('leftHand.thumb')

    @pyqtSlot()
    def on_leftHand_index_clicked(self):
        self.showButtonActivated(self.leftHand_index, 'leftHand.index')
        self.setServoGuiValues('leftHand.index')

    @pyqtSlot()
    def on_leftHand_majeure_clicked(self):
        self.showButtonActivated(self.leftHand_majeure, 'leftHand.majeure')
        self.setServoGuiValues('leftHand.majeure')

    @pyqtSlot()
    def on_leftHand_ringFinger_clicked(self):
        self.showButtonActivated(self.leftHand_ringFinger, 'leftHand.ringFinger')
        self.setServoGuiValues('leftHand.ringFinger')

    @pyqtSlot()
    def on_leftHand_pinky_clicked(self):
        self.showButtonActivated(self.leftHand_pinky, 'leftHand.pinky')
        self.setServoGuiValues('leftHand.pinky')

    @pyqtSlot()
    def on_leftHand_wrist_clicked(self):
        self.showButtonActivated(self.leftHand_wrist, 'leftHand.wrist')
        self.setServoGuiValues('leftHand.wrist')

    # right hand
    @pyqtSlot()
    def on_rightHand_thumb_clicked(self):
        self.showButtonActivated(self.rightHand_thumb, 'rightHand.thumb')
        self.setServoGuiValues('rightHand.thumb')

    @pyqtSlot()
    def on_rightHand_index_clicked(self):
        self.showButtonActivated(self.rightHand_index, 'rightHand.index')
        self.setServoGuiValues('rightHand.index')

    @pyqtSlot()
    def on_rightHand_majeure_clicked(self):
        self.showButtonActivated(self.rightHand_majeure, 'rightHand.majeure')
        self.setServoGuiValues('rightHand.majeure')

    @pyqtSlot()
    def on_rightHand_ringFinger_clicked(self):
        self.showButtonActivated(self.rightHand_ringFinger, 'rightHand.ringFinger')
        self.setServoGuiValues('rightHand.ringFinger')

    @pyqtSlot()
    def on_rightHand_pinky_clicked(self):
        self.showButtonActivated(self.rightHand_pinky, 'rightHand.pinky')
        self.setServoGuiValues('rightHand.pinky')

    @pyqtSlot()
    def on_rightHand_wrist_clicked(self):
        self.showButtonActivated(self.rightHand_wrist, 'rightHand.wrist')
        self.setServoGuiValues('rightHand.wrist')

    # torso
    @pyqtSlot()
    def on_torso_topStom_clicked(self):
        self.showButtonActivated(self.torso_topStom, 'torso.topStom')
        self.setServoGuiValues('torso.topStom')


    @pyqtSlot()
    def on_torso_midStom_clicked(self):
        self.showButtonActivated(self.torso_midStom, 'torso.midStom')
        self.setServoGuiValues('torso.midStom')


    def on_stopServo_clicked(self):
        #rpcSend.requestServoStop(self.selectedServoName)
        config.sc.stop(config.md.servoRequestQueue, self.selectedServoName)
        #arduinoSend.requestServoStop(self.selectedServoName)
        #if config.swipingServoName is not None:
        #    self.stopSwiping()


    def on_MoveServo_pressed(self):
        #config.log(f"on_Move_Servo_pressed")
        if self.MoveServo.text() == "Move":
            self.MoveServo.setText("Stop")
            position = self.RequestPositionSlider.value()
            duration = self.DurationSlider.value()
            config.log(f"requestServoPos, servoName: {self.selectedServoName}, position: {position}, duration: {duration}")
            #arduinoSend.requestServoPosition(self.selectedServoName, position, duration)
            config.sc.positionServo(config.md.servoRequestQueue, self.selectedServoName, position, duration)

        else:
            config.log(f"requestServoStop, servoName: {self.selectedServoName}")
            #arduinoSend.requestServoStop(self.selectedServoName)
            config.sc.stop(config.md.servoRequestQueue, self.selectedServoName)
            self.MoveServo.setText("Move")


    def on_Modify_pressed(self):

        # open detail dialog
        _ = QtWidgets.QDialog()
        dialog = detailGuiLogic.detailGui()
        dialog.initUI(self.selectedServoName)
        dialog.exec_()
        dialog.show()

        # after closing the dialog update the servo values in the main window
        self.setServoGuiValues(self.selectedServoName)


    def on_Rest_pressed(self):
        servoStatic: mg.ServoStatic = config.md.servoStaticDict[self.selectedServoName]
        degrees = servoStatic.restDeg
        position = config.evalPosFromDeg(self.selectedServoName, degrees)
        config.log(f"requestRestPosition, servoName: {self.selectedServoName}, degrees: {degrees}, pos: {position}")
        #arduinoSend.requestServoPosition(self.selectedServoName, position, config.REST_MOVE_DURATION)
        config.sc.positionServo(config.md.servoRequestQueue, self.selectedServoName, position, config.REST_MOVE_DURATION)
        # set request position slider
        self.RequestPositionSlider.setValue(round(position))

    def adjustGuiForSwipingStart(self):
        self.SwipeServo.setText("Stop Swipe")
        self.MoveServo.setEnabled(False)
        self.Modify.setEnabled(False)
        self.Rest.setEnabled(False)

    def adjustGuiForSwipingEnd(self):
        self.SwipeServo.setText("Swipe")
        self.MoveServo.setEnabled(True)
        self.Modify.setEnabled(True)
        self.Rest.setEnabled(True)


    def on_SwipeServo_pressed(self):
        #config.swipingServoName = self.selectedServoName
        if self.SwipeServo.text() == "Swipe":
            config.log(f"start swipe for {self.selectedServoName}")
            self.adjustGuiForSwipingStart()
            config.sc.startSwipe(config.md.servoRequestQueue, self.selectedServoName)

        else:
            config.log(f"stop swipe for {self.selectedServoName}")
            config.sc.stopSwipe(config.md.servoRequestQueue, self.selectedServoName)
            self.adjustGuiForSwipingEnd()

    def stopSwiping(self):
        '''
        swiping stop can be requested trough the gui but also by stopping/rest requesting
        for a single or all servos
        swiping continuation is handled in arduino receive when a movement is finished and
        servoCurrent.swiping is True
        More then one servo might be in swiping mode
        '''
        for servoName, servoCurrent in config.md.servoCurrentDict.items():
            if servoCurrent.swiping:
                config.sc.stopSwipe(config.md.servoRequestQueue, servoName)
                if servoName == self.selectedServoName:
                    self.adjustGuiForSwipingEnd()


    def on_Verbose_stateChanged(self):
        verboseOn = self.Verbose.isChecked()

        config.log(f"requestSetVerbose, servoName: {self.selectedServoName}, verboseOn: {verboseOn}")
        #arduinoSend.setVerbose(self.selectedServoName, verboseOn)
        config.sc.setVerbose(config.md.servoRequestQueue, self.selectedServoName, verboseOn)


    def stopSelfRunningActivities(self):
        config.sc.stopRandomMoves(config.md.servoRequestQueue)
        config.sc.stopGesture(config.md.servoRequestQueue)
        config.sc.allServoStop(config.md.servoRequestQueue)


    def on_randomMoves_pressed(self):
        config.log(f"on_randomMoves_pressed")

        if not config.randomMovesActive:
            config.sc.startRandomMoves(config.md.servoRequestQueue)
            config.randomMovesActive = True
            '''
            self.stopSelfRunningActivities()
            randomMove = randomMoves.RandomMoves()
            self.threadpool.start(randomMove)      # calls run method of randomMoves.py

            self.randomMoves.setStyleSheet("background-color: green; color: white;")
            i01.mouth.speakBlocking("zufallsbewegungen aktiviert")
            '''
        else:
            config.randomMovesActive = False    # this stops the thread
            config.sc.stopRandomMoves(config.md.servoRequestQueue)

            #arduinoSend.requestAllServosRest()
            #config.sc.allServoRest(config.md.servoRequestQueue)
            self.randomMoves.setStyleSheet("background-color: lightGray; color: black;")
            #i01.mouth.speakBlocking("zufallsbewegungen beendet")


    def on_locateFaces_pressed(self):

        config.log(f"on_locateFaces_pressed, isFaceTrackingActive: {config.isFaceTrackingActive}")
        if not config.isFaceTrackingActive:

            config.md.imageProcessingQueue.put('startFaceTracking')
            config.isFaceTrackingActive = True
            config.log(f"face tracking and face recognition started")
            #faceTracking = eyeCamFunctions.FaceTracking()
            #faceRecognition = eyeCamFunctions.FaceRecognition(faceTracking)
            #recognizeFaces = eyeCamFunctions.RecognizeFaces(faceTracking)

            #self.threadpool.start(faceTracking)
            #self.threadpool.start(recognizeFaces)

            # increase autoDetach time to speed up eye movement during scan
            #arduinoSend.setAutoDetach('head.eyeX', 5000)
            config.sc.setAutoDetach(config.md.servoRequestQueue, 'head.eyeX', 5000)

            self.locateFaces.setStyleSheet("background-color: green; color: white;")
            #i01.mouth.speakBlocking("gesichtsverfolgung aktiviert")

        else:
            config.md.imageProcessingQueue.put('stopFaceTracking')
            config.isFaceTrackingActive = False
            config.log(f"face tracking and face recognition stopped")
            config.sc.setAutoDetach(config.md.servoRequestQueue, 'head.eyeX', 500)
            self.locateFaces.setStyleSheet("background-color: lightGray; color: black;")


    def on_stopAllServos_pressed(self):
        self.stopSelfRunningActivities()


    def on_restAll_pressed(self):
        self.stopSelfRunningActivities()
        #arduinoSend.requestAllServosRest()
        config.sc.allServoRest(config.md.servoRequestQueue)


    def on_playGesture_pressed(self):

        self.stopSelfRunningActivities()

        # open a file selection dialog
        folder = "c:/Projekte/InMoov/robotControl/marvinGestures"
        fileName = QFileDialog.getOpenFileName(self, 'Select Gesture', folder, "gesture (*.py)")
        if os.path.isfile(fileName[0]):
            config.gestureName = os.path.basename(fileName[0]).replace(".py","")
            config.log(f"gesture selected: {config.gestureName}")

            # this triggers the call of the gesture in the gesture thread (module i01)
            config.gestureRunning = True


    def on_RequestPositionSlider_sliderReleased(self):
        # position needs to be in range min/max
        servoStatic: mg.ServoStatic = config.md.servoStaticDict.get(self.selectedServoName)
        if self.RequestPositionSlider.value() < servoStatic.minPos:
            self.RequestPositionSlider.setValue(servoStatic.minPos)
        if self.RequestPositionSlider.value() > servoStatic.maxPos:
            self.RequestPositionSlider.setValue(servoStatic.maxPos)

        #deg = config.rangeMap(self.RequestPositionSlider.value(),
        #                      self.selectedServo.minPos, self.selectedServo.maxPos,
        #                      self.selectedServo.minDeg, self.selectedServo.maxDeg)
        servoStatic = config.md.servoStaticDict.get(self.selectedServoName)
        servoDerived = config.md.servoDerivedDict.get(self.selectedServoName)
        degrees = mg.evalDegFromPos(servoStatic, servoDerived, self.RequestPositionSlider.value())

        #deg = config.evalDegFromPos(self.selectedServoName, self.RequestPositionSlider.value())
        self.RequestPosition.setText(str(self.RequestPositionSlider.value()))
        self.RequestDegree.setText(str(degrees))


    def on_RequestPositionSlider_valueChanged(self):
        # slider does not work with min < max, correct value
        #pos = config.rangeMap(self.RequestPositionSlider.value(),
        #                           self.selectedServo.maxPos, self.selectedServo.minPos,
        #                           self.selectedServo.minPos, self.selectedServo.maxPos)
        #deg = config.rangeMap(self.RequestPositionSlider.value(),
        #                           self.selectedServo.minPos, self.selectedServo.maxPos,
        #                           self.selectedServo.minDeg, self.selectedServo.maxDeg)
        servoStatic = config.md.servoStaticDict.get(self.selectedServoName)
        servoDerived = config.md.servoDerivedDict.get(self.selectedServoName)
        degrees = mg.evalDegFromPos(servoStatic, servoDerived, self.RequestPositionSlider.value())
        self.RequestPosition.setText(str(self.RequestPositionSlider.value()))
        self.RequestDegree.setText(str(degrees))


    def on_DurationSlider_sliderMoved(self):
        position = self.DurationSlider.value()
        self.Duration.setText(str(position))

    def on_DurationSlider_valueChanged(self):
        position = self.DurationSlider.value()
        self.Duration.setText(str(position))


    def setArduinoCheckbox(self, arduino, newState):
        if arduino == 0:
            self.ArduinoLeft.setChecked(newState)
        else:
            self.ArduinoRight.setChecked(newState)


    def setServoGuiValues(self, servoName: str):

        servoStatic: mg.ServoStatic = config.md.servoStaticDict.get(servoName)
        servoDerived = config.md.servoDerivedDict.get(servoName)
        servoType = config.md.servoTypeDict.get(servoStatic.servoType)

        formattedServoName = self.servoNameFormat.replace("ServoName", servoName)
        self.ServoName.setText(formattedServoName)
        self.ServoName.setStyleSheet("background-color: green; color: white;")

        arduinoIndex = servoStatic.arduino
        self.Arduino.setText(f"Arduino: {config.md.arduinoDict.get(arduinoIndex)['arduinoName']}")
        self.Pin.setText(f"Pin: {servoStatic.pin}")
        self.Power.setText(f"Power: {servoStatic.powerPin}")
        self.CableArduinoTerminal.setText(f"Arduino->Terminal({servoStatic.cableTerminal}): {servoStatic.wireColorArduinoTerminal}")
        #self.Terminal.setText(f"Terminal: {servoStatic.cableTerminal}")
        self.CableTerminalServo.setText(f"Terminal({servoStatic.cableTerminal})->Servo: {servoStatic.wireColorTerminalServo}")
        self.AutoDetach.setChecked(servoStatic.autoDetach > 0)
        self.AutoDetachValue.setValue(servoStatic.autoDetach)
        self.Inverted.setChecked(servoStatic.inverted)
        self.Torque.setText(f"Torque: {servoType.typeTorque}")
        self.Type.setText(f"Type: {servoStatic.servoType}")
        self.ServoSpeed.setText(f"Servo Speed (s/60°): {servoType.typeSpeed}")
        self.MoveSpeed.setText(f"Move Speed (s/60°): {servoStatic.moveSpeed/1000:.2f}")

        # leave it on 0..180 default
        #self.PositionRangeMin.setText(str(servoStatic.minPos))
        #self.PositionRangeMax.setText(str(servoStatic.maxPos))
        #self.PositionSlider.setMinimum(servoStatic.minPos)
        #self.PositionSlider.setMaximum(servoStatic.maxPos)

        # use posRange element to show min/max pos of servo
        x = self.PositionSlider.geometry().x() + (servoStatic.minPos / 180 * 250)
        y = self.posRange.geometry().y()
        w = (servoStatic.maxPos - servoStatic.minPos) / 180 * 250
        h = self.posRange.geometry().height()
        self.posRange.setGeometry(x,y,w,h)

        # possible degrees
        self.DegreeRangeMin.setText("-180")
        self.DegreeRangeMax.setText("180")
        self.DegreeSlider.setMinimum(-180)
        self.DegreeSlider.setMaximum(180)

        x = self.DegreeSlider.geometry().x() + (servoStatic.minDeg + 180) / 360 * 250
        y = self.degRange.geometry().y()
        w = servoDerived.degRange / 360 * 250
        h = self.degRange.geometry().height()
        self.degRange.setGeometry(x,y,w,h)

        servoCurrent = config.md.servoCurrentDict.get(servoName)

        if servoCurrent.swiping:
            self.MoveServo.setEnabled(False)
            self.Modify.setEnabled(False)
            self.Rest.setEnabled(False)
            self.SwipeServo.setText("Stop Swipe")
            self.SwipeServo.setEnabled(True)
        else:
            self.MoveServo.setEnabled(True)
            self.Modify.setEnabled(True)
            self.Rest.setEnabled(True)
            self.SwipeServo.setText("Swipe")
            self.SwipeServo.setEnabled(True)

        self.Verbose.setEnabled(True)

        self.RequestPositionMinLabel.setText(str(servoStatic.minPos))
        self.RequestPositionMaxLabel.setText(str(servoStatic.maxPos))
        self.RequestDegreeMinLabel.setText(str(servoStatic.minDeg))
        self.RequestDegreeMaxLabel.setText(str(servoStatic.maxDeg))

        self.RequestPositionSlider.setMinimum(servoStatic.minPos)
        self.RequestPositionSlider.setMaximum(servoStatic.maxPos)
        self.RequestPositionSlider.setEnabled(True)

        self.DurationSlider.setEnabled(True)
        self.Duration.setText(str(self.DurationSlider.value()))

        position = round(servoCurrent.position)
        self.RequestPosition.setText(str(position))
        self.RequestPositionSlider.setValue(round(servoCurrent.position))

        degree = round(servoCurrent.degrees)
        self.RequestDegree.setText(str(degree))

        self.minComment.setText(" " + servoStatic.minComment + " ")
        self.minComment.adjustSize()
        rect = self.minComment.geometry()
        rect.moveLeft(int(self.minCommentCenter - rect.width()/2))
        self.minComment.setGeometry(rect)

        self.maxComment.setText(" " + servoStatic.maxComment + " ")
        self.maxComment.adjustSize()
        rect = self.maxComment.geometry()
        rect.moveLeft(int(self.maxCommentCenter - rect.width()/2))
        self.maxComment.setGeometry(rect)


        self.updateGuiServo(servoName)


    def updateGuiArduino(self, arduino):

        def updateServoButtons(arduino, newState):
            for servoName, servoStatic in config.md.servoStaticDict.items():
                if servoStatic.enabled and servoStatic.arduino == arduino:
                    servo = servoName.replace('.','_')
                    control = getattr(self, servo)
                    control.setEnabled(newState)
                    control = getattr(self, servo + 'Slider')
                    control.setEnabled(newState)

        #config.log(f"updateGui with arduino update {data}")
        if config.md.arduinoDict.get(arduino)['connected']:
            if arduino == 0:
                self.ArduinoLeft.setChecked(True)
                updateServoButtons(arduino, True)
            else:
                self.ArduinoRight.setChecked(True)
                updateServoButtons(arduino, True)

        else:
            if arduino == 0:
                self.ArduinoLeft.setChecked(False)
                updateServoButtons(arduino, False)
            else:
                self.ArduinoRight.setChecked(False)
                updateServoButtons(arduino, False)


    def updateGuiServo(self, servoName):

        servoCurrent = config.md.servoCurrentDict.get(servoName)

        # build the sliderName for the servo
        sliderName = servoName.replace(".", "_") + "Slider"
        #config.log(f"update slider: {sliderName}, position: {servoCurrent.position}")
        try:
            s = getattr(self, sliderName)
            # prevent trigger of "on_value_changed" event by blocking events when updating
            if not s.isSliderDown():
                s.blockSignals(True)
                s.setValue(servoCurrent.position)
                s.blockSignals(False)

        except:
            config.log(f"problem with sliderName: {sliderName}")

        # check for updated servo is the currently shown servo in the GUI
        if self.selectedServoName != servoName:
            return

        assigned = servoCurrent.assigned
        if assigned != self.ServoAssigned.isChecked():
            self.ServoAssigned.setChecked(assigned)

        moving = servoCurrent.moving
        if moving != self.ServoMoving.isChecked():
            self.ServoMoving.setChecked(moving)
        if not moving:
            self.MoveServo.setText("Move")

        detached = not servoCurrent.attached
        if detached != self.ServoSignalStopped.isChecked():
            self.ServoSignalStopped.setChecked(detached)

        autoDetach = servoCurrent.autoDetach
        if autoDetach != self.AutoDetach.isChecked():
            self.AutoDetach.setChecked(autoDetach)

        verbose = servoCurrent.verbose
        if verbose != self.Verbose.isChecked():
            self.Verbose.setChecked(verbose)

        #print(f"pin: {data}, position: {position}")
        self.Position.setText(str(servoCurrent.position))
        self.PositionSlider.setValue(servoCurrent.position)

        self.Degree.setText(str(servoCurrent.degrees))
        self.DegreeSlider.setValue(servoCurrent.degrees)

        #config.log("gui update done")

    def updateGuiProcess(self, processName):
        config.log(f"tbd, update active processes in gui")