cmake_minimum_required(VERSION 3.8)
project(zippy_navigation)

find_package(ament_cmake REQUIRED)

install(DIRECTORY config launch DESTINATION share/${PROJECT_NAME})

# The maps live one folder up, in sim/maps, next to make_zippy_map.py that writes them.
# With --symlink-install the installed copies point back there, so rerunning the script
# updates Nav2's maps without a rebuild. (A brand-new file needs one rebuild.)
install(DIRECTORY ../sim/maps/ DESTINATION share/${PROJECT_NAME}/maps)

install(PROGRAMS scripts/go.py DESTINATION lib/${PROJECT_NAME})

ament_package()
