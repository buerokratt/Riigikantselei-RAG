def is_float(value: str) -> bool:
    normalized_numbers = value.replace('.', '')
    if '.' in value and str.isdigit(normalized_numbers):
        return True

    return False
