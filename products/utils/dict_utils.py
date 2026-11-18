
def deep_merge(existing, incoming):
    result = existing.copy()

    for key, value in incoming.items():
        if not key in result:
            result[key] = value
            continue

        old_value = result[key]
        if isinstance(old_value, dict) and isinstance(value, dict):
            result[key] = deep_merge(value, old_value)

        elif type(old_value) is not type(value):
            raise ValueError(
                f"Type mismatch for attribute '{key}'"
            )
        else:
            result[key] = value

    return result