"""Zippy's brain: the trip manager as a ROS 2 node (Manual 0.6, 5 Oct 2026).

Listens   /zippy/command    std_msgs/String  JSON like {"cmd": "go", "place": "bedroom_a"}
Publishes /zippy/status     std_msgs/String  JSON with the state, target, queue and message
          /zippy/heartbeat  std_msgs/UInt32  10 times a second while the brain runs;
                                             the ESP32's watchdog will stop the motors when it stops
Drives    Nav2's navigate_to_pose action, or a pretend Nav2 when fake is true.
"""
import json
import math
import os

import rclpy
import yaml
from action_msgs.msg import GoalStatus
from ament_index_python.packages import get_package_share_directory
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.clock import Clock, ClockType
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String, UInt32

from .fake_nav import FakeNavigator
from .trips import DOCK, TripManager

LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)


class Nav2Navigator:
    """Sends one goal at a time to Nav2 and reports how it ended."""

    def __init__(self, node):
        self.node = node
        self.client = ActionClient(node, NavigateToPose, 'navigate_to_pose')
        self.goal_handle = None
        self.token = 0              # changes on every start/cancel, so late answers are ignored
        self.active = False         # a trip is wanted right now
        self.to_cancel = None       # goal to cancel on the next update, unless a new trip replaces it
        self.remaining = None
        self.pending_failure = None

    def start(self, name, place, on_done):
        self.token += 1
        token = self.token
        self.active = True
        # A new goal replaces the old one inside Nav2 by itself; cancelling it as well can make
        # Nav2 drop the new goal too, so a pending cancel is forgotten here.
        self.to_cancel = None
        self.goal_handle = None
        self.remaining = None
        if not self.client.server_is_ready():
            # report on the next update, not from inside start()
            self.pending_failure = (on_done, "Nav2 isn't running")
            return
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = 'map'
        goal.pose.header.stamp = self.node.get_clock().now().to_msg()
        goal.pose.pose.position.x = float(place['x'])
        goal.pose.pose.position.y = float(place['y'])
        goal.pose.pose.orientation.z = math.sin(float(place['yaw']) / 2)
        goal.pose.pose.orientation.w = math.cos(float(place['yaw']) / 2)
        future = self.client.send_goal_async(goal, feedback_callback=lambda fb: self._feedback(token, fb))
        future.add_done_callback(lambda f: self._accepted(token, f, on_done))

    def cancel(self):
        self.token += 1
        self.active = False
        self.pending_failure = None
        self.remaining = None
        if self.goal_handle is not None:
            self.to_cancel = self.goal_handle     # sent on the next update
            self.goal_handle = None

    def update(self):
        if self.to_cancel is not None:
            if not self.active:
                self.to_cancel.cancel_goal_async()
            self.to_cancel = None
        if self.pending_failure:
            on_done, reason = self.pending_failure
            self.pending_failure = None
            on_done(False, reason)

    def distance_left(self):
        return self.remaining

    def _feedback(self, token, msg):
        if token == self.token:
            self.remaining = msg.feedback.distance_remaining

    def _accepted(self, token, future, on_done):
        handle = future.result()
        if token != self.token:          # cancelled while the goal was on its way
            if handle.accepted and not self.active:
                handle.cancel_goal_async()  # (if a newer trip started, Nav2 replaces this goal itself)
            return
        if not handle.accepted:
            on_done(False, 'Nav2 refused the goal')
            return
        self.goal_handle = handle
        handle.get_result_async().add_done_callback(lambda f: self._finished(token, f, on_done))

    def _finished(self, token, future, on_done):
        if token != self.token:
            return
        self.goal_handle = None
        self.remaining = None
        status = future.result().status
        if status == GoalStatus.STATUS_SUCCEEDED:
            on_done(True, '')
        elif status == GoalStatus.STATUS_CANCELED:
            on_done(False, 'cancelled')
        else:
            on_done(False, 'Nav2 gave up')


class MissionNode(Node):
    def __init__(self):
        super().__init__('zippy_mission')
        self.declare_parameter('fake', False)
        self.declare_parameter('fake_fail', '')            # comma-separated places that fail in pretend mode
        self.declare_parameter('arrive_timeout', 120.0)    # s to wait for Done before going home
        self.declare_parameter('trip_timeout', 240.0)      # s before a trip counts as failed
        self.declare_parameter('places_file', '')          # default: zippy_navigation's places.yaml

        places_file = self.get_parameter('places_file').value or os.path.join(
            get_package_share_directory('zippy_navigation'), 'maps', 'places.yaml')
        with open(places_file) as f:
            places = yaml.safe_load(f)['places']

        self.fake = self.get_parameter('fake').value
        if self.fake:
            fails = [p.strip() for p in self.get_parameter('fake_fail').value.split(',') if p.strip()]
            dock = places[DOCK]
            self.nav = FakeNavigator(start_xy=(dock['x'], dock['y']), fail_places=fails)
        else:
            self.nav = Nav2Navigator(self)
        self.trips = TripManager(places, self.nav,
                                 arrive_timeout=self.get_parameter('arrive_timeout').value,
                                 trip_timeout=self.get_parameter('trip_timeout').value)
        self.reply = ''
        self.beat = 0

        self.status_pub = self.create_publisher(String, '/zippy/status', LATCHED)
        self.heartbeat_pub = self.create_publisher(UInt32, '/zippy/heartbeat', 10)
        self.create_subscription(String, '/zippy/command', self.on_command, 10)
        # The computer's clock, not Gazebo's: the heartbeat and timeouts must keep going even if
        # the simulation runs slowly or is paused.
        steady = Clock(clock_type=ClockType.STEADY_TIME)
        self.create_timer(0.1, self.on_tick, clock=steady)
        self.create_timer(1.0, self.publish_status, clock=steady)   # once a second anyway
        mode = 'PRETEND Nav2' if self.fake else 'Nav2'
        self.get_logger().info(f'Zippy brain ready with {mode}. Places: {", ".join(places)}')
        self.publish_status()

    def on_command(self, msg):
        try:
            data = json.loads(msg.data)
            self.reply = self.trips.command(data.get('cmd', ''), data.get('place'))
        except (ValueError, AttributeError, TypeError):
            self.reply = f'Bad command: {msg.data}'
        self.get_logger().info(f'{msg.data} -> {self.reply}')
        self.publish_status()

    def on_tick(self):
        self.beat += 1
        self.heartbeat_pub.publish(UInt32(data=self.beat))
        self.nav.update()
        self.trips.progress(self.nav.distance_left())
        self.trips.tick()
        if self.trips.changed:
            self.publish_status()

    def publish_status(self):
        status = self.trips.status()
        status['reply'] = self.reply
        status['fake'] = self.fake
        self.status_pub.publish(String(data=json.dumps(status)))
        if self.trips.changed:
            self.get_logger().info(f"[{status['state']}] {status['message']}")
        self.trips.changed = False


def main():
    rclpy.init()
    node = MissionNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
