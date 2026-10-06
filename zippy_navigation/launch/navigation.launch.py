"""Zippy's navigation, v0.5 (Manual 0.5, 5 Oct 2026).

Starts Nav2 (nav2_bringup) with Zippy's settings, plus the keep-out and slow-zone filters.

    ros2 launch zippy_navigation navigation.launch.py

Arguments:
    map:=<path to map yaml>   default: the flat map made by make_zippy_map.py
    sim:=true|false           default: true (Gazebo clock). false on the real robot.
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node, SetParameter
from launch_ros.descriptions import ParameterFile
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    share = FindPackageShare('zippy_navigation')
    params_file = PathJoinSubstitution([share, 'config', 'zippy_nav2.yaml'])
    default_map = PathJoinSubstitution([share, 'maps', 'home.yaml'])
    use_sim_time = LaunchConfiguration('sim')

    # The four filter nodes read their settings from the same yaml file.
    # allow_substs turns $(find-pkg-share ...) in it into real paths.
    filter_params = ParameterFile(params_file, allow_substs=True)
    filter_nodes = [
        'keepout_mask_server', 'keepout_filter_info_server',
        'speed_mask_server', 'speed_filter_info_server',
    ]

    filters = GroupAction([
        SetParameter('use_sim_time', use_sim_time),
        Node(package='nav2_map_server', executable='map_server',
             name='keepout_mask_server', parameters=[filter_params], output='screen'),
        Node(package='nav2_map_server', executable='costmap_filter_info_server',
             name='keepout_filter_info_server', parameters=[filter_params], output='screen'),
        Node(package='nav2_map_server', executable='map_server',
             name='speed_mask_server', parameters=[filter_params], output='screen'),
        Node(package='nav2_map_server', executable='costmap_filter_info_server',
             name='speed_filter_info_server', parameters=[filter_params], output='screen'),
        # Starts the four nodes above, the same way Nav2 starts its own
        Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
             name='lifecycle_manager_filters', output='screen',
             parameters=[{'autostart': True, 'node_names': filter_nodes}]),
    ])

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            PathJoinSubstitution([FindPackageShare('nav2_bringup'), 'launch', 'bringup_launch.py'])),
        launch_arguments={
            'map': LaunchConfiguration('map'),
            'use_sim_time': use_sim_time,
            'params_file': params_file,
        }.items(),
    )

    return LaunchDescription([
        DeclareLaunchArgument('map', default_value=default_map,
                              description='Full path to the map yaml'),
        DeclareLaunchArgument('sim', default_value='true',
                              description='true in Gazebo, false on the real robot'),
        filters,
        nav2,
    ])
