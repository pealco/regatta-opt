from typing import Dict, List, Optional, Union

from ortools.sat.python import cp_model


def optimize_regatta_schedule(
    races: Dict[str, List[List[int]]], num_lanes: int, start_time: int, end_time: int
) -> Optional[Dict[str, List[Dict[str, Union[int, Dict[int, int]]]]]]:
    model = cp_model.CpModel()

    # Variables
    race_starts: Dict[str, cp_model.IntVar] = {}
    boat_lanes: Dict[str, cp_model.IntVar] = {}
    for race_name, heats in races.items():
        for heat_index, boats in enumerate(heats):
            heat_name = f"{race_name}_Heat_{chr(ord('a') + heat_index)}"
            race_starts[heat_name] = model.NewIntVar(
                start_time, end_time, f"race_{heat_name}_start"
            )
            for boat_id in boats:
                boat_name = f"{heat_name}_Boat_{boat_id}"
                boat_lanes[boat_name] = model.NewIntVar(
                    1, num_lanes, f"boat_{boat_name}_lane"
                )

    # Constraints
    # 1. First race starts at 8:00 AM
    model.Add(race_starts[sorted(race_starts.keys())[0]] == start_time)

    # 2. Races are scheduled back-to-back with 8-minute intervals
    sorted_races = sorted(race_starts.keys())
    for i in range(len(sorted_races) - 1):
        model.Add(race_starts[sorted_races[i + 1]] == race_starts[sorted_races[i]] + 8)

    # 3. At any given time, no more than num_lanes boats are racing concurrently
    time_points = range(start_time, end_time + 1)
    for t in time_points:
        concurrent_races: List[cp_model.IntVar] = []
        for heat_name in race_starts:
            is_concurrent = model.NewBoolVar(f"race_{heat_name}_concurrent_at_{t}")
            model.Add(race_starts[heat_name] <= t).OnlyEnforceIf(is_concurrent)
            model.Add(race_starts[heat_name] + 8 > t).OnlyEnforceIf(is_concurrent)
            concurrent_races.append(is_concurrent)
        model.Add(sum(concurrent_races) <= num_lanes)

    # 4. 1x races must go before 12:00, 2x and 2- races should go before 12:00 if possible
    for race_name in races:
        boat_type = race_name.split("_")[0]
        if boat_type == "1x":
            for heat_index in range(len(races[race_name])):
                heat_name = f"{race_name}_Heat_{chr(ord('a') + heat_index)}"
                model.Add(race_starts[heat_name] < 12 * 60)
        elif boat_type in ["2x", "2-"]:
            for heat_index in range(len(races[race_name])):
                heat_name = f"{race_name}_Heat_{chr(ord('a') + heat_index)}"
                before_noon = model.NewBoolVar(f"race_{heat_name}_before_noon")
                model.Add(race_starts[heat_name] < 12 * 60).OnlyEnforceIf(before_noon)
                model.Add(race_starts[heat_name] >= 12 * 60).OnlyEnforceIf(
                    before_noon.Not()
                )

    # 5. Assign unique lanes to boats in each heat
    for race_name, heats in races.items():
        for heat_index, boats in enumerate(heats):
            heat_name = f"{race_name}_Heat_{chr(ord('a') + heat_index)}"
            boat_names = [f"{heat_name}_Boat_{boat_id}" for boat_id in boats]
            model.AddAllDifferent([boat_lanes[boat_name] for boat_name in boat_names])

    # Solve the model
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60  # Set a time limit for the solver
    status = solver.Solve(model)

    # Process and format the output
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        schedule: Dict[str, List[Dict[str, Union[int, Dict[int, int]]]]] = {}
        for race_name, heats in races.items():
            schedule[race_name] = []
            for heat_index in range(len(heats)):
                heat_name = f"{race_name}_Heat_{chr(ord('a') + heat_index)}"
                heat_info: Dict[str, Union[int, Dict[int, int]]] = {
                    "start_time": solver.Value(race_starts[heat_name]),
                    "boat_lanes": {},
                }
                for boat_id in heats[heat_index]:
                    boat_name = f"{heat_name}_Boat_{boat_id}"
                    heat_info["boat_lanes"][boat_id] = solver.Value(
                        boat_lanes[boat_name]
                    )
                schedule[race_name].append(heat_info)
        return schedule
    else:
        print("No feasible solution found.")
        return None


def generate_races(
    race_definitions: Dict[str, Dict[str, List[str]]], boats_per_race: Dict[str, int]
) -> Dict[str, List[List[int]]]:
    races: Dict[str, List[List[int]]] = {}
    for boat_type, categories in race_definitions.items():
        for category, divisions in categories.items():
            for division in divisions:
                race_name = f"{boat_type}_{category}_{division}"
                num_boats = boats_per_race[boat_type]
                num_heats = (num_boats + 4) // 5
                races[race_name] = [list(range(1, 6)) for _ in range(num_heats)]
                remaining_boats = num_boats % 5
                if remaining_boats > 0:
                    races[race_name][-1] = races[race_name][-1][:remaining_boats]
    return races


# Example usage
race_definitions = {
    "1x": {
        "Open": ["Womens", "Mens", "Nonbinary"],
        "Masters": ["Womens", "Mens", "Nonbinary"],
        "Adaptive": ["Womens", "Mens", "Nonbinary"],
    },
    "2x": {
        "Open": ["Womens", "Mens", "Nonbinary", "Mixed"],
        "Masters": ["Womens", "Mens", "Nonbinary", "Mixed"],
        "Adaptive": ["Womens", "Mens", "Nonbinary", "Mixed"],
    },
    "2-": {
        "Open": ["Womens", "Mens", "Nonbinary"],
        "Masters": ["Womens", "Mens", "Nonbinary"],
    },
    "4+": {"Open": ["Womens", "Mens", "Mixed"], "Masters": ["Womens", "Mens", "Mixed"]},
    "8+": {"Open": ["Womens", "Mens", "Mixed"], "Masters": ["Womens", "Mens", "Mixed"]},
}

boats_per_race = {"1x": 8, "2x": 10, "2-": 7, "4+": 5, "8+": 4}

races = generate_races(race_definitions, boats_per_race)

num_lanes = 5
start_time = 8 * 60  # 8:00 AM
end_time = 17 * 60  # 4:00 PM

optimized_schedule = optimize_regatta_schedule(races, num_lanes, start_time, end_time)

if optimized_schedule:
    print("heat name, race time, race name, lane 1, lane 2, lane 3, lane 4, lane 5")
    sorted_heats = []
    for race_name, heats in optimized_schedule.items():
        for heat_index, heat_info in enumerate(heats):
            heat_name = f"{race_name}_Heat_{chr(ord('a') + heat_index)}"
            sorted_heats.append(
                (heat_info["start_time"], heat_name, race_name, heat_info["boat_lanes"])
            )

    sorted_heats.sort()  # Sort heats based on start time

    race_number = 1
    for _, heat_name, race_name, boat_lanes in sorted_heats:
        start_time = optimized_schedule[race_name][ord(heat_name[-1]) - ord("a")][
            "start_time"
        ]
        heat_label = (
            f"{race_number}"
            if len(optimized_schedule[race_name]) == 1
            else f"{race_number}{heat_name[-1]}"
        )
        lane_info = [""] * num_lanes
        for boat_id, lane in boat_lanes.items():
            lane_info[lane - 1] = f"Boat {boat_id}"
        print(
            f"{heat_label}, {start_time // 60:02d}:{start_time % 60:02d}, {race_name}, {', '.join(lane_info)}"
        )
        if heat_name[-1] == chr(ord("a") + len(optimized_schedule[race_name]) - 1):
            race_number += 1
