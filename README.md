# Zippy

A home tray robot. Zippy is 42 cm round and 80 cm tall, carries up to 8 kg on its tray,
drives itself between rooms and returns to its dock. Built by Aayush.

## Where it stands

Phase 0, simulation: ROS 2 Jazzy, Gazebo Harmonic and linorobot2 on WSL2 (Ubuntu 24.04).

| Manual | Result |
| --- | --- |
| 0.1 to 0.3 | Workshop set up, first robot in simulation, the flat as a map and a Gazebo world |
| 0.4 | Zippy's own body: every doorway, a hard stop with 8 kg, 1 cm sills 10 of 10 |
| 0.5 | Zippy's own Nav2: gentle braking, keep-out and slow zones, named places, a dock facing the door, odometry calibrated (tests on hold) |
| 0.6 | Zippy's brain and face: a trip manager, a touchscreen page, and the motor watchdog in Wokwi |

## Folders

| Folder | What it holds |
| --- | --- |
| `zippy_description` | Zippy's body for ROS and Gazebo; every number is in `urdf/zippy_properties.urdf.xacro` |
| `zippy_navigation` | Nav2 settings, the zone filters, and `go.py`, which sends Zippy to named places |
| `zippy_mission` | Zippy's brain (the trip manager) and face (the touchscreen page at http://localhost:8000) |
| `firmware/wokwi_watchdog` | The ESP32-S3 motor watchdog, as a Wokwi simulation |
| `sim/maps` | `make_zippy_map.py` and everything it writes: map, zone masks, places |
| `sim/worlds` | The Gazebo world of the flat |
| `patches` | Small changes to linorobot2 for WSL |
| `docs` | The build journal |

## Run it

Each line in its own terminal:

    ros2 launch linorobot2_gazebo gazebo.launch.py world_name:=home urdf:=$ZIPPY_URDF spawn_x:=2.98 spawn_y:=0.5 spawn_yaw:=-1.5708
    ros2 launch zippy_navigation navigation.launch.py
    ros2 launch linorobot2_viz navigation.launch.py sim:=true
    ros2 launch zippy_mission brain.launch.py

Then open http://localhost:8000 and tap a place. Without Gazebo: `ros2 launch zippy_mission brain.launch.py fake:=true`.
