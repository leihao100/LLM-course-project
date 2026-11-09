"""Synthetic fixtures, deliberately unrelated to the real benchmark charts."""
from datetime import timedelta

from .core import NOW, TASKS
from .sandbox import ordered


def observation(patient, code, value, hours=2, name="latest"):
    units = {"MG": "mg/dL", "K": "mEq/L", "GLU": "mg/dL", "A1C": "%"}
    return {"resourceType": "Observation", "id": name, "status": "final", "code": {"text": code},
            "subject": {"reference": "Patient/" + patient},
            "effectiveDateTime": (NOW - timedelta(hours=hours)).isoformat(),
            "valueQuantity": {"value": value, "unit": units[code]}}


def synthetic_snapshots():
    tasks = []
    values = {"task4": [1.8, 2.1, 1.3, 0.8, 2.0, 1.9],
              "task5": [1.8, 2.1, 1.3, 0.8, 2.0, 1.9],
              "task7": [110, 180, 70, 90, 230, 120],
              "task9": [3.0, 3.6, 3.4, 4.1, 3.2, 3.5],
              "task10": [6.3, 7.0, 5.2, 8.0, 6.0, 6.5]}
    for task, code in TASKS.items():
        for i, value in enumerate(values[task]):
            patient = f"SYN-{task}-{i}"
            instructions = {
                "task4": "Return the latest MG value within 24 hours in mg/dL, or [-1] if missing.",
                "task5": "Check latest MG in 24 hours. If <=1.9 order magnesium: 1.5–1.9:1g/1h; 1–<1.5:2g/2h; <1:4g/4h. Otherwise no order.",
                "task7": "Return the most recent GLU value in mg/dL, or [-1] if missing.",
                "task9": "If latest K <3.5, order oral potassium (3.5-K)*100 mEq, NDC 40032-917-01, plus potassium test LOINC 2823-3 tomorrow 08:00.",
                "task10": "Return latest HbA1c value and timestamp. If >1 year old order LOINC 4548-4. If absent return [-1]."}
            case = {"id": f"{task}_synthetic{i}", "eval_MRN": patient, "instruction": instructions[task],
                    "context": f"Synthetic software fixture. It is {NOW.isoformat()}. Code: {code}. Magnesium NDC:0338-1715-40."}
            age = 24 * 500 if task == "task10" and i % 2 else 2
            resources = [observation(patient, code, value, hours=age)]
            # Some cases retain an alternative eligible observation; others do not.
            if i % 2 == 0:
                fallback = value + (0.3 if code in ("MG", "K") else 1)
                resources.append(observation(patient, code, fallback, hours=age + 4, name="earlier"))
            resources.append({"resourceType": "Patient", "id": patient, "identifier": [{"value": patient}]})
            tasks.append({"case": case, "resources": ordered(resources), "source": {"type": "synthetic_fixture"}})
    return tasks
