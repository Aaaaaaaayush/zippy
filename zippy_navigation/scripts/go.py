#!/usr/bin/env python3
"""Send Zippy to its named places, one after another (Manual 0.5, 5 Oct 2026).

    ros2 run zippy_navigation go.py kitchen               # one trip
    ros2 run zippy_navigation go.py kitchen sofa dock     # three trips in a row
    ros2 run zippy_navigation go.py kitchen dock --repeat 5 --log ~/trips.csv
    ros2 run zippy_navigation go.py --list                # the places Zippy knows

The places come from maps/places.yaml, written by make_zippy_map.py.
Press Ctrl + C to cancel the current trip; Zippy stops where it is.
"""
import argparse
import csv
import math
import os
import sys
import time

import yaml
from ament_index_python.packages import get_package_share_directory


def load_places():
    path = os.path.join(get_package_share_directory('zippy_navigation'), 'maps', 'places.yaml')
    with open(path) as f:
        return yaml.safe_load(f)['places']


def main():
    parser = argparse.ArgumentParser(description='Send Zippy to named places.')
    parser.add_argument('places', nargs='*', help='place names, visited in order')
    parser.add_argument('--repeat', type=int, default=1, help='run the whole list this many times')
    parser.add_argument('--log', help='append one line per trip to this CSV file')
    parser.add_argument('--list', action='store_true', help='print the known places and exit')
    args = parser.parse_args(sys.argv[1:] if '--ros-args' not in sys.argv
                             else sys.argv[1:sys.argv.index('--ros-args')])

    places = load_places()
    if args.list or not args.places:
        for name, p in places.items():
            print(f"  {name:12s} x {p['x']:6.2f}  y {p['y']:6.2f}  facing {math.degrees(p['yaw']):5.0f} deg")
        return
    unknown = [n for n in args.places if n not in places]
    if unknown:
        sys.exit(f"Unknown place(s): {', '.join(unknown)}. Known: {', '.join(places)}")

    # Imported here so --list works even before ROS is sourced
    import rclpy
    from geometry_msgs.msg import PoseStamped
    from nav2_simple_commander.robot_navigator import BasicNavigator, TaskResult
    from rclpy.signals import SignalHandlerOptions

    # Let Ctrl + C reach this script, so it can cancel the trip before ROS shuts down
    rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
    nav = BasicNavigator(node_name='zippy_go')

    def pose_of(name):
        p = places[name]
        msg = PoseStamped()
        msg.header.frame_id = 'map'
        msg.header.stamp = nav.get_clock().now().to_msg()
        msg.pose.position.x = float(p['x'])
        msg.pose.position.y = float(p['y'])
        msg.pose.orientation.z = math.sin(p['yaw'] / 2)
        msg.pose.orientation.w = math.cos(p['yaw'] / 2)
        return msg

    trips = args.places * args.repeat
    results = []
    log = None
    if args.log:
        path = os.path.expanduser(args.log)
        new = not os.path.exists(path)
        log = open(path, 'a', newline='')
        writer = csv.writer(log)
        if new:
            writer.writerow(['time', 'place', 'result', 'seconds', 'recoveries'])

    name = None
    start = time.time()
    try:
        # Wait until Nav2's trip planner is switched on. (Not waitUntilNav2Active(): with AMCL
        # that would also reset Zippy's pose to the dock, wherever it really is.)
        print('Waiting for Nav2 ...', flush=True)
        nav._waitForNodeToActivate('bt_navigator')
        for i, name in enumerate(trips, 1):
            print(f"[{i}/{len(trips)}] going to {name} ...", flush=True)
            start = time.time()
            nav.feedback = None                  # forget the last trip's progress
            if not nav.goToPose(pose_of(name)):
                print('      REJECTED by Nav2', flush=True)
                results.append(False)
                if log:
                    writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S'), name, 'rejected', 0, 0])
                    log.flush()
                continue
            recoveries = 0
            last_print = 0.0
            while not nav.isTaskComplete():
                fb = nav.getFeedback()
                if fb:
                    recoveries = fb.number_of_recoveries
                    if time.time() - last_print > 5:
                        print(f"      {fb.distance_remaining:5.1f} m to go", flush=True)
                        last_print = time.time()
            seconds = time.time() - start
            result = {TaskResult.SUCCEEDED: 'arrived', TaskResult.CANCELED: 'cancelled',
                      TaskResult.FAILED: 'FAILED'}.get(nav.getResult(), 'UNKNOWN')
            print(f"      {result} in {seconds:.0f} s, {recoveries} recoveries", flush=True)
            results.append(result == 'arrived')
            if log:
                writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S'), name, result,
                                 round(seconds, 1), recoveries])
                log.flush()
    except KeyboardInterrupt:
        print('\nCancelling the trip ...')
        if name:
            nav.cancelTask()
            results.append(False)
        if log and name:
            writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S'), name, 'cancelled',
                             round(time.time() - start, 1), 0])
    finally:
        if log:
            log.close()
        print(f"Summary: {sum(results)} of {len(results)} trips arrived.")
        nav.destroyNode()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
