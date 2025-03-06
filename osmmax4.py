import argparse
import subprocess
import re
import os
import uuid


def get_map_bounds(pbf_file):
    """获取地图的经纬度范围"""
    info_command = f"osmium fileinfo {pbf_file}"
    info_result = subprocess.run(info_command, shell=True, capture_output=True, text=True)
    output = info_result.stdout
    match = re.search(r'\((\S+),(\S+),(\S+),(\S+)\)', output)
    if match:
        min_lon = float(match.group(1))
        min_lat = float(match.group(2))
        max_lon = float(match.group(3))
        max_lat = float(match.group(4))
        return min_lon, min_lat, max_lon, max_lat
    else:
        print("无法获取经纬度范围")
        return None


def process_rectangle(rect_info, pbf_file):
    """处理单个矩形区域，返回数据量大小"""
    min_lon, min_lat, max_lon, max_lat = rect_info
    temp_file_id = str(uuid.uuid4())
    final_temp_file = f"final_temp_{temp_file_id}.osm.pbf"

    extract_command = f"osmium extract -b {min_lon},{min_lat},{max_lon},{max_lat} {pbf_file} -o {final_temp_file}"
    subprocess.run(extract_command, shell=True)

    size_command = f"osmium fileinfo {final_temp_file}"
    size_result = subprocess.run(size_command, shell=True, capture_output=True, text=True)
    size_output = size_result.stdout

    size_match = re.search(r'Size: (\d+)', size_output)
    if size_match:
        size = int(size_match.group(1))
        os.remove(final_temp_file)
        return size
    else:
        os.remove(final_temp_file)
        return 0


def hierarchical_search(pbf_file, target_rect_width, target_rect_height):
    """多层次递进搜索函数，动态生成每层网格参数"""
    bounds = get_map_bounds(pbf_file)
    if bounds is None:
        return

    current_min_lon, current_min_lat, current_max_lon, current_max_lat = bounds
    level = 1
    max_size = 0
    max_rect = None
    while True:
        print(f"开始第 {level} 层搜索...")
        print(f"搜索区域的经纬度: {current_min_lon}, {current_min_lat}, {current_max_lon}, {current_max_lat}")

        rect_width = current_max_lon - current_min_lon
        rect_height = current_max_lat - current_min_lat
        step_lon = rect_width / 16
        step_lat = rect_height / 16

        if rect_width <= 2 * target_rect_width or rect_height <= 2 * target_rect_height:
            break

        lon_steps = int((current_max_lon - current_min_lon) / (2 * step_lon))
        lat_steps = int((current_max_lat - current_min_lat) / (2 * step_lat))
        grid_count = lon_steps * lat_steps
        print(f"第 {level} 层总网格数: {grid_count}")

        for i in range(lon_steps):
            for j in range(lat_steps):
                current_rect_min_lon = current_min_lon + i * step_lon
                current_rect_max_lon = current_rect_min_lon + rect_width / 2
                current_rect_min_lat = current_min_lat + j * step_lat
                current_rect_max_lat = current_rect_min_lat + rect_height / 2
                rect_info = (current_rect_min_lon, current_rect_min_lat, current_rect_max_lon, current_rect_max_lat)
                size = process_rectangle(rect_info, pbf_file)
                print(f"第 {level} 层({i},{j})/({lon_steps-1},{lat_steps-1})搜索结果: {rect_info}，文件大小: {size} 字节")
                if size > max_size:
                    max_size = size
                    max_rect = rect_info
                    print(f"第 {level} 层找到数据量最大的矩形区域经纬度范围: {max_rect}，文件大小: {max_size} 字节")

        print(f"第 {level} 层找到数据量最大的矩形区域经纬度范围: {max_rect}，文件大小: {max_size} 字节")

        current_min_lon, current_min_lat, current_max_lon, current_max_lat = max_rect
        print(f"更新下一层的搜索范围: {current_min_lon}, {current_min_lat}, {current_max_lon}, {current_max_lat}")
        level += 1
        max_size = 0

    if max_rect is None:
        max_rect = (current_min_lon, current_min_lat, current_max_lon, current_max_lat)
        max_size = process_rectangle(max_rect, pbf_file)
        print(f"因提前结束循环，使用当前搜索范围作为结果，经纬度范围: {max_rect}，文件大小: {max_size} 字节")
    return max_rect, max_size


def final_fine_search(pbf_file, result_rect, target_rect_width, target_rect_height, step_lon, step_lat):
    """在 result_rect 范围内进行最终的精细搜索，步进可自定义"""
    min_lon, min_lat, max_lon, max_lat = result_rect

    lon_steps = int((max_lon - min_lon) / step_lon)
    lat_steps = int((max_lat - min_lat) / step_lat)
    grid_count = lon_steps * lat_steps
    print(f"最终精细搜索总网格数: {grid_count}")
    print(f"搜索区域的经纬度: {min_lon}, {min_lat}, {max_lon}, {max_lat}")

    max_size = 0
    max_rect = None
    for i in range(lon_steps):
        for j in range(lat_steps):
            current_rect_min_lon = min_lon + i * step_lon
            current_rect_max_lon = current_rect_min_lon + target_rect_width
            current_rect_min_lat = min_lat + j * step_lat
            current_rect_max_lat = current_rect_min_lat + target_rect_height
            rect_info = (current_rect_min_lon, current_rect_min_lat, current_rect_max_lon, current_rect_max_lat)
            size = process_rectangle(rect_info, pbf_file)
            print(f"精细搜索({i},{j})/（{lon_steps-1},{lat_steps-1}）结果: {rect_info}，文件大小: {size} 字节")
            if size > max_size:
                max_size = size
                max_rect = rect_info
                print(f"更新当前精细搜索找到数据量最大的矩形区域经纬度范围: {max_rect}，文件大小: {max_size} 字节")

    print(f"最终精细搜索找到数据量最大的矩形区域经纬度范围: {max_rect}，文件大小: {max_size} 字节")
    return max_rect, max_size


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='多层次递进搜索 PBF 文件')
    parser.add_argument('pbf_file', type=str, help='PBF 文件的路径')
    args = parser.parse_args()

    pbf_file = args.pbf_file

    filtered_pbf_file = "filtered.osm.pbf"
    filter_command = f"osmium tags-filter {pbf_file} nwr/highway nwr/building -o {filtered_pbf_file}"
    print(f"正在执行过滤命令: {filter_command}")
    subprocess.run(filter_command, shell=True)

    target_rect_width = 1
    target_rect_height = 1

    fine_step_lon = target_rect_width/10.0
    fine_step_lat = target_rect_height/10.0

    result_rect, result_size = hierarchical_search(filtered_pbf_file, target_rect_width, target_rect_height)

    min_lon, min_lat, max_lon, max_lat = result_rect
    result_width = max_lon - min_lon
    result_height = max_lat - min_lat
    if result_width > target_rect_width or result_height > target_rect_height:
        final_rect, final_size = final_fine_search(filtered_pbf_file, result_rect, target_rect_width, target_rect_height,
                                                   fine_step_lon, fine_step_lat)
    else:
        final_rect = result_rect
        final_size = result_size
        print(f"由于结果范围小于等于目标范围，直接使用结果范围，经纬度范围: {final_rect}，文件大小: {final_size} 字节")
    os.remove(filtered_pbf_file)
