#!/usr/bin/env python
import rospy
import sys

import numpy as np
import random
import math
from enum import Enum

from geometry_msgs.msg import Twist
from turtlesim.msg import Pose
import turtlesim.srv
import std_srvs.srv



class State(Enum):
    WRITING = 1
    ANGRY = 2
    RETURNING = 3



PI = 3.1415926535897

def deg2rad(degrees):
    return degrees * 2 * PI / 360

def rad2deg(rad):
    return rad * 360 / PI / 2



class TurtlesimHelper:
    def __init__(self):
        rospy.wait_for_service('clear')
        self.clear = rospy.ServiceProxy('clear', std_srvs.srv.Empty())

        rospy.wait_for_service('kill')
        self.kill = rospy.ServiceProxy('kill', turtlesim.srv.Kill)

        rospy.wait_for_service('reset')
        self.reset = rospy.ServiceProxy('reset', std_srvs.srv.Empty())

        rospy.wait_for_service('spawn')
        self.spawn = rospy.ServiceProxy('spawn', turtlesim.srv.Spawn)

    def spawn_random(self, name):
        self.spawn(random.randint(1,10), random.randint(1,10), deg2rad(random.randint(1,360)), name)



class MyTurtle:
    def __init__(self, name, rate, set_pen_off):
        self.turtle_name = name
        self.rate = rate
        self.turtle_pose = Pose()

        turtlesim_helper.spawn_random(self.turtle_name)

        self.velocity_publisher = rospy.Publisher('/%s/cmd_vel' % self.turtle_name, Twist, queue_size=10)
        self.turtle_pose_subscriber = rospy.Subscriber('/%s/pose' % self.turtle_name, Pose, self.pose_callback)

        rospy.wait_for_service('/%s/set_pen' % self.turtle_name)
        self.turtle_set_pen = rospy.ServiceProxy('/%s/set_pen' % self.turtle_name, turtlesim.srv.SetPen)
        self.turtle_set_pen_off(set_pen_off) # custom function

    def pose_callback(self, data):
        self.turtle_pose = data
        self.turtle_pose.x = round(self.turtle_pose.x, 4)
        self.turtle_pose.y = round(self.turtle_pose.y, 4)
        self.turtle_pose.theta = round(self.turtle_pose.theta, 4)

    def turtle_set_pen_off(self, off):
        self.turtle_set_pen(200, 200, 200, 2, off) # default function

    def turtle_move_randomly(self):
        vel_msg = Twist()
        vel_msg.linear.x = random.uniform(0, 5)
        vel_msg.angular.z = random.uniform(-5, 5)
        self.velocity_publisher.publish(vel_msg)
        # self.rate.sleep()
        return vel_msg

    def linear_vel(self, goal_pose, constant):
        """See video: https://www.youtube.com/watch?v=Qh15Nol5htM."""
        return constant * self.euclidean_distance(goal_pose)

    def steering_angle(self, goal_pose):
        """See video: https://www.youtube.com/watch?v=Qh15Nol5htM."""
        return math.atan2(goal_pose.y - self.turtle_pose.y, goal_pose.x - self.turtle_pose.x)

    def angle_difference(self, angle1, angle2):
        return np.arctan2(np.sin(angle1 - angle2), np.cos(angle1 - angle2))

    def angular_vel(self, goal_pose, constant):
        """See video: https://www.youtube.com/watch?v=Qh15Nol5htM."""
        return constant * self.angle_difference(self.steering_angle(goal_pose), self.turtle_pose.theta)

    def euclidean_distance(self, goal_pose):
        """Euclidean distance between current pose and the goal."""
        return math.sqrt(math.pow((goal_pose.x - self.turtle_pose.x), 2) +
                         math.pow((goal_pose.y - self.turtle_pose.y), 2))

    def turtle_move2goal(self, x, y, angular_constant=6, linear_constant=1.5):
        goal_pose = Pose()
        goal_pose.x = x
        goal_pose.y = y
        distance_tolerance = 1
        vel_msg = Twist()

        # Porportional Controller
        # https://en.wikipedia.org/wiki/Proportional_control
        while not rospy.is_shutdown() and self.euclidean_distance(goal_pose) >= distance_tolerance:

            # Linear velocity in the x-axis:
            vel_msg.linear.x = self.linear_vel(goal_pose, linear_constant)
            vel_msg.linear.y = 0
            vel_msg.linear.z = 0

            # Angular velocity in the z-axis:
            vel_msg.angular.x = 0
            vel_msg.angular.y = 0
            vel_msg.angular.z = self.angular_vel(goal_pose, angular_constant)

            # Publishing our vel_msg
            self.velocity_publisher.publish(vel_msg)
            self.rate.sleep()

        self.turtle_stop()

    def turtle_rotate(self, angle, clockwise=False, speed=100):

        vel_msg = Twist()

        # Converting from angles to radians
        relative_angle = deg2rad(angle)
        angular_speed = deg2rad(speed)

        # We wont use linear components
        vel_msg.linear.x=0
        vel_msg.linear.y=0
        vel_msg.linear.z=0
        vel_msg.angular.x = 0
        vel_msg.angular.y = 0

        # Checking if our movement is CW or CCW
        if clockwise:
            vel_msg.angular.z = -abs(angular_speed)
        else:
            vel_msg.angular.z = abs(angular_speed)

        # Setting the current time for distance calculus
        t0 = rospy.Time.now().to_sec()
        current_angle = 0

        while not rospy.is_shutdown() and current_angle < relative_angle:
            self.velocity_publisher.publish(vel_msg)
            self.rate.sleep()
            t1 = rospy.Time.now().to_sec()
            current_angle = angular_speed*(t1-t0)

        self.turtle_stop()

    def turtle_stop(self):
        vel_msg = Twist()
        vel_msg.linear.x = 0
        vel_msg.angular.z = 0
        self.velocity_publisher.publish(vel_msg)
        self.rate.sleep()



class UsiAngryTurtle:

    def __init__(self, turtles_number = 6, linear_constant = 1.5, angular_constant = 6):

        rospy.init_node('usi_assignment1', anonymous=True)

        self.state = None
        self.rate = rospy.Rate(10)
        self.linear_costant = linear_constant
        self.angular_constant = angular_constant

        turtlesim_helper.reset()
        turtlesim_helper.kill('turtle1')
        
        self.writer = MyTurtle('turtle_writer', self.rate, 0)

        self.offenders = []
        for i in range(turtles_number - 1):
            self.offenders.append(MyTurtle('turtle%s' % i, self.rate, 1))


    def calculate_pose_ahead(self, offender):

        # "You can let m to be directly proportional to the current speed of the target turtle times the current distance"
        meters_ahead = offender.turtle_pose.linear_velocity / 2 * self.writer.euclidean_distance(offender.turtle_pose)
        meters_ahead = np.clip(meters_ahead, -5, 5) # if the offender is too distant, this look-ahead must be clipped or the writer will try to go out of screen

        # finding versor [x,y] which forms theta angle with the x-axis [0,1] wrt the origin (0,0)
        versor_x = np.cos(offender.turtle_pose.theta)
        versor_y = math.sqrt(1 - math.pow(versor_x, 2)) # inverse of the norm given x (where norm=1) to find y
        pose_ahead_wrt_origin = meters_ahead * np.array([versor_x, versor_y])

        # translating the versor from the origin to the actual offender pose
        pose_ahead = Pose()
        pose_ahead.x = pose_ahead_wrt_origin[0] + offender.turtle_pose.x
        pose_ahead.y = pose_ahead_wrt_origin[1] + offender.turtle_pose.y
        pose_ahead.theta = offender.turtle_pose.theta

        return pose_ahead


    def run(self, writing_poses, look_ahead = True):

        while not rospy.is_shutdown(): # infinite loop

            self.state = State.WRITING                                                       ####### Change Status: WRITING
            rospy.loginfo(self.state)
            offender = None

            for index in range(len(writing_poses)): # writes USI over and over again

                x = writing_poses[index][0]
                y = writing_poses[index][1]

                if x == -2:
                    self.writer.turtle_set_pen_off(1)   # disable pen

                elif x == -1:
                    self.writer.turtle_set_pen_off(0)   # enable pen


                else:                                   # normal behaviour
                    vel_msg = Twist()
                    goal_pose = Pose()
                    goal_pose.x = x
                    goal_pose.y = y

                    while not rospy.is_shutdown() and self.writer.euclidean_distance(goal_pose) >= 1: # move to goal

                        vel_msg.linear.x = self.writer.linear_vel(goal_pose, self.linear_costant)
                        vel_msg.angular.z = self.writer.angular_vel(goal_pose, self.angular_constant)
                        self.writer.velocity_publisher.publish(vel_msg)
                        self.rate.sleep()

                        # Moving offenders and intercepting them
                        for off_index, off in enumerate(self.offenders):
                            if off.turtle_name != 'turtle1': # turtle1 is teleoperated
                                off.turtle_move_randomly()

                            if self.writer.euclidean_distance(off.turtle_pose) < 3:
                                offender = off
                                offender_index = off_index
                                self.state = State.ANGRY                                     ####### Change Status: ANGRY
                                rospy.loginfo('%s with %s' % (self.state, offender.turtle_name))
                                break


                        if self.state == State.ANGRY and offender != None:
                            self.writer.turtle_set_pen_off(0)

                            # Following the offender
                            while not rospy.is_shutdown() and self.writer.euclidean_distance(offender.turtle_pose) >= 0.3:
                                if offender.turtle_name != 'turtle1': # turtle1 is teleoperated
                                    offender.turtle_move_randomly() # only the chosen offender keeps moving

                                pose_to_reach = Pose()

                                if look_ahead:
                                     # The writer turtle does not aim directly towards its target, but instead tries to look ahead m meters in front of the offender to intercept it
                                    pose_to_reach = self.calculate_pose_ahead(offender)
                                else:
                                    # The writer aims directly to the pose of the offender
                                    pose_to_reach = offender.turtle_pose

                                vel_msg.linear.x = self.writer.linear_vel(pose_to_reach, self.linear_costant * 2) # little speedup
                                vel_msg.angular.z = self.writer.angular_vel(pose_to_reach, self.angular_constant)
                                self.writer.velocity_publisher.publish(vel_msg)
                                self.rate.sleep()

                            # Offender has been caught
                            self.writer.turtle_stop()
                            turtlesim_helper.kill(offender.turtle_name) 

                            if offender.turtle_name == 'turtle1': # turtle1 is teleoperated, so it respawns instead of being killed only
                                self.offenders[offender_index] = MyTurtle('turtle1', self.rate, 1)
                                # NOTE: `rostopic echo /turtle1/pose` has 2 to 8 seconds delay after respawning
                                # we update this coords in order to achieve a sort of bugfix (preventing offender to be detected where it is not)
                                # anyway, this way we still prevent offender to be detected correctly during the first seconds of delay
                                self.offenders[offender_index].turtle_pose.x = -100 
                                self.offenders[offender_index].turtle_pose.y = -100
                            else:
                                del self.offenders[offender_index] # remove offenders from the list

                            self.state = State.RETURNING                                     ####### Change Status: RETURNING
                            rospy.loginfo(self.state)
                            break


                # Returing to proper position
                if self.state == State.RETURNING:
                    self.writer.turtle_move2goal(writing_poses[1][0], writing_poses[1][1])
                    turtlesim_helper.clear()
                    self.rate.sleep()
                    break
        



turtlesim_helper = TurtlesimHelper()

if __name__ == '__main__':

    usi = UsiAngryTurtle(turtles_number = 10)

    usi_poses = [
        (-2, -2), (1, 11), (1, 8), # starting position
        (-1, -1), (1, 3), (2, 2), (3, 4), (3, 10), # letter U
        (-2, -2), (9,10), (6, 9), # repositioning
        (-1, -1), (5, 9), (4, 7), (5, 5.5), (6, 5.5), (7, 4), (6, 2.5), (3, 2.5), # letter S
        (-2, -2), (9, 2), (9, 3.5), # repositioning
        (-1, -1), (9, 6), (9, 10) # letter I
    ]

    usi.run(usi_poses, look_ahead = True)

    rospy.spin()