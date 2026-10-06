"""Zippy's face: serves the touchscreen page and links it to the brain over ROS (Manual 0.6).

Open http://localhost:8000 in a browser on the same computer (WSL passes the port to Windows).
"""
import json
import os
import threading

import rclpy
import uvicorn
from ament_index_python.packages import get_package_share_directory
from rclpy.executors import SingleThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.signals import SignalHandlerOptions
from std_msgs.msg import String

from .web import Hub, make_app

LATCHED = QoSProfile(depth=1, reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)


class UiNode(Node):
    def __init__(self, hub):
        super().__init__('zippy_ui')
        self.declare_parameter('port', 8000)
        self.hub = hub
        self.command_pub = self.create_publisher(String, '/zippy/command', 10)
        self.create_subscription(String, '/zippy/status', lambda m: hub.update(m.data), LATCHED)

    def send(self, cmd, place):
        self.command_pub.publish(String(data=json.dumps({'cmd': cmd, 'place': place})))


def main():
    # uvicorn handles Ctrl + C; ROS shuts down after it
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    hub = Hub()
    node = UiNode(hub)
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    threading.Thread(target=executor.spin, daemon=True).start()

    port = node.get_parameter('port').value
    web_dir = os.path.join(get_package_share_directory('zippy_mission'), 'web')
    node.get_logger().info(f'Touchscreen page at http://localhost:{port}')
    try:
        uvicorn.run(make_app(hub, node.send, web_dir), host='0.0.0.0', port=port, log_level='warning')
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
