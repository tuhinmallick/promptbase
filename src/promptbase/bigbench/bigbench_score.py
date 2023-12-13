import datetime
import os
import json
import argparse

def score(api_type="chat"):
    ground_truth_dir = os.path.join("..", "datasets", "BigBench", "bbh")
    answer_dir = os.path.join(".", "results", "answers")

    score_dict = {}

    # loop through json files in ground truth path
    for filename in os.listdir(ground_truth_dir):
        if not filename.endswith(".json"):
            print(f"Skipping non-json file: {filename}")
            continue
        print(f"Processing file: {filename}")
        fname_base = filename.split(".")[0]
        answer_path = os.path.join(answer_dir, f"{fname_base}_{api_type}_answers.json")
        if not os.path.exists(answer_path):
            print(f"Answer file does not exist: {answer_path}")
            continue
        with open(os.path.join(ground_truth_dir, filename)) as f:
            ground_truth_data = json.load(f)
        with open(answer_path) as f:
            answer_data = json.load(f)

        print("Number of ground truth examples: " + str(len(ground_truth_data["examples"])))
        print(f"Number of answer examples: {len(answer_data)}")
        if len(ground_truth_data["examples"]) != len(answer_data):
            print(f"Number of examples does not match for file: {filename}")
            continue

        total_count = len(ground_truth_data["examples"])

        correct_count = sum(
            1
            for i, gt in enumerate(ground_truth_data["examples"])
            if gt["target"] == answer_data[i]["completion"]
        )
        score_dict[fname_base] = {
            "correct": correct_count,
            "total": total_count,
            "score": correct_count / total_count,
        }

    total_correct = 0
    total_overall = 0
    for v in score_dict.values():
        total_correct += v["correct"]
        total_overall += v["total"]

    score_dict["overall"] = {
        "correct": total_correct,
        "total": total_overall,
        "score": total_correct / total_overall,
    }

    print(score_dict)

    # save as json file
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    with open(f"bigbench_scores_{api_type}_{timestamp}.json", "w") as f:
        json.dump(score_dict, f)
