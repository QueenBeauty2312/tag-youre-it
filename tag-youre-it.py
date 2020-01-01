# Based on Amazon tutorial

# import os
# import sys
import time
import logging
import json
import random
import threading
from enum import Enum

from agt import AlexaGadget

from ev3dev2.led import Leds
from ev3dev2.sound import Sound
from ev3dev2.motor import OUTPUT_A, OUTPUT_B, OUTPUT_C, OUTPUT_D, MoveTank, SpeedPercent, MediumMotor
from ev3dev2.sensor.lego import UltrasonicSensor, TouchSensor, InfraredSensor

from time import sleep

# Set the logging level to INFO to see messages from AlexaGadget
logging.basicConfig(level=logging.INFO)

### Testing the sensors
# Connect infrared and touch sensors to any sensor ports
ir = InfraredSensor() 
ts = TouchSensor()
us = UltrasonicSensor()
leds = Leds()

leds.all_off() # stop the LEDs flashing (as well as turn them off)
# # is_pressed and proximity are not functions and do not need parentheses
# while not ts.is_pressed:  # Stop program by pressing the touch sensor button
#     print("Ultrasonic " + str(us.distance_centimeters))
#     print("Infrared " + str(ir.proximity))
#     if us.distance_centimeters < 40*1.4: # to detect objects closer than about 40cm
#         leds.set_color('LEFT',  'RED')
#         leds.set_color('RIGHT', 'RED')
#     else:
#         leds.set_color('LEFT',  'GREEN')
#         leds.set_color('RIGHT', 'GREEN')
#         self.drive.on_for_seconds(SpeedPercent(50), SpeedPercent(50), 2, block=is_blocking)


#     sleep (0.01) # Give the CPU a rest
# ###

class Direction(Enum):
    """
    The list of directional commands and their variations.
    These variations correspond to the skill slot values.
    """
    FORWARD = ['forward', 'forwards', 'go forward']
    BACKWARD = ['back', 'backward', 'go backward']
    LEFT = ['left', 'go left']
    RIGHT = ['right', 'go right']
    STOP = ['stop', 'brake', 'halt']


class Command(Enum):
    """
    The list of preset commands and their invocation variation.
    These variations correspond to the skill slot values.
    """
    MOVE_CIRCLE = ['circle', 'move around']
    MOVE_SQUARE = ['square']
    TAG_YOURE_IT = ['tag you\'re it', 'tag you are it']
    TAG_IM_IT = ['tag i\'m it', 'tag i am it']


class EventName(Enum):
    """
    The list of custom event name sent from this gadget
    """
    PROXIMITY = "Proximity"
    SPEECH = "Speech"


class MindstormsGadget(AlexaGadget):
    """
    A Mindstorms gadget that can perform bi-directional interaction with an Alexa skill.
    """

    def __init__(self):
        """
        Performs Alexa Gadget initialization routines and ev3dev resource allocation.
        """
        super().__init__()

        # Robot state
        self.tag_youre_it_mode = False
        self.tag_im_it_mode = False

        # Connect two large motors on output ports A and D
        self.drive = MoveTank(OUTPUT_A, OUTPUT_D)
        self.sound = Sound()
        self.leds = Leds()
        self.ir = InfraredSensor()
        self.us = UltrasonicSensor()

        # Start threads
        threading.Thread(target=self._youre_it_thread, daemon=True).start()
        threading.Thread(target=self._im_it_thread, daemon=True).start()

    def on_connected(self, device_addr):
        """
        Gadget connected to the paired Echo device.
        :param device_addr: the address of the device we connected to
        """
        self.leds.set_color("LEFT", "GREEN")
        self.leds.set_color("RIGHT", "GREEN")
        print("{} connected to Echo device".format(self.friendly_name))

    def on_disconnected(self, device_addr):
        """
        Gadget disconnected from the paired Echo device.
        :param device_addr: the address of the device we disconnected from
        """
        self.leds.set_color("LEFT", "BLACK")
        self.leds.set_color("RIGHT", "BLACK")
        print("{} disconnected from Echo device".format(self.friendly_name))

    def on_custom_mindstorms_gadget_control(self, directive):
        """
        Handles the Custom.Mindstorms.Gadget control directive.
        :param directive: the custom directive with the matching namespace and name
        """
        try:
            payload = json.loads(directive.payload.decode("utf-8"))
            print("Control payload: {}".format(payload))
            control_type = payload["type"]
            if control_type == "move":

                # Expected params: [direction, duration, speed]
                self._move(payload["direction"], int(payload["duration"]), int(payload["speed"]))

            if control_type == "command":
                # Expected params: [command]
                self._activate(payload["command"])

        except KeyError:
            print("Missing expected parameters: {}".format(directive))

    def _move(self, direction, duration: int, speed: int, is_blocking=False):
        """
        Handles move commands from the directive.
        Right and left movement can under or over turn depending on the surface type.
        :param direction: the move direction
        :param duration: the duration in seconds
        :param speed: the speed percentage as an integer
        :param is_blocking: if set, motor run until duration expired before accepting another command
        """
        print("Move command: ({}, {}, {}, {})".format(direction, speed, duration, is_blocking))
        if direction in Direction.FORWARD.value:
            self.drive.on_for_seconds(SpeedPercent(speed), SpeedPercent(speed), duration, block=is_blocking)

        if direction in Direction.BACKWARD.value:
            self.drive.on_for_seconds(SpeedPercent(-speed), SpeedPercent(-speed), duration, block=is_blocking)

        if direction in (Direction.RIGHT.value + Direction.LEFT.value):
            self._turn(direction, speed)
            self.drive.on_for_seconds(SpeedPercent(speed), SpeedPercent(speed), duration, block=is_blocking)

        if direction in Direction.STOP.value:
            self.drive.off()
            self.patrol_mode = False

    def _activate(self, command, speed=50):
        """
        Handles preset commands.
        :param command: the preset command
        :param speed: the speed if applicable
        """
        print("Activate command: ({}, {})".format(command, speed))
        if command in Command.MOVE_CIRCLE.value:
            self.drive.on_for_seconds(SpeedPercent(int(speed)), SpeedPercent(5), 12)

        if command in Command.MOVE_SQUARE.value:
            for i in range(4):
                self._move("right", 2, speed, is_blocking=True)

        if command in Command.TAG_YOURE_IT.value:
            # Set tag you're it mode to resume tag_youre_it thread processing
            self.tag_youre_it_mode = True
            self._send_event(EventName.SPEECH, {'speechOut': "Oh no. I am it! Here I come!"})

        if command in Command.TAG_IM_IT.value:
            self.tag_im_it__mode = True
            self._send_event(EventName.SPEECH, {'speechOut': "Yikes! You are it! I am out of here!"})

            # Perform Shuffle posture
            self.drive.on_for_seconds(SpeedPercent(80), SpeedPercent(-80), 0.2)
            time.sleep(0.3)
            self.drive.on_for_seconds(SpeedPercent(-40), SpeedPercent(40), 0.2)

            self.leds.set_color("LEFT", "YELLOW", 1)
            self.leds.set_color("RIGHT", "YELLOW", 1)

    def _turn(self, direction, speed):
        """
        Turns based on the specified direction and speed.
        Calibrated for hard smooth surface.
        :param direction: the turn direction
        :param speed: the turn speed
        """
        if direction in Direction.LEFT.value:
            self.drive.on_for_seconds(SpeedPercent(0), SpeedPercent(speed), 2)

        if direction in Direction.RIGHT.value:
            self.drive.on_for_seconds(SpeedPercent(speed), SpeedPercent(0), 2)

    def _send_event(self, name: EventName, payload):
        """
        Sends a custom event to trigger an action.
        :param name: the name of the custom event
        :param payload: the JSON payload
        """
        self.send_custom_event('Custom.Mindstorms.Gadget', name.value, payload)

    def _im_it_thread(self):
        """
        The robot is it. Seek after the IR beacon.
        If the minimum distance is breached, send a custom event to trigger tag action on
        the Alexa skill.
        """
        count = 0
        while True:
            while self.tag_im_it_mode:
                # Chase after person. 
                self.drive.on_for_seconds(SpeedPercent(50), SpeedPercent(50), 2, block=is_blocking)
                distance = self.us.proximity
                print("Proximity: {}".format(distance))
                count = count + 1 if distance < 10 else 0
                if count > 3:
                    print("Proximity breached. Sending event to skill")
                    self.leds.set_color("LEFT", "RED", 1)
                    self.leds.set_color("RIGHT", "RED", 1)

                    self._send_event(EventName.SPEECH, {'speechOut': "Tag you are it!"})

                    self._send_event(EventName.PROXIMITY, {'distance': distance})
                    self.tag_im_it_mode = False

                time.sleep(0.2)
            time.sleep(1)

    def _youre_it_thread(self):
        """
        Performs random movement when you're it mode is activated.
        """
        while True:
            while self.tag_youre_it_mode:
                print("Tag You're it mode activated randomly picking a path")
                direction = random.choice(list(Direction))
                duration = random.randint(1, 5)
                speed = random.randint(1, 4) * 25

                while direction == Direction.STOP:
                    direction = random.choice(list(Direction))

                # direction: all except stop, duration: 1-5s, speed: 25, 50, 75, 100
                self._move(direction.value[0], duration, speed)
                time.sleep(duration)
            time.sleep(1)


if __name__ == '__main__':
    # Startup sequence
    gadget = MindstormsGadget()
    gadget.sound.play_song((('C4', 'e'), ('D4', 'e'), ('E5', 'q')))
    gadget.leds.set_color("LEFT", "GREEN")
    gadget.leds.set_color("RIGHT", "GREEN")

    # Gadget main entry point
    gadget.main()

    # Shutdown sequence
    gadget.sound.play_song((('E5', 'e'), ('C4', 'e')))
    gadget.leds.set_color("LEFT", "BLACK")
    gadget.leds.set_color("RIGHT", "BLACK")
