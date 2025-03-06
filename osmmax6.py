import argparse
import subprocess
import re
import os
import uuid
import random
import math


def get_map_bounds(pbf_file):
    """Get the latitude and longitude range of the map"""
    info_command = f"osmium fileinfo {pbf_file}"
    print(f"Executing command to get map bounds: {info_command}")
    info_result = subprocess.run(info_command, shell=True, capture_output=True, text=True)
    output = info_result.stdout
    match = re.search(r'\((\S+),(\S+),(\S+),(\S+)\)', output)
    if match:
        min_lon = float(match.group(1))
        min_lat = float(match.group(2))
        max_lon = float(match.group(3))
        max_lat = float(match.group(4))
        print(f"Successfully obtained map bounds: ({min_lon}, {min_lat}, {max_lon}, {max_lat})")
        return min_lon, min_lat, max_lon, max_lat
    else:
        print("Failed to obtain latitude and longitude range")
        return None


def process_rectangle(rect_info, pbf_file):
    """Process a single rectangular area and return the data size"""
    min_lon, min_lat, max_lon, max_lat = rect_info
    temp_file_id = str(uuid.uuid4())
    # Use /dev/shm as the temporary file storage location
    final_temp_file = f"/dev/shm/final_temp_{temp_file_id}.osm.pbf"

    extract_command = f"osmium extract -b {min_lon},{min_lat},{max_lon},{max_lat} {pbf_file} -o {final_temp_file}"
    print(f"Executing command to extract rectangular area data: {extract_command}")
    subprocess.run(extract_command, shell=True)

    size_command = f"osmium fileinfo {final_temp_file}"
    print(f"Executing command to get the size of the extracted file: {size_command}")
    size_result = subprocess.run(size_command, shell=True, capture_output=True, text=True)
    size_output = size_result.stdout

    size_match = re.search(r'Size: (\d+)', size_output)
    if size_match:
        size = int(size_match.group(1))
        print(f"Successfully obtained the data size of the rectangular area: {size} bytes. Deleting temporary file {final_temp_file}")
        os.remove(final_temp_file)
        return size
    else:
        print(f"Failed to obtain data size. Deleting temporary file {final_temp_file}")
        os.remove(final_temp_file)
        return 0


# Define the rectangle area class
class Rectangle:
    def __init__(self, min_lon, min_lat, max_lon, max_lat):
        self.min_lon = min_lon
        self.min_lat = min_lat
        self.max_lon = max_lon
        self.max_lat = max_lat

    def get_size(self, pbf_file):
        return process_rectangle((self.min_lon, self.min_lat, self.max_lon, self.max_lat), pbf_file)


# Genetic algorithm main function
def genetic_algorithm(pbf_file, target_rect_width, target_rect_height, population_size=10, generations=100):
    # Initialize the population
    bounds = get_map_bounds(pbf_file)
    if bounds is None:
        return

    min_lon, min_lat, max_lon, max_lat = bounds
    population = []
    print(f"Starting to initialize the population. Population size: {population_size}")
    for i in range(population_size):
        rect_min_lon = random.uniform(min_lon, max_lon - target_rect_width)
        rect_min_lat = random.uniform(min_lat, max_lat - target_rect_height)
        rect_max_lon = rect_min_lon + target_rect_width
        rect_max_lat = rect_min_lat + target_rect_height
        population.append(Rectangle(rect_min_lon, rect_min_lat, rect_max_lon, rect_max_lat))
        print(f"Initializing the {i + 1}-th individual: ({rect_min_lon}, {rect_min_lat}, {rect_max_lon}, {rect_max_lat})")

    # Iterative evolution
    for generation in range(generations):
        print(f"\nStarting the {generation + 1}-th generation of evolution")
        # Calculate fitness values
        fitness_values = [rect.get_size(pbf_file) for rect in population]
        print(f"Fitness values of individuals in the {generation + 1}-th generation: {fitness_values}")

        # Selection operation (roulette wheel selection)
        total_fitness = sum(fitness_values)
        selection_probs = [fitness / total_fitness for fitness in fitness_values]
        print(f"Selection probabilities of individuals in the {generation + 1}-th generation: {selection_probs}")
        new_population = []
        for _ in range(population_size):
            selected_index = random.choices(range(population_size), weights=selection_probs)[0]
            new_population.append(population[selected_index])
        print(f"Indices of individuals in the new population after selection in the {generation + 1}-th generation: {[i for i, _ in enumerate(new_population)]}")

        # Crossover operation
        for i in range(0, population_size, 2):
            parent1 = new_population[i]
            parent2 = new_population[i + 1]
            # Simple crossover method, exchange part of the boundaries
            crossover_point = random.random()
            child1_min_lon = parent1.min_lon * crossover_point + parent2.min_lon * (1 - crossover_point)
            child1_min_lat = parent1.min_lat * crossover_point + parent2.min_lat * (1 - crossover_point)
            child1_max_lon = child1_min_lon + target_rect_width
            child1_max_lat = child1_min_lat + target_rect_height
            child2_min_lon = parent2.min_lon * crossover_point + parent1.min_lon * (1 - crossover_point)
            child2_min_lat = parent2.min_lat * crossover_point + parent1.min_lat * (1 - crossover_point)
            child2_max_lon = child2_min_lon + target_rect_width
            child2_max_lat = child2_min_lat + target_rect_height
            new_population[i] = Rectangle(child1_min_lon, child1_min_lat, child1_max_lon, child1_max_lat)
            new_population[i + 1] = Rectangle(child2_min_lon, child2_min_lat, child2_max_lon, child2_max_lat)
            print(f"Crossover of the {i // 2 + 1}-th group in the {generation + 1}-th generation. Offspring 1: ({child1_min_lon}, {child1_min_lat}, {child1_max_lon}, {child1_max_lat}), Offspring 2: ({child2_min_lon}, {child2_min_lat}, {child2_max_lon}, {child2_max_lat})")

        # Mutation operation
        for j, rect in enumerate(new_population):
            if random.random() < 0.1:  # Mutation probability
                old_min_lon = rect.min_lon
                old_min_lat = rect.min_lat
                rect.min_lon += random.uniform(-0.1, 0.1)
                rect.min_lat += random.uniform(-0.1, 0.1)
                rect.max_lon = rect.min_lon + target_rect_width
                rect.max_lat = rect.min_lat + target_rect_height
                print(f"Mutation occurred in the {j + 1}-th individual in the {generation + 1}-th generation. Old coordinates: ({old_min_lon}, {old_min_lat}), New coordinates: ({rect.min_lon}, {rect.min_lat})")

        population = new_population

    # Find the optimal solution
    fitness_values = [rect.get_size(pbf_file) for rect in population]
    best_index = fitness_values.index(max(fitness_values))
    best_rect = population[best_index]
    best_size = best_rect.get_size(pbf_file)
    best_rect_info = (best_rect.min_lon, best_rect.min_lat, best_rect.max_lon, best_rect.max_lat)
    print(f"\nGenetic algorithm completed. The rectangular area with the largest data size has the following bounds: {best_rect_info}, File size: {best_size} bytes")
    return best_rect_info, best_size


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Search PBF files using a genetic algorithm')
    parser.add_argument('pbf_file', type=str, help='Path to the PBF file')
    args = parser.parse_args()

    pbf_file = args.pbf_file

    # Store the filtered file in /dev/shm
    filtered_pbf_file = f"/dev/shm/filtered1.osm.pbf"
    filter_command = f"osmium tags-filter {pbf_file} nwr/highway nwr/building -o {filtered_pbf_file}"
    print(f"Executing the filtering command: {filter_command}")
    subprocess.run(filter_command, shell=True)

    target_rect_width = 1
    target_rect_height = 1

    result_rect, result_size = genetic_algorithm(filtered_pbf_file, target_rect_width, target_rect_height)

    # Delete the filtered file in memory
    os.remove(filtered_pbf_file)