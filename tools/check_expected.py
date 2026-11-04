"""Compare one output JSON with an expected JSON and list every difference."""
import json
import sys


def find_differences(actual, expected, path="(root)"):
    """Return a list of "path: actual vs expected" strings."""
    differences = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in actual:
                differences.append(f"{path}/{key}: missing in output")
            elif key not in expected:
                differences.append(f"{path}/{key}: extra field in output")
            else:
                differences += find_differences(actual[key], expected[key], f"{path}/{key}")
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(actual) != len(expected):
            differences.append(f"{path}: {len(actual)} entries vs expected {len(expected)}")
        for index, (a, e) in enumerate(zip(actual, expected)):
            differences += find_differences(a, e, f"{path}[{index}]")
    elif actual != expected:
        differences.append(f"{path}: got {actual!r}, expected {expected!r}")
    return differences


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: python check_expected.py <output.json> <expected.json>")
    with open(sys.argv[1], encoding="utf-8") as f:
        actual = json.load(f)
    with open(sys.argv[2], encoding="utf-8") as f:
        expected = json.load(f)

    differences = find_differences(actual, expected)
    if differences:
        print(f"{len(differences)} difference(s):")
        for line in differences:
            print("  " + line)
        sys.exit(1)
    print("MATCH: output equals expected")
