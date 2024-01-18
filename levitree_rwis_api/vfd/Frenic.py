def function_code_to_coil(function_code: str) -> int:
    group = function_code[0:1]
    glt = {"F": 0, "E": 1, "C": 2, "P": 3, "H": 4, "A": 5, "b": 18, "r":10, "S": 7, "o": 6, "M": 8, "J": 13, "d": 19, "y": 14, "W": 15, "X": 16, "Z": 17}
    idn = int(function_code[1:])
    return glt[group]<<8 | idn