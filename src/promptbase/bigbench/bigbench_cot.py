import openai
import requests
import os
import json
import time
import argparse
import threading


bigbench_data_root = "../datasets/BigBench"
cot_prompts_dir = os.path.join(bigbench_data_root, "cot-prompts")
bbh_test_dir = os.path.join(bigbench_data_root, "bbh")

SUBJECTS = [
    "boolean_expressions",
    "causal_judgement",
    "date_understanding",
    "disambiguation_qa",
    "dyck_languages",
    "formal_fallacies",
    "geometric_shapes",
    "hyperbaton",
    "logical_deduction_five_objects",
    "logical_deduction_seven_objects",
    "logical_deduction_three_objects",
    "movie_recommendation",
    "multistep_arithmetic_two",
    "navigate",
    "object_counting",
    "penguins_in_a_table",
    "reasoning_about_colored_objects",
    "ruin_names",
    "salient_translation_error_detection",
    "snarks",
    "sports_understanding",
    "temporal_sequences",
    "tracking_shuffled_objects_five_objects",
    "tracking_shuffled_objects_seven_objects",
    "tracking_shuffled_objects_three_objects",
    "web_of_lies",
    "word_sorting",
]


def extract_chat_qa(few_shot_prompt):
    question = few_shot_prompt.split("\nA: ")[0].strip()
    answer = "A: " + few_shot_prompt.split("\nA: ")[1].strip()
    print("fewshot===")
    print("Q: ", question)
    print("A: ", answer)
    return (question, answer)


def do_chat_cot(bbh_test_path, cot_prompt_path, test_name, cot_results_path):
    print(f"Processing {test_name}")
    test_results = []
    with open(cot_prompt_path, "r", encoding="utf-8") as file:
        cot_prompt_contents = file.read()
        # use everything starting with the third line
        cot_prompt_contents = "\n".join(cot_prompt_contents.split("\n")[2:])

    few_shots = cot_prompt_contents.split("\n\n")
    # The first shot starts with an instruction, then two newlines, then the first shot
    instruction = few_shots[0]
    qa_pairs = [extract_chat_qa(few_shot) for few_shot in few_shots[1:]]
    few_shot_messages = [
        {"role": "system", "content": f"{instruction}"},
    ]

    for question, answer in qa_pairs:
        few_shot_messages.extend(
            (
                {"role": "user", "content": f"{question}"},
                {"role": "assistant", "content": f"{answer}"},
            )
        )
    with open(bbh_test_path, "r", encoding="utf-8") as file:
        example_data = json.load(file)
        for i, example in enumerate(example_data["examples"]):
            print(
                f"Processing example {i} of {len(example_data['examples'])} for {test_name}"
            )
            prompt_messages = few_shot_messages + [
                {"role": "user", "content": "Q: " + example["input"]}
            ]
            header = {"Authorization": os.getenv("AZURE_OPENAI_API_KEY")}
            data = {
                "model": "gpt-4-1106-preview",
                "temperature": 0,
                "messages": prompt_messages,
                "max_tokens": 2000,
            }
            url = os.getenv("AZURE_OPENAI_API_URL")
            while True:
                try:
                    response = requests.post(
                        url, headers=header, json=data, timeout=600
                    )
                    completion = json.loads(response.text)
                    test_results.append(
                        {
                            "index": i,
                            "test_name": test_name,
                            "prompt": prompt_messages,
                            "completion": completion["choices"][0]["message"][
                                "content"
                            ],
                        }
                    )
                    break
                except Exception as e:
                    print("Caught exception: ", e)
                    print("Retrying in 35 seconds...")
                    time.sleep(35)
            cot_results_filename = os.path.join(cot_results_path, f"{test_name}_chat_cot_results.json")
            json.dump(
                cot_results_filename, open(f"{test_name}_chat_cot_results.json", "w"), indent=4
            )


def do_completion_cot(bbh_test_path, cot_prompt_path, test_name, cot_results_path):
    print(f"Processing {test_name}")
    test_results = []
    with open(cot_prompt_path, "r", encoding="utf-8") as file:
        cot_prompt_contents = file.read()
        # use everything starting with the third line
        cot_prompt_contents = "\n".join(cot_prompt_contents.split("\n")[2:]).strip()

    print("Chain of thought few-shot prompt:\n", cot_prompt_contents)

    with open(bbh_test_path, "r", encoding="utf-8") as file:
        example_data = json.load(file)
        for i, example in enumerate(example_data["examples"]):
            print(
                f"Processing example {i} of {len(example_data['examples'])} for {test_name}"
            )
            prompt = f"{cot_prompt_contents}\n\nQ: {example['input']}\nA: Let's think step by step.\n"
            while True:
                try:
                    completion = openai.Completion.create(
                        engine="gemini-compete-wus",
                        prompt=prompt,
                        temperature=0,
                        max_tokens=2000,
                        top_p=1,
                        frequency_penalty=0,
                        presence_penalty=0,
                        best_of=1,
                        stop="\n\n",
                        # stop=["\n\n", "\nQ: ", "\nQ:", "\n\nQ:", "\n\nQ: ", "\nQ: "],
                    )
                    test_results.append(
                        {
                            "index": i,
                            "test_name": test_name,
                            "prompt": prompt,
                            "completion": completion["choices"][0]["text"],
                        }
                    )
                    break
                except Exception as e:
                    print("Caught exception: ", e)
                    print("Retrying in 5 seconds...")
                    time.sleep(5)
            cot_results_filename = os.path.join(cot_results_path, f"{test_name}_completion_cot_results.json")
            json.dump(
                test_results,
                open(cot_results_filename, "w"),
                indent=4,
            )

def process_cot(test_name: str, api_type="chat"):
    if test_name == "all":
        subjects = SUBJECTS
    elif test_name in SUBJECTS:
        subjects = [test_name]
    else:
        print(f"Invalid test name: {test_name}")
        exit(1)

    print(f"Processing CoT for BigBench subjects: {subjects}")

    threads = []
    for subject in subjects:
        bbh_test_path = os.path.join(bbh_test_dir, f"{subject}.json")
        cot_prompt_path = os.path.join(cot_prompts_dir, f"{subject}.txt")
        # check if they exist
        if not os.path.exists(bbh_test_path):
            print(f"Data file {bbh_test_path} does not exist")
        elif not os.path.exists(cot_prompt_path):
            print(f"COT prompt file {cot_prompt_path} does not exist")

        if api_type == "completion":
            results_path = os.path.join(".", "results", "cot_results", "completion")
            thread = threading.Thread(
                target=do_completion_cot, args=(bbh_test_path, cot_prompt_path, subject, results_path)
            )
        else:
            results_path = os.path.join(".", "results", "cot_results", "chat")
            thread = threading.Thread(
                target=do_chat_cot, args=(bbh_test_path, cot_prompt_path, subject, results_path)
            )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    print("Done!")