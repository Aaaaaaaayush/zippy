"""Zippy's brain and face together (Manual 0.6).

    ros2 launch zippy_mission brain.launch.py                         # with Gazebo and Nav2
    ros2 launch zippy_mission brain.launch.py fake:=true              # pretend Nav2, no Gazebo
    ros2 launch zippy_mission brain.launch.py fake:=true fake_fail:=kitchen
"""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PythonExpression
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    fake = LaunchConfiguration('fake')
    # Gazebo's clock when Zippy really drives; the computer's clock in pretend mode
    sim_time = PythonExpression(["'", fake, "'.lower() != 'true'"])
    return LaunchDescription([
        DeclareLaunchArgument('fake', default_value='false', description='true = pretend Nav2, no Gazebo needed'),
        DeclareLaunchArgument('fake_fail', default_value='', description='places that fail in pretend mode, e.g. kitchen'),
        DeclareLaunchArgument('port', default_value='8000', description='port of the touchscreen page'),
        Node(package='zippy_mission', executable='brain', name='zippy_mission', output='screen',
             parameters=[{'fake': PythonExpression(["'", fake, "'.lower() == 'true'"]),
                          'fake_fail': ParameterValue(LaunchConfiguration('fake_fail'), value_type=str),
                          'use_sim_time': sim_time}]),
        Node(package='zippy_mission', executable='face', name='zippy_ui', output='screen',
             parameters=[{'port': LaunchConfiguration('port'), 'use_sim_time': sim_time}]),
    ])
